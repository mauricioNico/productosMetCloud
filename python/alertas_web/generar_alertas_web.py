#!/usr/bin/env python3
"""Generador espacial experimental de lluvia/viento.

Entrada: dos NPZ normalizados, con grillas y regiones previamente delimitadas.
NO interpreta GRIB directamente, NO infiere regiones a partir de estaciones y
NO emite alertas oficiales. Validar las regiones cartograficas antes de operar.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

FENOMENOS = ("lluvia", "viento")
BLOQUES = ((0, 24), (24, 48), (48, 72))
NIVELES = ("VERDE", "AMARILLO", "NARANJA", "ROJO")
PUNTAJE = {"AMARILLO": 1, "NARANJA": 2, "ROJO": 3}
VARIABLES = {
    "lluvia": ("precip_interval_mm",),
    "viento": ("wind_kmh", "gust_kmh"),
}
REGIONES = {"lluvia": "region_lluvia", "viento": "region_viento"}


def leer_umbrales(path):
    reglas = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r["fenomeno"] not in ("LLUVIA", "VIENTO"):
                continue
            fen = r["fenomeno"].lower()
            variable = r["variable"]
            if variable not in VARIABLES[fen]:
                raise ValueError(f"Variable desconocida: {variable}")
            reglas[(fen, r["region"])].append((
                PUNTAJE[r["nivel"]], variable, int(r["ventana_h"]),
                r["operador"], float(r["valor"])))
    if not reglas:
        raise ValueError("Archivo de umbrales vacio")
    return reglas


def cargar_modelo(path):
    with np.load(path, allow_pickle=False) as z:
        oblig = ("steps", "interval_hours", "lats", "lons", "run_time",
                 "precip_interval_mm", "wind_kmh", "gust_kmh",
                 "region_lluvia", "region_viento")
        faltan = set(oblig) - set(z.files)
        if faltan:
            raise ValueError(f"{path}: faltan {sorted(faltan)}")
        d = {k: z[k].copy() for k in oblig}
    d["run_time"] = str(d["run_time"].item())
    steps = d["steps"].astype(float)
    widths = d["interval_hours"].astype(float)
    lats, lons = d["lats"], d["lons"]
    if not (len(steps) and steps.ndim == 1 and np.all(np.diff(steps) > 0)
            and len(steps) == len(widths)
            and np.all(widths > 0) and np.all(widths <= 6)
            and np.allclose(np.r_[0, steps[:-1]], steps - widths)
            and np.max(steps) >= 72):
        raise ValueError(f"{path}: pasos/intervalos incompletos o discontinuos")
    if (lats.ndim != 1 or lons.ndim != 1 or len(lats) < 2 or len(lons) < 2
        or not (np.all(np.diff(lats) > 0) or np.all(np.diff(lats) < 0))
        or not (np.all(np.diff(lons) > 0) or np.all(np.diff(lons) < 0))):
        raise ValueError(f"{path}: ejes geograficos invalidos")
    shp = (len(lats), len(lons))
    for name in ("region_lluvia", "region_viento"):
        if d[name].shape != shp:
            raise ValueError(f"{path}: forma invalida para {name}")
    for name in ("precip_interval_mm", "wind_kmh", "gust_kmh"):
        if d[name].shape != (len(steps), *shp):
            raise ValueError(f"{path}: forma invalida para {name}")
    return d


def agregado_lluvia(modelo, inicio, fin, ventana):
    """Maximo acumulado en cualquier ventana COMPLETA dentro del bloque."""
    pasos = modelo["steps"]
    dur = modelo["interval_hours"]
    lluvia = modelo["precip_interval_mm"]
    sal = np.full(lluvia.shape[1:], np.nan, dtype=float)
    for e in pasos[(pasos >= inicio + ventana) & (pasos <= fin)]:
        seleccion = (pasos > e - ventana) & (pasos <= e)
        indices = np.flatnonzero(seleccion)
        if not len(indices):
            continue
        # Verificamos que cada intervalo encadene exactamente con el anterior.
        if not np.isclose(pasos[indices[0]] - dur[indices[0]], e - ventana):
            continue
        if not np.allclose(pasos[indices], np.r_[pasos[indices[0]] - dur[indices[0]], pasos[indices[:-1]] ] + dur[indices]):
            continue
        bloque = lluvia[indices]
        suma = np.where(np.all(np.isfinite(bloque), axis=0),
                        np.sum(bloque, axis=0), np.nan)
        sal = np.fmax(sal, suma)
    return sal


def agregado_viento(modelo, inicio, fin, variable):
    mask = (modelo["steps"] > inicio) & (modelo["steps"] <= fin)
    valores = modelo[variable][mask]
    if not len(valores):
        return np.full(modelo["region_viento"].shape, np.nan)
    return np.max(np.where(np.isfinite(valores), valores, -np.inf), axis=0).astype(float)


def evaluar(modelo, reglas, fenomeno, inicio, fin):
    regiones = modelo[REGIONES[fenomeno]]
    niveles = np.full(regiones.shape, -1, dtype=np.int8)
    variables = {}
    for reg in np.unique(regiones):
        reglas_reg = reglas.get((fenomeno, str(reg)), [])
        if not reglas_reg:
            continue
        for _, var, ventana, _, _ in reglas_reg:
            if (var, ventana) not in variables:
                if fenomeno == "lluvia":
                    variables[(var, ventana)] = agregado_lluvia(modelo, inicio, fin, ventana)
                else:
                    variables[(var, ventana)] = agregado_viento(modelo, inicio, fin, var)
        rmask = (regiones == reg)
        cobertura = np.zeros(regiones.shape, dtype=bool)
        # Existe cobertura si alguna variable exigida tiene una ventana completa.
        for _, var, ventana, _, _ in reglas_reg:
            cobertura |= np.isfinite(variables[(var, ventana)])
        niveles[rmask & cobertura] = 0
        for nivel, var, ventana, op, umbral in reglas_reg:
            valor = variables[(var, ventana)]
            cumple = valor >= umbral if op == ">=" else valor > umbral if op == ">" else None
            if cumple is None:
                raise ValueError(f"Operador no contemplado: {op}")
            actualizar = rmask & cumple & (niveles >= 0)
            niveles[actualizar] = np.maximum(niveles[actualizar], nivel)
    return niveles


def consenso(gfs, ecmwf):
    """El verde solo indica cobertura evaluada; -1 significa SIN DATOS."""
    res = np.full(gfs.shape, -1, dtype=np.int8)
    fuente = np.full(gfs.shape, "SIN_DATOS", dtype="<U14")
    conf = np.full(gfs.shape, "NO_EVALUADA", dtype="<U12")
    for index in np.ndindex(gfs.shape):
        a, b = int(gfs[index]), int(ecmwf[index])
        if a < 0 and b < 0:
            continue
        if a < 0 or b < 0:
            res[index] = max(a, b)
            fuente[index] = "ECMWF" if a < 0 else "GFS"
            conf[index] = "BAJA"
        elif a == b:
            res[index] = a
            fuente[index] = "CONSENSO"
            conf[index] = "ALTA"
        elif a > 0 and b > 0:
            res[index] = min(a, b)
            fuente[index] = "CONSENSO"
            conf[index] = "MEDIA"
        else:
            res[index] = max(a, b)
            fuente[index] = "ECMWF" if b > a else "GFS"
            conf[index] = "BAJA"
    return res, fuente, conf


def limites_centros(valores):
    arr = np.asarray(valores, dtype=float)
    m = (arr[1:] + arr[:-1]) / 2
    return np.r_[arr[0] - (m[0] - arr[0]), m, arr[-1] + (arr[-1] - m[-1])]


def mascara_geografica(path):
    dato = json.loads(Path(path).read_text(encoding="utf-8"))
    if dato.get("type") == "FeatureCollection":
        geoms = [shape(f["geometry"]) for f in dato["features"] if f.get("geometry")]
        if not geoms:
            raise ValueError("La mascara GeoJSON no tiene geometria")
        pais = unary_union(geoms)
    elif dato.get("type") == "Feature":
        pais = shape(dato["geometry"])
    else:
        pais = shape(dato)
    # Norte y territorio sudamericano/insular, nunca sector antartico.
    pais = pais.intersection(box(-75.5, -56.8, -52, -21))
    if pais.is_empty or not pais.is_valid:
        raise ValueError("Mascara cartografica vacia o invalida")
    return pais


def exportar_capa(modelo, mascara, resultado, fuente, confianza, fen, inicio, fin, simulacion):
    xs = limites_centros(modelo["lons"])
    ys = limites_centros(modelo["lats"])
    grupos = defaultdict(list)
    for (i, j), nivel in np.ndenumerate(resultado):
        if nivel < 0:
            continue
        celda = box(min(xs[j:j+2]), min(ys[i:i+2]), max(xs[j:j+2]), max(ys[i:i+2]))
        if not celda.intersects(mascara):
            continue
        grupos[(int(nivel), str(fuente[i, j]), str(confianza[i, j]))].append(celda)
    features = []
    for (nivel, orig, conf), celdas in grupos.items():
        geom = unary_union(celdas).intersection(mascara)
        if geom.is_empty:
            continue
        props = {
            "fenomeno": fen.upper(), "periodo": f"{fin}h",
            "inicio_h": inicio, "fin_h": fin, "nivel": NIVELES[nivel],
            "fuente": orig, "confianza": conf, "simulacion": simulacion,
        }
        features.append({"type": "Feature", "properties": props, "geometry": mapping(geom)})
    return {"type": "FeatureCollection", "features": features}


def generar(input_gfs, input_ecmwf, mask_geojson, umbrales, output, simulacion=False):
    gfs, ecmwf = cargar_modelo(input_gfs), cargar_modelo(input_ecmwf)
    for campo in ("lats", "lons", "steps", "interval_hours", "region_lluvia", "region_viento"):
        if not np.array_equal(gfs[campo], ecmwf[campo]):
            raise ValueError(f"Grillas/ventanas/regiones incompatibles: {campo}")
    if gfs["run_time"] != ecmwf["run_time"]:
        raise ValueError("Los modelos deben alinearse por hora valida (run_time diferente)")
    reglas = leer_umbrales(umbrales)
    mascara = mascara_geografica(mask_geojson)
    dest = Path(output)
    dest.mkdir(parents=True, exist_ok=True)
    manifest = {
        "producto": "Monitoreo de Eventos Extremos",
        "organismo": "Departamento de Meteorologia Militar",
        "tipo": "VIGILANCIA_NUMERICA",
        "estado": "SIMULACION" if simulacion else "EXPERIMENTAL_NO_PUBLICAR",
        "publicacion_autorizada": False,
        "run_time": gfs["run_time"],
        "generado_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "modelos": ["GFS", "ECMWF"],
        "capas": {},
        "nota": "Salida experimental. Requiere validar regiones, GRIB y umbrales antes de publicacion.",
    }
    for fen in FENOMENOS:
        for inicio, fin in BLOQUES:
            a, b = (evaluar(m, reglas, fen, inicio, fin) for m in (gfs, ecmwf))
            lvl, fuente, conf = consenso(a, b)
            capa = exportar_capa(gfs, mascara, lvl, fuente, conf, fen, inicio, fin, simulacion)
            nombre = f"{fen}_{fin}h.geojson"
            (dest / nombre).write_text(json.dumps(capa, ensure_ascii=False), encoding="utf-8")
            manifest["capas"][f"{fen}_{fin}h"] = nombre
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gfs", required=True, help="Grilla normalizada GFS NPZ")
    p.add_argument("--ecmwf", required=True, help="Grilla normalizada ECMWF NPZ")
    p.add_argument("--mask", required=True, help="GeoJSON de Argentina continental")
    p.add_argument("--thresholds", default="vigilancia/config/umbrales.csv")
    p.add_argument("--output", default="salidas_alertas_web")
    p.add_argument("--simulacion", action="store_true", help="Marcar inequívocamente datos sintéticos")
    a = p.parse_args()
    r = generar(a.gfs, a.ecmwf, a.mask, a.thresholds, a.output, a.simulacion)
    print(f"OK: {len(r['capas'])} capas -> {a.output}; estado={r['estado']}; PUBLICACION BLOQUEADA")


if __name__ == "__main__":
    main()
