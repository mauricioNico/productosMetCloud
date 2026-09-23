#!/usr/bin/env python3
import argparse
import datetime as dt
from pathlib import Path
from ecmwf.opendata import Client

STEPS=list(range(0,97,3))
CARD_STEPS={12,24,36,48,60,72,84}

def candidates(now):
    base=now.replace(minute=0,second=0,microsecond=0)
    out=[]
    for d in range(0,3):
        day=(base-dt.timedelta(days=d)).date()
        for hour in (12,0):
            t=dt.datetime.combine(day,dt.time(hour),tzinfo=dt.timezone.utc)
            if t<=now: out.append(t)
    return sorted(out, reverse=True)

def retrieve_run(run, outdir):
    client=Client(source="ecmwf", model="ifs", resol="0p25")
    date=run.strftime("%Y%m%d"); time=run.hour
    outdir.mkdir(parents=True,exist_ok=True)
    for step in STEPS:
        target=outdir/f"ecmwf_{date}_{time:02d}_f{step:03d}_sfc.grib2"
        core=["msl","tp","2t","10u","10v","tcc"]
        client.retrieve(date=date,time=time,step=step,type="fc",stream="oper",param=core,target=str(target))
        for optional in ("10fg","sf"):
            extra=outdir/f".extra_{optional}_{step:03d}.grib2"
            try:
                client.retrieve(date=date,time=time,step=step,type="fc",stream="oper",param=optional,target=str(extra))
                if extra.exists() and extra.stat().st_size:
                    with target.open("ab") as dst, extra.open("rb") as src:
                        dst.write(src.read())
            except Exception as exc:
                print(f"WARN {optional} no disponible en f{step:03d}: {exc}")
            finally:
                extra.unlink(missing_ok=True)
        if step in CARD_STEPS:
            ptarget=outdir/f"ecmwf_{date}_{time:02d}_f{step:03d}_pl.grib2"
            client.retrieve(date=date,time=time,step=step,type="fc",stream="oper",
                            levtype="pl",levelist=[200,500,1000],param=["gh","u","v","t"],target=str(ptarget))
    (outdir/"run_metadata.txt").write_text(f"run={run.isoformat()}\n",encoding="utf-8")
    return run

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="ecmwf/gribs")
    args=ap.parse_args()
    now=dt.datetime.now(dt.timezone.utc)
    last=None
    for run in candidates(now):
        try:
            print(f"Probando ECMWF {run:%Y-%m-%d %HZ} con horizonte f096...")
            retrieve_run(run,Path(args.output)); return
        except Exception as exc:
            last=exc
            print(f"No disponible/descarga fallida para {run:%Y-%m-%d %HZ}: {exc}")
            for p in Path(args.output).glob("*.grib2"): p.unlink(missing_ok=True)
    raise SystemExit(f"No se pudo obtener una corrida ECMWF con f096: {last}")

if __name__=="__main__": main()
