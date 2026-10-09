#!/usr/bin/env python3
"""PRUEBA DE LABORATORIO: puntos reales GFS/ECMWF para visor, SIN alertas.

GFS: selección de mensajes GRIB por índices de NOAA GFS S3 (HTTP Range).
ECMWF: IFS Open Data. No modifica productos, umbrales ni workflow productivo.
"""
import argparse
import csv
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cfgrib
import numpy as np
import requests

AREA = {"south": -40., "north": -30., "west": -68., "east": -54.}
HORIZONTES = (24, 48, 72)
FIELDS = {
    "u10": ("u10", "10u", "ugrd"),
    "v10": ("v10", "10v", "vgrd"),
    "gust": ("gust", "10fg", "10fg3"),
    "tp": ("tp", "apcp"),
}
CSV_COLS = ("model", "run_time", "valid_time", "lead_h", "lat", "lon",
            "precip_interval_mm", "precip_window_h", "wind_kmh",
            "gust_kmh", "estado")


def run_utc():
    """Mismo ciclo disponible para comparar (mínimo 14 horas de antigüedad)."""
    limit = datetime.now(timezone.utc) - timedelta(hours=14)
    base = limit.replace(hour=0, minute=0, second=0, microsecond=0)
    if (limit - base).total_seconds() >= 12 * 3600:
        base += timedelta(hours=12)
    return base


def get(url, headers=None, timeout=90):
    err = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers or {}, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as exc:
            err = exc
            print(f"ADVERTENCIA: intento {attempt+1}/3: {str(exc)[:170]}", file=sys.stderr)
    raise RuntimeError(f"No se pudo descargar {url}: {err}")


def download_gfs(run, step, target):
    """Descarga 4 mensajes GRIB específicos sin bajar un archivo global."""
    base = (f"https://noaa-gfs-bdp-pds.s3.amazonaws.com/"
            f"gfs.{run:%Y%m%d}/{run:%H}/atmos/"
            f"gfs.t{run:%H}z.pgrb2.0p25.f{step:03d}")
    raw_idx = get(base + ".idx").text
    records = []
    for line in raw_idx.splitlines():
        cols = line.split(":")
        if len(cols) >= 6 and cols[0].isdigit() and cols[1].isdigit():
            records.append({"offset": int(cols[1]), "name": cols[3],
                            "level": cols[4], "forecast": cols[5],
                            "line": line})
    if not records:
        raise ValueError(f"Índice GFS vacío o inesperado f{step:03d}")
    requests_specs = {
        "u10": ("UGRD", "10 m above ground"),
        "v10": ("VGRD", "10 m above ground"),
        "gust": ("GUST", "surface"),
        "tp": ("APCP", "surface"),
    }
    requested = []
    for field, (var, level) in requests_specs.items():
        match = [i for i, rec in enumerate(records)
                 if rec["name"] == var and rec["level"] == level]
        if not match:
            if field == "gust":
                print(f"AVISO GFS: ráfaga no disponible para f{step:03d}")
                continue
            raise ValueError(f"Falta GFS {var}:{level} f{step:03d}")
        if field == "tp":
            # Preferir acumulado 24 h, cuando el mensaje lo identifica.
            match.sort(key=lambda i:
                       (("0-%d hour acc" % step) in records[i]["forecast"],
                        "24 hour acc" in records[i]["forecast"]), reverse=True)
        requested.append((field, match[0]))
    with target.open("wb") as out:
        for field, i in requested:
            start = records[i]["offset"]
            end = records[i+1]["offset"] - 1 if i+1 < len(records) else None
            # Evitar descargar el GRIB entero si el mensaje fuese el último.
            if end is None:
                raise ValueError(f"Último mensaje del índice sin longitud: {field}")
            r = get(base, headers={"Range": f"bytes={start}-{end}"}, timeout=100)
            if r.status_code != 206 or len(r.content) != end-start+1:
                raise ValueError(f"NOAA devolvió rango inválido ({field}, {r.status_code})")
            out.write(r.content)
            print("GFS", step, field, records[i]["forecast"], len(r.content), "bytes")
    return target


