# -*- coding: utf-8 -*-
"""
ECMWF IFS 0.25° - Departamento Meteorología Militar 

Uso:
    python SCRIPT.py archivo.grib2 carpeta_salida

Base cartográfica:
- Natural Earth 10m
- límites internacionales
- provincias/estados (admin_1)
- ríos y lagos principales
"""

import os
import sys
import warnings
from pathlib import Path

import cfgrib
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------
# DOMINIO
# ECMWF usa longitudes 0..360
# 250E = 110W ; 340E = 20W
# ---------------------------------------------------------
NORTE = -20
SUR = -85
OESTE = 250
ESTE = 340

COLOR_FONDO_FIG = "#347ccc"
COLOR_TIERRA = "#d8c5b2"
COLOR_OCEANO = "#a8bfd8"
COLOR_LIMITE_INTERNO = "#555555"
COLOR_RIOS = "#56788d"


def abrir_grib(archivo):
    return cfgrib.open_datasets(
        archivo,
        backend_kwargs={"indexpath": ""}
    )


def buscar_dataset(datasets, variable=None, coord=None):
    for ds in datasets:
        if variable is not None and variable not in ds.data_vars:
            continue
        if coord is not None and coord not in ds.coords:
            continue
        return ds
    return None


def agregar_base_cartografica(ax):
    ax.set_extent(
        [OESTE, ESTE, SUR, NORTE],
        crs=ccrs.PlateCarree()
    )

    ax.set_facecolor(COLOR_OCEANO)

    ax.add_feature(
        cfeature.LAND.with_scale("10m"),
        facecolor=COLOR_TIERRA,
        edgecolor="none",
        zorder=0
    )

    ax.add_feature(
        cfeature.OCEAN.with_scale("10m"),
        facecolor=COLOR_OCEANO,
        edgecolor="none",
        zorder=0
    )

    ax.add_feature(
        cfeature.LAKES.with_scale("10m"),
        facecolor=COLOR_OCEANO,
        edgecolor="#555555",
        linewidth=0.35,
        zorder=4
    )

    rios = cfeature.NaturalEarthFeature(
        category="physical",
        name="rivers_lake_centerlines",
        scale="10m",
        facecolor="none"
    )

    ax.add_feature(
        rios,
        edgecolor=COLOR_RIOS,
        linewidth=0.28,
        alpha=0.65,
        zorder=4.5
    )

    provincias = cfeature.NaturalEarthFeature(
        category="cultural",
        name="admin_1_states_provinces_lines",
        scale="10m",
        facecolor="none"
    )

    ax.add_feature(
        provincias,
        edgecolor=COLOR_LIMITE_INTERNO,
        linewidth=0.45,
        linestyle="-",
        zorder=5.5
    )

    ax.add_feature(
        cfeature.BORDERS.with_scale("10m"),
        edgecolor="#333333",
        linewidth=0.65,
        zorder=6
    )

    ax.add_feature(
        cfeature.COASTLINE.with_scale("10m"),
        edgecolor="black",
        linewidth=0.80,
        zorder=6
    )

    gl = ax.gridlines(
        draw_labels=True,
        linewidth=0.35,
        linestyle="--",
        alpha=0.42,
        x_inline=False,
        y_inline=False,
        zorder=3
    )

    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {"size": 8}
    gl.ylabel_style = {"size": 8}


def tiempo_textos(ds):
    inicio = np.datetime_as_string(
        ds["time"].values,
        unit="h"
    )

    valido = np.datetime_as_string(
        ds["valid_time"].values,
        unit="h"
    )

    paso = int(
        ds["step"].values / np.timedelta64(1, "h")
    )

    salida_z = str(inicio)[11:13]

    return inicio, valido, paso, salida_z


def preparar_salida(
    archivo,
    carpeta_salida,
    sufijo
):
    carpeta = Path(carpeta_salida)
    carpeta.mkdir(
        parents=True,
        exist_ok=True
    )

    base = Path(archivo).stem

    return carpeta / f"{base}_{sufijo}.png"


