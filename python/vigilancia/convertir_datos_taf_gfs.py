#!/usr/bin/env python3
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--units", default="vigilancia/config/unidades.csv")
    ap.add_argument("--output", required=True)
    a = ap.parse_args()

    df = pd.read_csv(a.input, sep=";")
    units = pd.read_csv(a.units, sep=";")[["nombre", "lat", "lon"]]
    df = df.merge(units, on="nombre", how="left")

    required = ["run_time", "lead_h", "fecha_hora", "wind_kt", "gust_kt", "precip_mm"]
    missing = [x for x in required if x not in df.columns]
    if missing:
        raise SystemExit(f"Faltan columnas en datos_taf para vigilancia: {missing}")

    def num(name):
        return pd.to_numeric(df[name], errors="coerce") if name in df.columns else pd.Series(np.nan, index=df.index)

    out = pd.DataFrame({
        "model": "GFS",
        "run_time": pd.to_datetime(df["run_time"], utc=True, errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "unidad": df["nombre"],
        "lat": num("lat"),
        "lon": num("lon"),
        "valid_time": pd.to_datetime(df["fecha_hora"], utc=True, errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lead_h": num("lead_h"),
        "wind_kmh": num("wind_kt") * 1.852,
        "gust_kmh": num("gust_kt") * 1.852,
        "precip_interval_mm": num("precip_mm"),
        "snow_interval_mm": num("snow_mm"),
        "snow_depth_cm": num("snow_depth_cm"),
        "zonda_hint": "false",
    })

    out = out.dropna(subset=["run_time", "valid_time", "lead_h", "lat", "lon"])
    out["lead_h"] = out["lead_h"].astype(int)
    out = out.sort_values(["unidad", "lead_h"])

    target = Path(a.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(target, sep=";", index=False, float_format="%.3f", na_rep="")
    print(f"OK GFS: {len(out)} registros reutilizados desde {a.input} -> {target}")

if __name__ == "__main__":
    main()