def download_ecmwf(run, step, target):
    from ecmwf.opendata import Client
    client = Client(source="ecmwf", model="ifs", resol="0p25")
    kwargs = dict(date=f"{run:%Y%m%d}", time=run.hour, step=step,
                  type="fc", stream="oper")
    client.retrieve(**kwargs, param=["tp", "10u", "10v"], target=str(target))
    # Ráfaga opcional: la disponibilidad depende del ciclo y paso.
    gust_file = target.with_name(target.stem + "_gust.grib2")
    for param in ("10fg", "10fg3"):
        try:
            client.retrieve(**kwargs, param=param, target=str(gust_file))
            with target.open("ab") as f_out, gust_file.open("rb") as f_in:
                import shutil
                shutil.copyfileobj(f_in, f_out)
            print(f"ECMWF f{step:03d} ráfaga desde {param}")
            break
        except Exception as exc:
            print(f"AVISO: ECMWF {param} no disponible en f{step:03d}: {str(exc)[:170]}")
        finally:
            gust_file.unlink(missing_ok=True)
    if not target.exists() or target.stat().st_size < 100:
        raise RuntimeError("ECMWF devolvió GRIB vacío")
    return target


def abrir_campos(path):
    """Abrir todas las agrupaciones para evitar incompatibilidad de stepTypes."""
    datasets = cfgrib.open_datasets(str(path), backend_kwargs={"indexpath": ""})
    encontrados = {}
    for ds in datasets:
        for name, da in ds.data_vars.items():
            aliases = {name.lower(), str(da.attrs.get("GRIB_shortName", "")).lower()}
            for key, opciones in FIELDS.items():
                if key not in encontrados and any(a in opciones for a in aliases):
                    encontrados[key] = da.squeeze(drop=True)
    faltan = {"u10", "v10", "tp"} - set(encontrados)
    if faltan:
        raise ValueError(f"GRIB {path.name}: faltan campos {sorted(faltan)}; presentes {list(encontrados)}")
    return encontrados


def cropped(da):
    if "latitude" not in da.coords or "longitude" not in da.coords:
        raise ValueError("Coordenadas regulares lat/lon no disponibles")
    lats = np.asarray(da.latitude.values).ravel()
    lons = np.asarray(da.longitude.values).ravel()
    signed = (lons + 180) % 360 - 180
    yi = np.flatnonzero((lats >= AREA["south"]) & (lats <= AREA["north"]))
    xi = np.flatnonzero((signed >= AREA["west"]) & (signed <= AREA["east"]))
    if not len(yi) or not len(xi):
        raise ValueError(f"GRIB sin puntos en dominio {AREA}")
    data = np.asarray(da.isel(latitude=yi, longitude=xi).values, dtype=float)
    if data.shape != (len(yi), len(xi)):
        raise ValueError(f"Campo no bidimensional: {data.shape}")
    return lats[yi], signed[xi], data


def periodo_precipitacion(da, step):
    """Nunca atribuir 24 h si el mensaje GRIB no acredita la ventana."""
    meta = str(da.attrs.get("GRIB_stepRange", ""))
    typ = str(da.attrs.get("GRIB_stepType", "")).lower()
    # Ej. 0-24, 18-24, 24 (debe considerarse desconocido si no hay metadato).
    match = re.fullmatch(r"(\d+)-(\d+)", meta)
    hours = int(match.group(2)) - int(match.group(1)) if match else None
    if typ != "accum" or not hours or int(match.group(2)) != step:
        return None, meta, False
    return hours, meta, True


