"""Anomalías experimentales de T2m contra climatología mensual NASA POWER 1991–2020.

Calcula temperatura media de 24 h estimada a partir de cuatro salidas
instantáneas separadas 6 h de GFS/ECMWF (f006..f072) y resta la normal
climática interpolada en fecha y espacio. Las diferencias entre modelos
y el sesgo frente a MERRA-2 NO están corregidos: no es una alerta ni una
atribución a ENOS. No modifica umbrales de lluvia/viento.
"""
from __future__ import annotations
import json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import numpy as np
from scipy.interpolate import RegularGridInterpolator


def leer_climatologia(path):
    obj=json.loads(Path(path).read_text(encoding="utf-8"))
    if (obj.get("referencia")!="1991-2020" or obj.get("variable")!="T2M"
        or obj.get("unidades")!="C" or len(obj.get("tiles_sha256",[]))!=16):
        raise ValueError("Climatología no corresponde a NASA POWER 1991–2020")
    lat=np.asarray(obj["lat"],dtype=float)
    lon=np.asarray(obj["lon"],dtype=float)
    arr=np.asarray(obj["valores"],dtype=float)
    if (arr.shape!=(12,71,65) or lat.shape!=(71,) or lon.shape!=(65,)
            or not np.all(np.diff(lat)>0) or not np.all(np.diff(lon)>0)
            or not np.all(np.isfinite(arr))):
        raise ValueError("Climatología NASA incompleta/inválida")
    if not (np.isclose(lat[0],-55) and np.isclose(lat[-1],-20)
            and np.isclose(lon[0],-85) and np.isclose(lon[-1],-45)):
        raise ValueError("Dominio climatológico distinto del modelo")
    return lat,lon,arr


def referencias_mensuales(fecha):
    """Meses climatológicos anclados en sus días 15 a las 12 UTC."""
    if fecha.tzinfo is None:
        raise ValueError("La fecha debe incluir zona horaria")
    fecha=fecha.astimezone(timezone.utc)
    this=datetime(fecha.year,fecha.month,15,12,tzinfo=timezone.utc)
    if fecha>=this:
        m1=this
        y,m=(fecha.year+1,1) if fecha.month==12 else (fecha.year,fecha.month+1)
        m2=datetime(y,m,15,12,tzinfo=timezone.utc)
    else:
        m2=this
        y,m=(fecha.year-1,12) if fecha.month==1 else (fecha.year,fecha.month-1)
        m1=datetime(y,m,15,12,tzinfo=timezone.utc)
    frac=(fecha-m1).total_seconds()/(m2-m1).total_seconds()
    return m1.month-1,m2.month-1,float(frac)


def climatologia_en_grilla(ref,lat,lon,fecha):
    lats,lons,normal=ref
    i,j,alpha=referencias_mensuales(fecha)
    monthly=(1-alpha)*normal[i]+alpha*normal[j]
    Y,X=np.meshgrid(np.asarray(lat),np.asarray(lon),indexing="ij")
    points=np.stack([Y.ravel(),X.ravel()],axis=-1)
    interp=RegularGridInterpolator((lats,lons),monthly,bounds_error=False,fill_value=np.nan)
    climate=interp(points).reshape(Y.shape)
    if not np.all(np.isfinite(climate)):
        raise ValueError("La climatología no cubre todos los puntos del modelo")
    return climate


def calcular_anomalias(datos,clim):
    model=datos["model"]
    cube=np.asarray(datos["temp2m_c"],dtype=float)
    if cube.shape[0]!=12 or not np.all(np.isfinite(cube)):
        raise ValueError(f"{model}: faltan pasos f006..f072 de temperatura a 2m")
    if np.nanmin(cube)<-80 or np.nanmax(cube)>65:
        raise ValueError(f"{model}: temperatura física inválida")
    run=datetime.fromisoformat(datos["run"].replace("Z","+00:00"))
    output={}
    for lead in (24,48,72):
        start=(lead-24)//6
        forecast=np.mean(cube[start:start+4],axis=0)
        if forecast.shape!=cube.shape[1:]:raise ValueError("Intervalo térmico incompleto")
        period_midpoint=run+timedelta(hours=lead-12)
        climatology=climatologia_en_grilla(clim,datos["lat"],datos["lon"],period_midpoint)
        anomaly=forecast-climatology
        if np.any(~np.isfinite(anomaly)) or np.nanmax(abs(anomaly))>55:
            raise ValueError("Anomalía térmica no válida")
        output[lead]={"tmean":forecast,"clima":climatology,"anom":anomaly,
                      "fecha_media":period_midpoint.isoformat()}
    return output
