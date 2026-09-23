#!/usr/bin/env python3
import argparse
import re
import subprocess
import sys
from pathlib import Path

CARD_STEPS = [12, 24, 36, 48, 60, 72, 84]
HERE = Path(__file__).resolve().parent

def metadata(path):
    m = re.fullmatch(r"ecmwf_(\d{8})_(\d{2})_f(\d{3})\.grib2", path.name)
    if not m:
        raise ValueError(f"Nombre ECMWF no reconocido: {path.name}")
    return m.group(1), m.group(2), int(m.group(3))

def run_script(script, grib, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(HERE / script), str(grib), str(output_dir)]
    print("▶", " ".join(cmd))
    subprocess.run(cmd, check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="ecmwf/gribs")
    ap.add_argument("--output", default="salidas_ecmwf")
    args = ap.parse_args()

    inp = Path(args.input)
    out = Path(args.output)

    for step in CARD_STEPS:
        matches = sorted(inp.glob(f"ecmwf_*_f{step:03d}.grib2"))
        if not matches:
            raise FileNotFoundError(f"Falta GRIB ECMWF unificado f{step:03d}")
        grib = matches[-1]
        date, cycle, _ = metadata(grib)

        plazo = "cortoplazo" if step <= 36 else "largo_plazo"
        baseout = out / date / f"cartas{cycle}" / plazo

        run_script("mapa_superficie_ecmwf_estilo_gfs.py", grib, baseout / "superficie")
        run_script("mapa_500hpa_ecmwf.py", grib, baseout / "500hPa")
        run_script("mapa_200hpa_ecmwf.py", grib, baseout / "200hPa")

if __name__ == "__main__":
    main()
