#!/usr/bin/env python3
"""Descarga reproducible del campo climatológico NASA POWER T2M (1991-2020).

La API limita los rectángulos regionales a 10°; se descargan 16 bloques y se
ensamblan estrictamente en una grilla de 0.5°lat / 0.625°lon WGS84.
No se inventan valores ni se aceptan huecos. Ejecutar solamente al actualizar
la climatología versionada, no en cada corrida del modelo.
"""
from __future__ import annotations
import hashlib
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import requests
import xarray as xr

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"web/monitoreo-extremo/climatologia_t2m_1991_2020.json"
API="https://power.larc.nasa.gov/api/temporal/climatology/regional"
LATS=np.round(np.arange(-55,-20+0.01,0.5),3)
LONS=np.round(np.arange(-85,-45+0.01,0.625),3)
MATRIX=np.full((12,len(LATS),len(LONS)),np.nan,dtype=np.float64)
TILES=[]


def download(south,north,west,east):
    params={
        "latitude-min":south,"latitude-max":north,
        "longitude-min":west,"longitude-max":east,
        "parameters":"T2M","community":"AG",
        "start":1991,"end":2020,"format":"NetCDF"
    }
    last=None
    for attempt in range(4):
        try:
            response=requests.get(API,params=params,timeout=160)
            response.raise_for_status()
            data=response.content
            if not data.startswith(b"\x89HDF"):
                raise ValueError("NASA POWER no devolvió NetCDF4 HDF5")
            return response.url,data
        except (requests.RequestException,ValueError) as exc:
            last=exc
            print("Reintento NASA",south,north,west,east,attempt,str(exc)[:180],flush=True)
            time.sleep(4*(attempt+1))
    raise RuntimeError(f"NASA POWER no pudo entregar climatología: {last}")


def main():
    total=0
    for south in [-55,-45,-35,-25]:
        north=min(-20,south+10)
        for west in [-85,-75,-65,-55]:
            east=min(-45,west+10)
            url,raw=download(south,north,west,east)
            with xr.open_dataset(io.BytesIO(raw),engine="netcdf4") as ds:
                var=ds["T2M"]
                if not str(var.attrs.get("units","")).strip()=="C":
                    raise ValueError(f"Unidades de clima distintas de Celsius: {var.attrs.get('units')}")
                times=np.asarray(ds["time"].values,dtype=int)
                if not np.array_equal(times[:12],np.arange(1,13)):
                    raise ValueError(f"Meses inesperados: {times}")
                for i,lat in enumerate(ds.lat.values):
                    yy=int(round((float(lat)+55)*2))
                    if yy<0 or yy>=len(LATS) or abs(LATS[yy]-lat)>.001:continue
                    for j,lon in enumerate(ds.lon.values):
                        xx=int(round((float(lon)+85)/.625))
                        if xx<0 or xx>=len(LONS) or abs(LONS[xx]-lon)>.001:continue
                        new=np.asarray(var.values[:12,i,j],dtype=float)
                        if np.any(~np.isfinite(new)) or np.any((new < -65)|(new > 58)):
                            raise ValueError(f"NASA POWER devolvió T2M inválida {lat},{lon}: {new}")
                        old=MATRIX[:,yy,xx]
                        if np.any(np.isfinite(old)) and not np.allclose(old,new,atol=.01):
                            raise ValueError(f"Datos incompatibles en borde entre mosaicos {lat},{lon}")
                        MATRIX[:,yy,xx]=new
                        total+=1
            TILES.append({"s":south,"n":north,"w":west,"e":east,
                          "sha256":hashlib.sha256(raw).hexdigest(),"url":url})
            print(f"OK bloque {south}/{north} {west}/{east} (bytes {len(raw)})",flush=True)
    missing=int(np.count_nonzero(~np.isfinite(MATRIX)))
    if missing:raise ValueError(f"Climatología regional incompleta: {missing} celdas mensuales sin datos")
    output={
      "fuente":"NASA POWER climatologia T2M (basada en MERRA-2)",
      "variable":"T2M",
      "unidades":"C",
      "referencia":"1991-2020",
      "tipo":"media mensual climatologica",
      "nota":"Climatologia mensual: interpolar suavemente entre centros de mes; no es una normal diaria observada.",
      "capturado_utc":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
      "lat":LATS.tolist(),"lon":LONS.tolist(),
      "meses":list(range(1,13)),
      "valores":[[[round(float(v),2) for v in line] for line in month] for month in MATRIX],
      "tiles_sha256":TILES,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(output,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    assert len(output["valores"])==12 and len(output["valores"][0])==71 and len(output["valores"][0][0])==65
    print("CLIMATOLOGIA VALIDA",OUT,OUT.stat().st_size,"bytes",total,"muestras ensambladas",flush=True)
    print("RANGO",float(np.nanmin(MATRIX)),float(np.nanmax(MATRIX)),flush=True)


if __name__=="__main__":main()
