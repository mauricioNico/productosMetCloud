#!/usr/bin/env python3
"""Clasificación espacial de LABORATORIO (NO OPERATIVA) a partir de dos CSV GRIB reales.

Geografía: geometría provincial de respaldo (solo para ensayo).
Regionalización: cercanía de <= 120 km a unidades con región conocida.
Los puntos restantes se etiquetan SIN_REGION y NO se colorean como verdes.
La regionalización provisoria NO debe utilizarse para emitir alertas oficiales.
"""
import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

from generar_alertas_web import consenso, leer_umbrales, NIVELES

PASOS = list(range(6, 73, 6))
PLAZOS = (24, 48, 72)
RADIO_KM = 120
NIVEL = {"AMARILLO": 1, "NARANJA": 2, "ROJO": 3}
COLUMNAS = ("model", "run_time", "valid_time", "lead_h", "lat", "lon",
            "precip_interval_mm", "precip_window_h", "wind_kmh", "gust_kmh", "estado")


def geometria_provincias(repo):
    files = sorted((repo / "web/cartografia").glob("referencia_provincias_*.geojson"))
    if len(files) != 4:
        raise ValueError("Faltan las cuatro capas provinciales de respaldo")
    polys = []
    for p in files:
        datos = json.loads(p.read_text(encoding="utf-8"))
        for feat in datos["features"]:
            geom = shape(feat["geometry"]).intersection(box(-85, -55, -45, -20))
            if not geom.is_empty and geom.is_valid and geom.area > .005:
                polys.append(geom)
    if len(polys) < 20:
        raise ValueError("La cobertura provincial es incompleta")
    return unary_union(polys)


def leer_puntos(path):
    d = pd.read_csv(path, sep=";", low_memory=False)
    mandatory = set(COLUMNAS)
    if not mandatory.issubset(d.columns):
        raise ValueError(f"{path}: faltan {mandatory-set(d.columns)}")
    if d["model"].nunique() != 1:
        raise ValueError(f"{path}: hay más de un modelo")
    if sorted(d.lead_h.unique().tolist()) != PASOS:
        raise ValueError(f"{path}: faltan pasos 6...72 horas")
    if d["run_time"].nunique() != 1:
        raise ValueError(f"{path}: ciclo ambiguo")
    lats = np.sort(d.lat.unique().astype(float))
    lons = np.sort(d.lon.unique().astype(float))
    ny, nx = len(lats), len(lons)
    d.sort_values(["lead_h", "lat", "lon"], inplace=True)
    if len(d) != len(PASOS)*ny*nx:
        raise ValueError(f"{path}: grilla irregular o faltan celdas")
    arrays = {}
    for column in ("precip_interval_mm", "precip_window_h", "wind_kmh", "gust_kmh"):
        arrays[column] = pd.to_numeric(d[column], errors="coerce").to_numpy().reshape((len(PASOS), ny, nx))
    for step, window in zip(PASOS, arrays["precip_window_h"]):
        if not np.all(np.isfinite(window)) or len(np.unique(window)) != 1:
            raise ValueError(f"{path}: metadatos de ventana incompletos en f{step}")
    return {"model":str(d["model"].iloc[0]), "run":str(d["run_time"].iloc[0]),
            "lat":lats, "lon":lons, **arrays}


def normalizar_acumulados(datos):
    pp = datos["precip_interval_mm"]
    if not np.all(np.isfinite(pp)):
        raise ValueError(f"{datos['model']}: faltan valores de lluvia GRIB")
    if datos["model"] == "GFS":
        # GFS puede entregar 0-fN (acumulado desde el ciclo) O f(N-6)-fN.
        # El índice NOAA confirma ambos tipos en una misma corrida.
        # Reconstruir 6h usando el saldo ya acumulado hasta el paso anterior.
        windows = datos["precip_window_h"]
        inc = np.zeros_like(pp)
        saldo = np.zeros_like(pp[0])
        for i, step in enumerate(PASOS):
            if np.all(windows[i] == step):
                # De 0 a fN, restar la precipitación de f000 a f(N-6).
                nueva = pp[i] - saldo
            elif np.all(windows[i] == 6):
                nueva = pp[i]
            else:
                raise ValueError(f"GFS f{step}: ventana no compatible con sumas de 6h")
            if np.nanmin(nueva) < -0.2:
                raise ValueError(f"GFS f{step}: descenso del acumulado al restar intervalo previo")
            inc[i] = np.maximum(nueva, 0)
            saldo += inc[i]
    elif datos["model"] == "ECMWF":
        for i, step in enumerate(PASOS):
            if not np.all(datos["precip_window_h"][i] == step):
                raise ValueError(f"ECMWF f{step}: acumulado distinto a 0-f{step}")
        inc = np.diff(np.concatenate([np.zeros_like(pp[:1]), pp], axis=0), axis=0)
        if np.nanmin(inc) < -0.2:
            raise ValueError("ECMWF: acumulados no monótonos; revisar reinicios GRIB")
        inc = np.maximum(inc, 0)
    else:
        raise ValueError(f"Modelo desconocido {datos['model']}")
    return inc