def convertir(model, run, step, path):
    fields = abrir_campos(path)
    lat, lon, u = cropped(fields["u10"])
    _, _, v = cropped(fields["v10"])
    _, _, tp = cropped(fields["tp"])
    if u.shape != v.shape or u.shape != tp.shape:
        raise ValueError(f"{model} f{step}: shape inconsistente")
    wind = np.hypot(u, v) * 3.6  # m/s -> km/h
    wind_units = str(fields["u10"].attrs.get("units", ""))
    if wind_units not in ("m s**-1", "m/s", "m s-1"):
        raise ValueError(f"Unidad del viento desconocida: {wind_units!r}")
    factor = 1000. if str(fields["tp"].attrs.get("units", "")).lower() in (
        "m", "metre", "metres", "meter", "meters") else 1.
    if str(fields["tp"].attrs.get("units", "")) not in (
        "m", "metre", "metres", "meter", "meters", "kg m**-2", "mm"):
        raise ValueError(f"Unidad de precipitación desconocida: {fields['tp'].attrs.get('units')!r}")
    hours, raw_window, valid_tp = periodo_precipitacion(fields["tp"], step)
    precip = tp * factor if valid_tp else None
    gust = None
    if "gust" in fields:
        gy, gx, values = cropped(fields["gust"])
        if np.array_equal(lat, gy) and np.array_equal(lon, gx):
            unit = str(fields["gust"].attrs.get("units", ""))
            if unit in ("m s**-1", "m/s", "m s-1"):
                gust = values * 3.6
            else:
                print(f"AVISO {model} f{step}: unidades ráfaga no reconocidas {unit}")
    meta = {"modelo": model, "f": step, "cantidad_puntos": int(u.size),
            "precip_grib_stepRange": raw_window, "precip_interval_h": hours,
            "precip_validada": bool(valid_tp), "con_rafagas": gust is not None}
    print("CONTROL GRIB:", json.dumps(meta))
    rows = []
    iso_run = run.strftime("%Y-%m-%dT%H:%M:%SZ")
    valid = (run + timedelta(hours=step)).strftime("%Y-%m-%dT%H:%M:%SZ")
    def finite(v):
        return round(float(v), 3) if np.isfinite(v) else ""
    for i, latval in enumerate(lat):
        for j, lonval in enumerate(lon):
            rows.append({
                "model": model, "run_time": iso_run, "valid_time": valid,
                "lead_h": step, "lat": round(float(latval), 3),
                "lon": round(float(lonval), 3),
                "precip_interval_mm": finite(precip[i, j]) if precip is not None else "",
                "precip_window_h": hours if valid_tp else "",
                "wind_kmh": finite(wind[i, j]),
                "gust_kmh": finite(gust[i, j]) if gust is not None else "",
                "estado": "GRIB_REAL_EXPERIMENTAL_NO_ALERTA"
            })
    return rows, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="salidas_grilla_real")
    ap.add_argument("--modelo", choices=["GFS", "ECMWF"], required=True)
    ap.add_argument("--run-utc", help="Corrida YYYYMMDDHH, opcional")
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    run = datetime.strptime(args.run_utc, "%Y%m%d%H").replace(tzinfo=timezone.utc) if args.run_utc else run_utc()
    print(f"CORRIDA PRUEBA {args.modelo} {run.isoformat()}, recorte {AREA}", flush=True)
    rows = []
    metadata = []
    for step in HORIZONTES:
        path = out / f"temporal_{args.modelo.lower()}_{step:03d}.grib2"
        try:
            if args.modelo == "GFS":
                download_gfs(run, step, path)
            else:
                download_ecmwf(run, step, path)
            rec, meta = convertir(args.modelo, run, step, path)
            rows.extend(rec)
            metadata.append(meta)
        finally:
            path.unlink(missing_ok=True)
    file = out / f"grilla_{args.modelo.lower()}_real.csv"
    with file.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS, delimiter=";")
        w.writeheader()
        w.writerows(rows)
    manifest = {
        "estado": "GRIB_REAL_EXPERIMENTAL_NO_ALERTA",
        "advertencia": "Sin niveles de alerta ni consenso; no publicar como vigilancia",
        "modelo": args.modelo, "run_utc": run.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dominio": AREA, "datos": metadata, "csv": file.name,
        "separacion_grilla_grados": 0.25
    }
    (out / f"manifest_{args.modelo.lower()}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if len(metadata) != 3:
        raise RuntimeError("Faltan plazos")
    print(f"OK {args.modelo}: {len(rows)} puntos, {len(metadata)} pronósticos -> {file}")


if __name__ == "__main__":
    main()
