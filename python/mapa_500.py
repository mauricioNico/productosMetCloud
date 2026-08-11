#!/usr/bin/env python
"""Carta GFS de 500 hPa: altura geopotencial y vorticidad relativa."""

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
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap
from matplotlib.ticker import FixedLocator

logging.getLogger("cfgrib").setLevel(logging.ERROR)
logging.getLogger("eccodes").setLevel(logging.ERROR)

RADIO_TIERRA = 6_371_000.0


def abrir(archivo, short_name, nivel=500):
    filtros = {
        "shortName": short_name,
        "typeOfLevel": "isobaricInhPa",
        "level": nivel,
        "stepType": "instant",
    }
    return xr.open_dataset(
        archivo,
        engine="cfgrib",
        backend_kwargs={"filter_by_keys": filtros, "indexpath": ""},
    )


def campo(ds, candidatos):
    candidatos = {c.lower() for c in candidatos}
    for nombre, da in ds.data_vars.items():
        short = str(da.attrs.get("GRIB_shortName", da.attrs.get("shortName", ""))).lower()
        if nombre.lower() in candidatos or short in candidatos:
            return da.squeeze(drop=True)
    raise KeyError(f"No se encontró ninguna variable entre {sorted(candidatos)}")


def recortar(da, top, bottom, left, right):
    lat = da.latitude.values
    tramo_lat = slice(bottom, top) if lat[0] < lat[-1] else slice(top, bottom)
    return da.sel(latitude=tramo_lat, longitude=slice(left, right)).squeeze(drop=True)


def fechas(da):
    def convertir(valor):
        valor = np.asarray(valor).reshape(-1)[0]
        return dt.datetime.fromisoformat(np.datetime_as_string(valor, unit="h"))

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


def vorticidad_relativa(u, v):
    """Calcula zeta sobre esfera: [dv/dlambda - d(u cos(phi))/dphi] / (R cos(phi))."""
    lat_rad = np.deg2rad(u.latitude.values)
    lon_rad = np.deg2rad(u.longitude.values)
    cos_lat = np.cos(lat_rad)[:, None]
    dv_dlambda = np.gradient(v.values, lon_rad, axis=1, edge_order=2)
    ducos_dphi = np.gradient(u.values * cos_lat, lat_rad, axis=0, edge_order=2)
    zeta = (dv_dlambda - ducos_dphi) / (RADIO_TIERRA * cos_lat)
    return xr.DataArray(zeta * 1.0e5, coords=u.coords, dims=u.dims)


def fondo(fig):
    eje = fig.add_axes([0, 0, 1, 1], zorder=-1)
    eje.set_axis_off()
    grad = np.linspace(0, 1, 512).reshape(512, 1)
    cmap = LinearSegmentedColormap.from_list("fondo", ["#6db3f2", "#54a3ee", "#1e69de"])
    eje.imshow(grad, aspect="auto", cmap=cmap, origin="upper", extent=[0, 1, 0, 1])


def main():
    if len(sys.argv) != 7:
        print("Uso: mapa_500.py archivo.grib2 salida.png top bottom left right")
        sys.exit(1)

    archivo = Path(sys.argv[1])
    salida = Path(sys.argv[2])
    top, bottom, left, right = map(float, sys.argv[3:7])
    salida.parent.mkdir(parents=True, exist_ok=True)

    try:
        z = recortar(campo(abrir(archivo, "gh"), {"gh", "z", "hgt"}), top, bottom, left, right)
        u = recortar(campo(abrir(archivo, "u"), {"u", "ugrd"}), top, bottom, left, right)
        v = recortar(campo(abrir(archivo, "v"), {"v", "vgrd"}), top, bottom, left, right)
    except Exception as exc:
        print(f"❌ No se pudieron leer los campos de 500 hPa: {exc}")
        sys.exit(2)

    # GFS entrega altura geopotencial en metros; la carta se expresa en dam.
    z_dam = z / 10.0 if float(z.max()) > 1000 else z
    vort = vorticidad_relativa(u, v)
    inicio, valida, horas = fechas(z)

    proy = ccrs.PlateCarree()
    fig, ax = plt.subplots(figsize=(11.053, 9.053), subplot_kw={"projection": proy})
    fig.subplots_adjust(left=0.025, right=0.89, top=0.91, bottom=0.045)
    fig.patch.set_alpha(0)
    fondo(fig)
    ax.set_facecolor("#f4f2ed")
    ax.set_extent([left, right, bottom, top], crs=proy)

    gl = ax.gridlines(draw_labels=True, linewidth=0.5, color="gray", linestyle="--", alpha=0.55)
    gl.xlocator = FixedLocator(np.arange(left, right + 1, 10))
    gl.ylocator = FixedLocator(np.arange(bottom, top + 1, 10))
    gl.top_labels = gl.right_labels = False
    gl.xlabel_style = gl.ylabel_style = {"size": 7}

    niveles_vort = np.arange(-12, 14, 2)
    colores = ["#08306b", "#08519c", "#2171b5", "#6baed6", "#bdd7e7", "#ffffff",
               "#fee0d2", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15", "#67000d"]
    cmap = LinearSegmentedColormap.from_list("vorticidad", colores, N=len(colores))
    norm = BoundaryNorm(niveles_vort, cmap.N)
    sombreado = ax.contourf(z.longitude, z.latitude, vort, levels=niveles_vort,
                           cmap=cmap, norm=norm, extend="both", transform=proy, zorder=1)

    minimo = int(np.floor(float(z_dam.min()) / 6) * 6)
    maximo = int(np.ceil(float(z_dam.max()) / 6) * 6)
    contornos = ax.contour(z.longitude, z.latitude, z_dam,
                          levels=np.arange(minimo, maximo + 6, 6), colors="black",
                          linewidths=1.0, transform=proy, zorder=5)
    ax.clabel(contornos, inline=True, fontsize=7, fmt="%.0f")

    provincias = cfeature.NaturalEarthFeature("cultural", "admin_1_states_provinces_lines", "10m",
                                               edgecolor="#555555", facecolor="none")
    ax.add_feature(provincias, linewidth=0.4, alpha=0.75, zorder=7)
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), linewidth=0.8, zorder=8)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), linewidth=0.55, zorder=8)

    cax = fig.add_axes([0.91, 0.18, 0.022, 0.58])
    barra = fig.colorbar(sombreado, cax=cax, ticks=niveles_vort)
    barra.set_label("Vorticidad relativa (10⁻⁵ s⁻¹)", fontsize=9)
    barra.ax.tick_params(labelsize=7)

    ciclo = re.search(r"_(\d{2})_f", archivo.name)
    ciclo_txt = f"{ciclo.group(1)}Z" if ciclo else "??Z"
    ax.set_title("Departamento Meteorología Militar\n"
                 "500 hPa: altura geopotencial (dam) y vorticidad relativa\n"
                 f"Inicio: {fecha_es(inicio)} | Validez: {fecha_es(valida)} "
                 f"(H+{horas}, salida {ciclo_txt})", fontsize=11, fontweight="bold", pad=10)

    plt.savefig(salida, dpi=150, bbox_inches="tight", pad_inches=0.02, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"✔ Carta de 500 hPa generada: {salida.resolve()}")


if __name__ == "__main__":
    main()