def mascara_y_regiones(lat, lon, pais, unidades_csv):
    lons, lats = np.meshgrid(lon, lat)
    dentro = shapely.contains_xy(pais, lons, lats)
    regiones = {k:np.full(lons.shape, "", dtype="<U16") for k in ("LLUVIA", "VIENTO")}
    menor = np.full(lons.shape, np.inf, dtype=float)
    with open(unidades_csv, encoding="utf-8", newline="") as f:
        for unidad in csv.DictReader(f, delimiter=";"):
            if unidad.get("activo", "").lower() != "true":
                continue
            if not unidad["region_lluvia"].startswith("PP_R") or not unidad["region_viento"].startswith("WIND_R"):
                continue
            ulat, ulon = float(unidad["lat"]),float(unidad["lon"])
            if not (-55 <= ulat <= -20 and -85 <= ulon <= -45):
                continue
            a1, a2 = np.deg2rad(lats), np.deg2rad(ulat)
            dlat = a2 - a1
            dlon = np.deg2rad(lons-ulon)
            a = np.sin(dlat/2)**2 + np.cos(a1)*np.cos(a2)*np.sin(dlon/2)**2
            km = 2*6371*np.arcsin(np.minimum(1,np.sqrt(a)))
            accept = dentro & (km < menor) & (km <= RADIO_KM)
            menor[accept] = km[accept]
            regiones["LLUVIA"][accept] = unidad["region_lluvia"]
            regiones["VIENTO"][accept] = unidad["region_viento"]
    return dentro, regiones


def acumulados_y_viento(datos):
    inc = normalizar_acumulados(datos)
    salida = {}
    for lead in PLAZOS:
        start = (lead - 24)//6
        end = lead//6
        p = inc[start:end]
        # Tres ventanas completas de 12 h: 0-12, 6-18, 12-24.
        p12 = np.maximum.reduce([p[0]+p[1],p[1]+p[2],p[2]+p[3]])
        p24 = np.sum(p, axis=0)
        # Muestreo cada 6 h; NO son máximos continuos del intervalo.
        v = datos["wind_kmh"][start:end]
        g = datos["gust_kmh"][start:end]
        v_max = np.where(np.any(np.isfinite(v),axis=0), np.nanmax(v,axis=0), np.nan)
        g_max = np.where(np.any(np.isfinite(g),axis=0), np.nanmax(g,axis=0), np.nan)
        salida[lead] = dict(p12=p12, p24=p24, viento=v_max, rafaga=g_max)
    return salida


def categorizar(valores, fenomeno, regiones, rules):
    region_grid = regiones[fenomeno]
    out = np.full(region_grid.shape, -1, dtype=np.int8)
    for region in np.unique(region_grid):
        if not region:
            continue
        rlist = rules.get((fenomeno.lower(), region), [])
        if not rlist:
            continue
        where = region_grid == region
        if fenomeno=="LLUVIA":
            mask = np.isfinite(valores["p12"]) & np.isfinite(valores["p24"])
        else:
            mask = np.isfinite(valores["viento"]) | np.isfinite(valores["rafaga"])
        out[where & mask] = 0
        for level, variable, hours, op, limit in rlist:
            if fenomeno=="LLUVIA":
                if variable != "precip_interval_mm":
                    raise ValueError(variable)
                val = valores["p12"] if hours==12 else valores["p24"] if hours==24 else None
            else:
                val = valores["viento"] if variable=="wind_kmh" else valores["rafaga"] if variable=="gust_kmh" else None
            if val is None:
                raise ValueError(f"Regla sin datos: {fenomeno} {variable} {hours}")
            good = (val >= limit) if op==">=" else (val > limit) if op==">" else None
            if good is None: raise ValueError(f"Operador inválido {op}")
            out[where & good & mask] = np.maximum(out[where & good & mask], level)
    return out


