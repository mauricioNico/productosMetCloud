#!/usr/bin/env python3
"""Fabrica de grillas sinteticas para CI. NO son pronosticos."""
import argparse
import json
from pathlib import Path

import numpy as np


def construir(destino):
    out = Path(destino)
    out.mkdir(parents=True, exist_ok=True)
    # Rectangulo deliberadamente artificial para el smoke test, NO es Argentina.
    mascara = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature", "properties": {"origen": "SINTETICO"},
            "geometry": {"type": "Polygon", "coordinates": [[
                [-69.0, -38.0], [-58.0, -38.0], [-58.0, -25.0],
                [-69.0, -25.0], [-69.0, -38.0]
            ]]}
        }]
    }
    (out / "mascara_ficticia.geojson").write_text(json.dumps(mascara), encoding="utf-8")
    pasos = np.arange(3, 97, 3)
    lats = np.array([-37., -34., -31., -28.])
    lons = np.array([-68., -65., -62., -59.])
    region_lluvia = np.full((4, 4), "PP_R8", dtype="<U12")
    region_viento = np.full((4, 4), "WIND_R2", dtype="<U12")
    for modelo in ("gfs", "ecmwf"):
        lluvia = np.zeros((len(pasos), 4, 4))
        viento = np.full_like(lluvia, 28.)
        rafaga = np.full_like(lluvia, 38.)
        # Intensidades deliberadamente distintas para testear el consenso.
        lluvia[(pasos <= 24), 1, 1] = 28 if modelo == "gfs" else 9
        lluvia[(pasos > 24) & (pasos <= 48), 2, 2] = 20 if modelo == "gfs" else 15
        lluvia[(pasos > 48) & (pasos <= 72), 1, 2] = 12
        viento[(pasos <= 24), 1, 2] = 100 if modelo == "gfs" else 80
        rafaga[(pasos > 24) & (pasos <= 48), 2, 1] = 98
        viento[(pasos > 48) & (pasos <= 72), 2, 3] = 65
        np.savez_compressed(
            out / f"{modelo}.npz",
            steps=pasos, interval_hours=np.full(len(pasos), 3),
            lats=lats, lons=lons, run_time=np.array("2026-10-09T00:00:00Z"),
            precip_interval_mm=lluvia, wind_kmh=viento, gust_kmh=rafaga,
            region_lluvia=region_lluvia, region_viento=region_viento
        )
    print(f"OK: grillas y mascara SINTETICAS -> {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="demo_alertas_web")
    a = p.parse_args()
    construir(a.output)
