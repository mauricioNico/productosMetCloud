#!/usr/bin/env python3
import argparse,csv,re
from pathlib import Path
import numpy as np
import pandas as pd
import cfgrib

ALIASES={
    "u10":{"u10","10u","ugrd"},"v10":{"v10","10v","vgrd"},
    "gust":{"gust","10fg","10fg3","10fg6","fg10","gust10m"},"tp":{"tp","apcp"},
    "sf":{"sf","sdwe","weasd"},"sd":{"sd","sde","snow_depth"}
}

def units(path):
    out=[]
    with open(path,encoding="utf-8") as f:
        for row in csv.DictReader(f,delimiter=';'):
            if row.get("activo","true").lower()=="true": out.append(row)
    return out

def normlon(lon, coords):
    vals=np.asarray(coords)
    if vals.max()>180 and lon<0: return lon%360
    return lon

def datasets(path):
    try:return cfgrib.open_datasets(path,backend_kwargs={"indexpath":""})
    except Exception as e:
        print(f"WARN no se pudo abrir {path}: {e}"); return []

def var(dslist,key):
    names=ALIASES[key]
    for ds in dslist:
        for n,da in ds.data_vars.items():
            short=str(da.attrs.get("GRIB_shortName",da.attrs.get("shortName",""))).lower()
            if n.lower() in names or short in names:return da.squeeze(drop=True)
    return None

def point(da,lat,lon):
    if da is None:return np.nan
    try:
        lon2=normlon(lon,da.longitude.values)
        v=da.sel(latitude=lat,longitude=lon2,method="nearest").values
        return float(np.asarray(v).squeeze())
    except Exception:return np.nan

def unitspeed(v,attrs):
    if not np.isfinite(v):return np.nan
    u=str(attrs.get("units","")).lower()
    if "knot" in u or u=="kt":return v*1.852
    return v*3.6

def mm(v,attrs):
    if not np.isfinite(v):return np.nan
    u=str(attrs.get("units","")).lower()
    if u in {"m","metre","meter","metres","meters"}:return v*1000
    return v

def cm(v,attrs):
    if not np.isfinite(v):return np.nan
    u=str(attrs.get("units","")).lower()
    if u in {"m","metre","meter","metres","meters"}:return v*100
    if "mm" in u:return v/10
    return v

def metadata(name):
    m=re.search(r"(?:gfs|ecmwf)_(\d{8})_(\d{2})_f(\d{3})",name)
    if not m:return None
    run=pd.Timestamp(f"{m.group(1)} {m.group(2)}:00",tz="UTC")
    lead=int(m.group(3)); return run,lead,run+pd.Timedelta(hours=lead)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model",required=True,choices=["GFS","ECMWF"])
    ap.add_argument("--input",required=True)
    ap.add_argument("--units",default="vigilancia/config/unidades.csv")
    ap.add_argument("--output",required=True)
    a=ap.parse_args(); us=units(a.units); rows=[]
    files=sorted(Path(a.input).glob("*.grib2"))
    if a.model=="ECMWF": files=[p for p in files if "_sfc." in p.name]
    cumulative={}
    for path in files:
        md=metadata(path.name)
        if not md:continue
        run,lead,valid=md; ds=datasets(path)
        U,V,G,TP,SF,SD=[var(ds,k) for k in ("u10","v10","gust","tp","sf","sd")]
        for u in us:
            lat=float(u["lat"]); lon=float(u["lon"])
            uu=point(U,lat,lon); vv=point(V,lat,lon)
            wind=np.hypot(uu,vv)*3.6 if np.isfinite(uu) and np.isfinite(vv) else np.nan
            gust=unitspeed(point(G,lat,lon),G.attrs if G is not None else {})
            tp=mm(point(TP,lat,lon),TP.attrs if TP is not None else {})
            sf=mm(point(SF,lat,lon),SF.attrs if SF is not None else {})
            sd=cm(point(SD,lat,lon),SD.attrs if SD is not None else {})
            key=(u["nombre"],"tp"); prev=cumulative.get(key,0.0); tpi=max(tp-prev,0) if np.isfinite(tp) else np.nan; cumulative[key]=tp if np.isfinite(tp) else prev
            key=(u["nombre"],"sf"); prev=cumulative.get(key,0.0); sfi=max(sf-prev,0) if np.isfinite(sf) else np.nan; cumulative[key]=sf if np.isfinite(sf) else prev
            rows.append(dict(model=a.model,run_time=run.isoformat().replace('+00:00','Z'),unidad=u["nombre"],lat=lat,lon=lon,
                valid_time=valid.isoformat().replace('+00:00','Z'),lead_h=lead,wind_kmh=wind,gust_kmh=gust,
                precip_interval_mm=tpi,snow_interval_mm=sfi,snow_depth_cm=sd,zonda_hint="false"))
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    cols=["model","run_time","unidad","lat","lon","valid_time","lead_h","wind_kmh","gust_kmh","precip_interval_mm","snow_interval_mm","snow_depth_cm","zonda_hint"]
    pd.DataFrame(rows,columns=cols).sort_values(["unidad","lead_h"]).to_csv(out,sep=';',index=False,float_format='%.3f')
    print(f"OK {a.model}: {len(rows)} registros -> {out}")
if __name__=="__main__":main()
