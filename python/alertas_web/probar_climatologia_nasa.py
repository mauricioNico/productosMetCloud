#!/usr/bin/env python3
"""Inspección de la respuesta de climatología regional NASA POWER para Argentina.
La prueba no modifica datos meteorológicos, publica solo la descripción HTTP/NetCDF.
"""
from urllib.parse import urlencode
import requests
from pathlib import Path
params={
    "parameters":"T2M",
    "community":"AG",
    "start":1991,
    "end":2020,
    "format":"NetCDF",
}
base="https://power.larc.nasa.gov/api/temporal/climatology/global"
url=base+"?"+urlencode(params)
print("URL:",url,flush=True)
response=requests.get(url,timeout=180)
print("RESPONSE:",response.status_code,response.headers.get("content-type"),len(response.content),response.url,flush=True)
print("HEAD:",repr(response.content[:280]),flush=True)
response.raise_for_status()
p=Path("/tmp/power_t2m_probe.nc")
p.write_bytes(response.content)
import xarray as xr
ds=xr.open_dataset(p)
print("NETCDF:",ds,flush=True)
print("Region Argentina:",ds.T2M.sel(lat=slice(-55,-20),lon=slice(-85,-45)).shape,flush=True)
for k in ds.data_vars: print(k,ds[k].attrs,ds[k].shape,flush=True)