def main():

    if len(sys.argv) < 3:
        print(
            "Uso: python mapa_500hpa_ecmwf.py "
            "archivo.grib2 carpeta_salida"
        )
        sys.exit(1)

    archivo = sys.argv[1]
    carpeta_salida = sys.argv[2]

    if not os.path.exists(archivo):
        raise FileNotFoundError(
            f"No existe: {archivo}"
        )

    datasets = abrir_grib(archivo)

    ds_pl = buscar_dataset(
        datasets,
        variable="gh",
        coord="isobaricInhPa"
    )

    if ds_pl is None:
        raise RuntimeError(
            "No se encontró dataset isobárico con gh."
        )

    gh = ds_pl["gh"].sel(
        isobaricInhPa=500
    )

    u = ds_pl["u"].sel(
        isobaricInhPa=500
    )

    v = ds_pl["v"].sel(
        isobaricInhPa=500
    )

    lat = ds_pl["latitude"]
    lon = ds_pl["longitude"]

    gh_dam = gh / 10.0

    vel_kt = (
        np.sqrt(
            u**2 + v**2
        )
        * 1.94384
    )

    # -----------------------------------------------------
    # FIGURA
    # Ajuste manual para acercar el mapa al título
    # -----------------------------------------------------

    fig = plt.figure(
        figsize=(14, 11),
        facecolor=COLOR_FONDO_FIG
    )

    ax = fig.add_axes(
        [0.055, 0.08, 0.83, 0.80],
        projection=ccrs.PlateCarree()
    )

    agregar_base_cartografica(ax)

    # -----------------------------------------------------
    # VELOCIDAD DEL VIENTO
    # -----------------------------------------------------

    niveles_v = [
        30, 40, 50, 60, 70,
        80, 90, 100, 120, 140
    ]

    colores_v = [
        "#e5f5ff",
        "#c6e9ff",
        "#9dd9ff",
        "#71c4ff",
        "#4ba7ff",
        "#4a80ff",
        "#6b67ff",
        "#8b58dc",
        "#a34fb8"
    ]

    cmap_v = mcolors.ListedColormap(
        colores_v
    )

    norm_v = mcolors.BoundaryNorm(
        niveles_v,
        cmap_v.N
    )

    cf_v = ax.contourf(
        lon,
        lat,
        vel_kt,
        levels=niveles_v,
        cmap=cmap_v,
        norm=norm_v,
        extend="max",
        alpha=0.80,
        transform=ccrs.PlateCarree(),
        zorder=2
    )

    # -----------------------------------------------------
    # ALTURA GEOPOTENCIAL
    # -----------------------------------------------------

    hmin = (
        np.floor(
            float(gh_dam.min()) / 6
        ) * 6
    )

    hmax = (
        np.ceil(
            float(gh_dam.max()) / 6
        ) * 6
    )

    niveles_gh = np.arange(
        hmin,
        hmax + 6,
        6
    )

    c_gh = ax.contour(
        lon,
        lat,
        gh_dam,
        levels=niveles_gh,
        colors="black",
        linewidths=1.0,
        transform=ccrs.PlateCarree(),
        zorder=8
    )

    ax.clabel(
        c_gh,
        fontsize=8,
        fmt="%d",
        inline=True
    )

    # -----------------------------------------------------
    # BARBAS
    # -----------------------------------------------------

    stride = 8

    ax.barbs(
        lon.values[::stride],
        lat.values[::stride],
        u.values[::stride, ::stride]
        * 1.94384,
        v.values[::stride, ::stride]
        * 1.94384,
        length=4.8,
        linewidth=0.43,
        pivot="middle",
        color="black",
        transform=ccrs.PlateCarree(),
        zorder=10
    )

    # -----------------------------------------------------
    # TÍTULOS
    # -----------------------------------------------------

    inicio, valido, paso, salida_z = tiempo_textos(
        ds_pl
    )

    fig.suptitle(
        "Departamento Meteorología Militar - MODELO ECMWF IFS 0.25°",
        fontsize=16,
        fontweight="bold",
        y=0.955
    )

    ax.set_title(
        "500 hPa - Altura geopotencial y viento\n"
        f"Inicio: {inicio} UTC   |   "
        f"Validez: {valido} UTC   "
        f"(H+{paso:02d}, salida {salida_z}Z)",
        fontsize=11.5,
        fontweight="bold",
        pad=6
    )

    # -----------------------------------------------------
    # BARRA DE COLOR
    # -----------------------------------------------------

    cax = fig.add_axes(
        [0.905, 0.29, 0.020, 0.46]
    )

    cb = plt.colorbar(
        cf_v,
        cax=cax
    )

    cb.set_label(
        "Velocidad del viento (kt)",
        fontsize=10
    )

    cb.ax.tick_params(
        labelsize=8
    )

    # -----------------------------------------------------
    # GUARDAR
    # -----------------------------------------------------

    salida = preparar_salida(
        archivo,
        carpeta_salida,
        "500hPa"
    )

    plt.savefig(
        salida,
        dpi=200,
        facecolor=fig.get_facecolor()
    )

    plt.close()

    print(
        f"Mapa 500 hPa generado: "
        f"{salida.resolve()}"
    )


if __name__ == "__main__":
    main()