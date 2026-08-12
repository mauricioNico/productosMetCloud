#!/usr/bin/env python
"""Carta GFS de 200 hPa: líneas de corriente e isotacas."""

import datetime as dt
import logging
import re
import sys
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.ticker import FixedLocator

logging.getLogger("cfgrib").setLevel(logging.ERROR)
logging.getLogger("eccodes").setLevel(logging.ERROR)


def abrir(archivo, short_name):
    return xr.open_dataset(archivo, engine="cfgrib", backend_kwargs={
        "filter_by_keys": {"shortName": short_name, "typeOfLevel": "isobaricInhPa",
                           "level": 200, "stepType": "instant"},
        "indexpath": "",
    })


def campo(ds, candidatos):
    candidatos = {c.lower() for c in candidatos}
    for nombre, da in ds.data_vars.items():
        short = str(da.attrs.get("GRIB_shortName", da.attrs.get("shortName", ""))).lower()
        if nombre.lower() in candidatos or short in candidatos:
            return da.squeeze(drop=True)
    raise KeyError(f"No se encontró ninguna variable entre {sorted(candidatos)}")


def recortar(da, top, bottom, left, right):
    tramo_lat = slice(bottom, top) if da.latitude.values[0] < da.latitude.values[-1] else slice(top, bottom)
    return da.sel(latitude=tramo_lat, longitude=slice(left, right)).squeeze(drop=True)


def normalizar_longitudes(da):
    """Convierte longitudes GFS 0..360 a -180..180 y las ordena para streamplot."""
    lon = ((da.longitude + 180.0) % 360.0) - 180.0
    return da.assign_coords(longitude=lon).sortby("longitude")


def fechas(da):
    def convertir(valor):
        return dt.datetime.fromisoformat(np.datetime_as_string(np.asarray(valor).reshape(-1)[0], unit="h"))
    inicio = convertir(da.time.values) if "time" in da.coords else None
    valida = convertir(da.valid_time.values) if "valid_time" in da.coords else inicio
    horas = int((valida - inicio).total_seconds() / 3600) if inicio and valida else 0
    return inicio, valida, horas


def fecha_es(valor):
    if valor is None:
        return "N/D"
    dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    return f"{dias[valor.weekday()]} {valor.day:02d} {meses[valor.month - 1]} {valor.year}, {valor:%H} UTC"


def main():
    if len(sys.argv) != 7:
        print("Uso: mapa_200.py archivo.grib2 salida.png top bottom left right")
        sys.exit(1)

    archivo, salida = Path(sys.argv[1]), Path(sys.argv[2])
    top, bottom, left, right = map(float, sys.argv[3:7])
    salida.parent.mkdir(parents=True, exist_ok=True)

    try:
        u = recortar(campo(abrir(archivo, "u"), {"u", "ugrd"}), top, bottom, left, right)
        v = recortar(campo(abrir(archivo, "v"), {"v", "vgrd"}), top, bottom, left, right)
        u = normalizar_longitudes(u)
        v = normalizar_longitudes(v)
    except Exception as exc:
        print(f"❌ No se pudieron leer los campos de viento de 200 hPa: {exc}")
        sys.exit(2)

    velocidad = np.hypot(u, v)  # m/s
    inicio, valida, horas = fechas(u)
    proy = ccrs.PlateCarree()
    fig, ax = plt.subplots(figsize=(11.053, 9.053), subplot_kw={"projection": proy})
    fig.subplots_adjust(left=0.025, right=0.89, top=0.91, bottom=0.045)
    ax.set_facecolor("#f7f7f5")
    left_mapa = ((left + 180.0) % 360.0) - 180.0
    right_mapa = ((right + 180.0) % 360.0) - 180.0
    ax.set_extent([left_mapa, right_mapa, bottom, top], crs=proy)

    gl = ax.gridlines(draw_labels=True, linewidth=0.5, color="gray", linestyle="--", alpha=0.55)
    gl.xlocator = FixedLocator(np.arange(left_mapa, right_mapa + 1, 10))
    gl.ylocator = FixedLocator(np.arange(bottom, top + 1, 10))
    gl.top_labels = gl.right_labels = False
    gl.xlabel_style = gl.ylabel_style = {"size": 7}

    niveles = [30, 40, 50, 60, 70, 80, 90, 100]
    cmap = ListedColormap(["#d9f0f3", "#a6dcef", "#62bde5", "#2595cf",
                           "#116fb5", "#084b8a", "#3f1b78"])
    norm = BoundaryNorm(niveles, cmap.N)
    isotacas = ax.contourf(u.longitude, u.latitude, velocidad, levels=niveles,
                          cmap=cmap, norm=norm, extend="max", transform=proy, zorder=1)

    # streamplot necesita ejes crecientes; el GFS suele entregar latitudes decrecientes.
    lat = u.latitude.values
    u_arr, v_arr = u.values, v.values
    if lat[0] > lat[-1]:
        lat, u_arr, v_arr = lat[::-1], u_arr[::-1, :], v_arr[::-1, :]
    paso = 2
    corrientes = ax.streamplot(
        u.longitude.values[::paso],
        lat[::paso],
        u_arr[::paso, ::paso],
        v_arr[::paso, ::paso],
        density=1.6,
        color="#171717",
        linewidth=0.75,
        arrowsize=0.9,
        arrowstyle="->",
        minlength=0.15,
        maxlength=4.0,
        zorder=6,
    )
    # Refuerza el orden de dibujo en distintas versiones de Matplotlib/Cartopy.
    corrientes.lines.set_zorder(6)
    corrientes.arrows.set_zorder(6)

    provincias = cfeature.NaturalEarthFeature("cultural", "admin_1_states_provinces_lines", "10m",
                                               edgecolor="#555555", facecolor="none")
    ax.add_feature(provincias, linewidth=0.4, alpha=0.75, zorder=7)
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), linewidth=0.8, zorder=8)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), linewidth=0.55, zorder=8)

    cax = fig.add_axes([0.91, 0.18, 0.022, 0.58])
    barra = fig.colorbar(isotacas, cax=cax, ticks=niveles)
    barra.set_label("Velocidad del viento en 200 hPa (m/s)", fontsize=9)
    barra.ax.tick_params(labelsize=7)

    ciclo = re.search(r"_(\d{2})_f", archivo.name)
    ciclo_txt = f"{ciclo.group(1)}Z" if ciclo else "??Z"
    ax.set_title("Departamento Meteorología Militar\n"
                 "200 hPa: líneas de corriente e isotacas (corriente en chorro)\n"
                 f"Inicio: {fecha_es(inicio)} | Validez: {fecha_es(valida)} "
                 f"(H+{horas}, salida {ciclo_txt})", fontsize=11, fontweight="bold", pad=10)

    # No usar bbox_inches="tight" en este GeoAxes: al combinar longitudes
    # normalizadas y streamplot puede recortar el mapa y dejar solo la colorbar.
    plt.savefig(
        salida,
        dpi=150,
        facecolor=fig.get_facecolor(),
        edgecolor="none",
    )
    plt.close(fig)
    print(f"✔ Carta de 200 hPa generada: {salida.resolve()}")


if __name__ == "__main__":
    main()
