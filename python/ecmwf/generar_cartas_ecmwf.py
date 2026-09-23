#!/usr/bin/env python3
import argparse,re
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

CARD_STEPS=[12,24,36,48,60,72,84]
TOP,BOTTOM,LEFT,RIGHT=-20,-80,-95,-25

def open_var(path, short, levtype=None, level=None):
    f={"shortName":short}
    if levtype: f["typeOfLevel"]=levtype
    if level is not None: f["level"]=level
    return xr.open_dataset(path,engine="cfgrib",backend_kwargs={"filter_by_keys":f,"indexpath":""})

def da(ds,names):
    for n,v in ds.data_vars.items():
        short=str(v.attrs.get("GRIB_shortName","")).lower()
        if n.lower() in names or short in names: return v.squeeze(drop=True)
    raise KeyError(names)

def lon180(a):
    if "longitude" in a.coords:
        a=a.assign_coords(longitude=((a.longitude+180)%360)-180).sortby("longitude")
    return a

def base(title):
    proj=ccrs.PlateCarree(); fig,ax=plt.subplots(figsize=(11,9),subplot_kw={"projection":proj})
    ax.set_extent([LEFT,RIGHT,BOTTOM,TOP],crs=proj); ax.set_facecolor("#eef3f7")
    provinces=cfeature.NaturalEarthFeature("cultural","admin_1_states_provinces_lines","10m",facecolor="none")
    ax.add_feature(provinces,edgecolor="#555",linewidth=.45,zorder=5)
    ax.add_feature(cfeature.BORDERS.with_scale("10m"),linewidth=.7,zorder=6)
    ax.add_feature(cfeature.COASTLINE.with_scale("10m"),linewidth=.8,zorder=6)
    gl=ax.gridlines(draw_labels=True,linewidth=.4,linestyle="--",alpha=.5); gl.top_labels=False; gl.right_labels=False
    ax.set_title("Departamento Meteorología Militar\n"+title,fontsize=11,fontweight="bold")
    return fig,ax,proj

def meta(path):
    m=re.search(r"ecmwf_(\d{8})_(\d{2})_f(\d{3})",Path(path).name)
    return (m.group(1),m.group(2),int(m.group(3))) if m else ("????????","??",0)

def sfc(sfcfile,out):
    msl=lon180(da(open_var(sfcfile,"msl"),{"msl","prmsl"}))/100.0
    fig,ax,p=base("ECMWF IFS 0.25° – presión al nivel medio del mar (hPa)")
    cs=ax.contour(msl.longitude,msl.latitude,msl,levels=np.arange(960,1045,3),colors="black",linewidths=.8,transform=p)
    ax.clabel(cs,fmt="%.0f",fontsize=7); fig.savefig(out,dpi=140,bbox_inches="tight"); plt.close(fig)

def h500(plfile,out):
    z=lon180(da(open_var(plfile,"gh","isobaricInhPa",500),{"gh","z"})); zd=z/10 if float(z.max())>1000 else z
    fig,ax,p=base("ECMWF IFS 0.25° – 500 hPa altura geopotencial (dam)")
    lo=int(np.floor(float(zd.min())/6)*6); hi=int(np.ceil(float(zd.max())/6)*6)
    cs=ax.contour(zd.longitude,zd.latitude,zd,levels=np.arange(lo,hi+6,6),colors="black",transform=p)
    ax.clabel(cs,fmt="%.0f",fontsize=7); fig.savefig(out,dpi=140,bbox_inches="tight"); plt.close(fig)

def h200(plfile,out):
    u=lon180(da(open_var(plfile,"u","isobaricInhPa",200),{"u"})); v=lon180(da(open_var(plfile,"v","isobaricInhPa",200),{"v"}))
    speed=np.hypot(u,v)*1.94384
    fig,ax,p=base("ECMWF IFS 0.25° – 200 hPa isotacas y líneas de corriente")
    cf=ax.contourf(u.longitude,u.latitude,speed,levels=[60,80,100,120,140,160,180,200],extend="max",transform=p)
    lat=u.latitude.values; ua=u.values; va=v.values
    if lat[0]>lat[-1]: lat=lat[::-1]; ua=ua[::-1,:]; va=va[::-1,:]
    ax.streamplot(u.longitude.values[::2],lat[::2],ua[::2,::2],va[::2,::2],density=1.4,color="black",linewidth=.6)
    fig.colorbar(cf,ax=ax,shrink=.65,label="kt"); fig.savefig(out,dpi=140,bbox_inches="tight"); plt.close(fig)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",default="ecmwf/gribs"); ap.add_argument("--output",default="salidas_ecmwf")
    a=ap.parse_args(); inp=Path(a.input); out=Path(a.output)
    for step in CARD_STEPS:
        s=next(iter(sorted(inp.glob(f"ecmwf_*_f{step:03d}_sfc.grib2"))),None)
        p=next(iter(sorted(inp.glob(f"ecmwf_*_f{step:03d}_pl.grib2"))),None)
        if not s or not p: print(f"Faltan archivos ECMWF f{step:03d}"); continue
        date,cycle,_=meta(s); baseout=out/date/f"cartas{cycle}"/("cortoplazo" if step<=36 else "largo_plazo")
        for sub in ("superficie","500hPa","200hPa"): (baseout/sub).mkdir(parents=True,exist_ok=True)
        sfc(s,baseout/"superficie"/f"ecmwf_{date}_{cycle}_f{step:03d}_sfc.png")
        h500(p,baseout/"500hPa"/f"ecmwf_{date}_{cycle}_f{step:03d}_500hPa.png")
        h200(p,baseout/"200hPa"/f"ecmwf_{date}_{cycle}_f{step:03d}_200hPa.png")

if __name__=="__main__": main()
