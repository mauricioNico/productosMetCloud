#!/usr/bin/env python3
import argparse
import datetime as dt
import shutil
from pathlib import Path
from ecmwf.opendata import Client

STEPS = list(range(0, 97, 3))
CARD_STEPS = {12, 24, 36, 48, 60, 72, 84}

def candidates(now):
    base = now.replace(minute=0, second=0, microsecond=0)
    out = []
    for d in range(0, 3):
        day = (base - dt.timedelta(days=d)).date()
        for hour in (12, 0):
            t = dt.datetime.combine(day, dt.time(hour), tzinfo=dt.timezone.utc)
            if t <= now:
                out.append(t)
    return sorted(out, reverse=True)

def append_file(dst, src):
    if src.exists() and src.stat().st_size:
        with dst.open("ab") as fout, src.open("rb") as fin:
            shutil.copyfileobj(fin, fout)

def retrieve_run(run, outdir):
    client = Client(source="ecmwf", model="ifs", resol="0p25")
    date = run.strftime("%Y%m%d")
    time = run.hour
    outdir.mkdir(parents=True, exist_ok=True)

    for step in STEPS:
        target = outdir / f"ecmwf_{date}_{time:02d}_f{step:03d}.grib2"
        tmp_sfc = outdir / f".sfc_{step:03d}.grib2"
        tmp_pl = outdir / f".pl_{step:03d}.grib2"
        extras = []

        try:
            client.retrieve(
                date=date, time=time, step=step, type="fc", stream="oper",
                param=["msl", "tp", "2t", "10u", "10v", "tcc"],
                target=str(tmp_sfc)
            )
            tmp_sfc.replace(target)

            # Ráfagas: algunas horas de ECMWF Open Data exponen 10fg3
            # en lugar de 10fg. Se prueba primero 10fg y luego 10fg3.
            gust_ok = False
            for gust_param in ("10fg", "10fg3"):
                extra = outdir / f".extra_{gust_param}_{step:03d}.grib2"
                extras.append(extra)
                try:
                    client.retrieve(
                        date=date, time=time, step=step, type="fc", stream="oper",
                        param=gust_param, target=str(extra)
                    )
                    append_file(target, extra)
                    gust_ok = True
                    break
                except Exception:
                    extra.unlink(missing_ok=True)
            if not gust_ok:
                print(f"WARN ráfaga 10fg/10fg3 no disponible en f{step:03d}")

            extra = outdir / f".extra_sf_{step:03d}.grib2"
            extras.append(extra)
            try:
                client.retrieve(
                    date=date, time=time, step=step, type="fc", stream="oper",
                    param="sf", target=str(extra)
                )
                append_file(target, extra)
            except Exception as exc:
                print(f"WARN sf no disponible en f{step:03d}: {exc}")

            if step in CARD_STEPS:
                client.retrieve(
                    date=date, time=time, step=step, type="fc", stream="oper",
                    levtype="pl", levelist=[200, 500, 1000],
                    param=["gh", "u", "v", "t"],
                    target=str(tmp_pl)
                )
                append_file(target, tmp_pl)

            print(f"OK ECMWF f{step:03d}: {target.name}")
        finally:
            tmp_sfc.unlink(missing_ok=True)
            tmp_pl.unlink(missing_ok=True)
            for extra in extras:
                extra.unlink(missing_ok=True)

    (outdir / "run_metadata.txt").write_text(
        f"run={run.isoformat()}\n", encoding="utf-8"
    )
    return run

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="ecmwf/gribs")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    last = None
    for run in candidates(now):
        try:
            print(f"Probando ECMWF {run:%Y-%m-%d %HZ} con horizonte f096...")
            retrieve_run(run, Path(args.output))
            return
        except Exception as exc:
            last = exc
            print(f"No disponible/descarga fallida para {run:%Y-%m-%d %HZ}: {exc}")
            for p in Path(args.output).glob("*.grib2"):
                p.unlink(missing_ok=True)

    raise SystemExit(f"No se pudo obtener una corrida ECMWF con f096: {last}")

if __name__ == "__main__":
    main()