def convertir_geojson(lat, lon, niveles, fuentes, confianza, pais, fen, lead, ciclo):
    # Transformación de malla a polígonos, fusionando celdas vecinas del mismo nivel.
    geoms = {}
    from shapely.geometry import box as cell
    present = np.argwhere(niveles >= 0)
    for i, j in present:
        k = (int(niveles[i,j]), str(fuentes[i,j]), str(confianza[i,j]))
        geoms.setdefault(k, []).append(cell(float(lon[j]-.125),float(lat[i]-.125),
                                            float(lon[j]+.125),float(lat[i]+.125)))
    features = []
    for (n, src, conf), cells in geoms.items():
        poly = unary_union(cells).intersection(pais)
        if poly.is_empty:
            continue
        features.append({"type":"Feature", "geometry":mapping(poly),
                         "properties":{"nivel":NIVELES[n], "fenomeno":fen,
                           "periodo":f"{lead}h", "inicio_h":lead-24,
                           "fin_h":lead, "fuente":src, "confianza":conf,
                           "run_time":ciclo,"ambito":"EXPERIMENTAL",
                           "regionalizacion":"RADIO_120_KM_UNIDADES_NO_OPERATIVO"}})
    return {"type":"FeatureCollection","features":features}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--gfs",required=True)
    p.add_argument("--ecmwf",required=True)
    p.add_argument("--repo",default=".")
    p.add_argument("--out",default="salidas_regionales")
    a=p.parse_args()
    repo=Path(a.repo)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    modelos={m:leer_puntos(path) for m,path in (("GFS",a.gfs),("ECMWF",a.ecmwf))}
    for m,d in modelos.items():
        if d["model"]!=m:raise ValueError("Modelo y ruta no coinciden")
    g,e=modelos["GFS"],modelos["ECMWF"]
    if not (np.array_equal(g["lat"],e["lat"]) and np.array_equal(g["lon"],e["lon"])):
        raise ValueError("Las grillas GFS y ECMWF no coinciden: interpolación pendiente")
    if g["run"] != e["run"]:raise ValueError("Ciclos distintos, rechazar consenso")
    pais=geometria_provincias(repo)
    dentro,regiones=mascara_y_regiones(g["lat"],g["lon"],pais,repo/"vigilancia/config/unidades.csv")
    rules=leer_umbrales(repo/"vigilancia/config/umbrales.csv")
    valores={m:acumulados_y_viento(d) for m,d in modelos.items()}
    meta={"tipo":"MONITOREO_EXPERIMENTAL_NO_OPERATIVO",
          "publicacion_autorizada":False, "run_time":g["run"],
          "dominio":{"south":-55,"north":-20,"west":-85,"east":-45},
          "modelos":["GFS","ECMWF"],"regionalizacion":"Radio de 120 km alrededor de unidades. NO equivale a polígonos SMN.",
          "restricciones":["Sólo se clasifican celdas cercanas a unidades existentes",
                           "Mapa provincial de referencia comunitaria, no oficial",
                           "Viento y ráfagas muestreados cada 6 horas",
                           "Sin regiones cartográficas nacionales verificadas, no publicar"],
          "capas":{},"conteos":{}}
    for fenomeno in ("LLUVIA","VIENTO"):
        for lead in PLAZOS:
            a1=categorizar(valores["GFS"][lead],fenomeno,regiones,rules)
            b1=categorizar(valores["ECMWF"][lead],fenomeno,regiones,rules)
            c,fuente,conf=consenso(a1,b1)
            j=convertir_geojson(g["lat"],g["lon"],c,fuente,conf,pais,
                               fenomeno.lower(),lead,g["run"])
            fname=f"{fenomeno.lower()}_{lead}h.geojson"
            (out/fname).write_text(json.dumps(j,ensure_ascii=False),encoding="utf-8")
            meta["capas"][f"{fenomeno.lower()}_{lead}h"]=fname
            meta["conteos"][f"{fenomeno.lower()}_{lead}h"]={k:int(np.sum(c==i)) for i,k in enumerate(NIVELES)}
            meta["conteos"][f"{fenomeno.lower()}_{lead}h"]["SIN_REGION_O_DATOS"]=int(np.sum((c<0)&dentro))
    # Para el visor: solamente Argentina terrestre y f024/f048/f072.
    # Se conserva grilla real a 0.25° en el dominio evaluado.
    npts=np.count_nonzero(dentro)
    with (out/"grilla_gfs_ecmwf_real.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=COLUMNAS,delimiter=";")
        w.writeheader()
        for model in ("GFS","ECMWF"):
            d=modelos[model]
            for lead in PLAZOS:
                v=valores[model][lead]
                for i,j in np.argwhere(dentro):
                    def fmt(x):return f"{float(x):.3f}" if np.isfinite(x) else ""
                    w.writerow({"model":model,"run_time":g["run"],
                     "valid_time":(datetime.fromisoformat(g["run"].replace("Z","+00:00"))+timedelta(hours=lead)).isoformat().replace("+00:00","Z"),
                     "lead_h":lead,"lat":d["lat"][i],"lon":d["lon"][j],
                     "precip_interval_mm":fmt(v["p24"][i,j]),"precip_window_h":24,
                     "wind_kmh":fmt(v["viento"][i,j]),"gust_kmh":fmt(v["rafaga"][i,j]),
                     "estado":"GRIB_REAL_UMBRAL_PROVISORIO"})
    if npts*6>100000:
        print(f"AVISO: CSV de {npts*6} filas excede visor antiguo; usar GeoJSON solamente")
    (out/"manifest.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"OK: 6 capas GeoJSON, grilla argentina con {npts} celdas por campo, "
          f"{npts*6} filas CSV; NO OPERATIVO")
    print("CONTEOS:",json.dumps(meta["conteos"],ensure_ascii=False))


if __name__=="__main__":
    main()
