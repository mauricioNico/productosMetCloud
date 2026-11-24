import argparse, datetime as dt, json, tempfile
from pathlib import Path
import numpy as np
import xarray as xr
import requests
from ecmwf.opendata import Client
from indice import LATS,LONS,diagnose

def field(path,run,step):
    with xr.open_dataset(path,engine="cfgrib",backend_kwargs={"indexpath":"","filter_by_keys":{"typeOfLevel":"isobaricInhPa","level":500}}) as ds:
        a=ds["gh"] if "gh" in ds else ds["z"]
        units=a.attrs.get("units","")
        if units in ("m**2 s**-2","m2 s-2","m^2 s^-2"): a=a/9.80665
        elif units not in ("m","gpm"): raise ValueError("Unidades desconocidas: "+units)
        if np.datetime64(run.replace(tzinfo=None)) != ds.time.values or np.timedelta64(step,"h") != ds.step.values:
            raise ValueError("Fecha o plazo incorrecto")
        a=a.assign_coords(longitude=(a.longitude+180)%360-180).sortby("longitude")
        return a.sel(latitude=-LATS,longitude=LONS).transpose("latitude","longitude").values

def download(model,run,step,p):
    if model=="ECMWF":
        Client(source="ecmwf",model="ifs",resol="0p25").retrieve(date=run.strftime("%Y%m%d"),time=run.hour,step=step,type="fc",stream="oper",levtype="pl",levelist=500,param="gh",target=str(p))
    else:
        filename=f"gfs.t{run.hour:02d}z.pgrb2.0p25.f{step:03d}"
        q=dict(file=filename,lev_500_mb="on",var_HGT="on",subregion="",leftlon=0,rightlon=360,toplat=-30,bottomlat=-65,dir=f"/gfs.{run:%Y%m%d}/{run.hour:02d}/atmos")
        with requests.get("https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl",params=q,timeout=120,stream=True) as response:
            response.raise_for_status()
            with p.open("wb") as f:
                for chunk in response.iter_content(65536): f.write(chunk)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run",required=True)
    p.add_argument("--model",choices=["GFS","ECMWF"],required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--hours",type=int,default=120)
    args=p.parse_args()
    run=dt.datetime.strptime(args.run,"%Y%m%d%H").replace(tzinfo=dt.timezone.utc)
    if run.hour not in (0,12) or args.hours not in (24,120,240): raise ValueError("Corrida/plazo no admitido")
    fields={}; errors={}
    with tempfile.TemporaryDirectory() as tmp:
        for step in range(0,args.hours+1,6):
            path=Path(tmp)/"z.grib"
            try:
                download(args.model,run,step,path)
                fields[step]=field(path,run,step)
                print("OK",step,flush=True)
            except Exception as e:
                errors[str(step)]=str(e); print("ERROR",step,e,flush=True)
            finally: path.unlink(missing_ok=True)
    if not fields: raise RuntimeError("No se pudo obtener Z500")
    inst=[dict(step=s,valid=(run+dt.timedelta(hours=s)).isoformat(),**diagnose(z)) for s,z in fields.items()]
    daily=[]; streak={}
    for day in sorted({(run+dt.timedelta(hours=s)).date() for s in range(0,args.hours+1,6)}):
        steps=[int((dt.datetime.combine(day,dt.time(h),tzinfo=dt.timezone.utc)-run).total_seconds()/3600) for h in (0,6,12,18)]
        if not all(s in fields for s in steps):
            daily.append(dict(date=str(day),status="incomplete")); streak={}; continue
        result=diagnose(np.mean([fields[s] for s in steps],axis=0))
        streak={k:streak.get(k,0)+1 if v else 0 for k,v in result["sectors"].items()}
        daily.append(dict(date=str(day),status="forecast",streak=streak.copy(),**result))
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(dict(model=args.model,run=run.isoformat(),instant=inst,daily=daily,errors=errors),allow_nan=False),encoding="utf-8")
if __name__=="__main__": main()
