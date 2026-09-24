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
import re
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



def obtener_precipitacion_12h(archivo_actual, ds_tp_actual, paso):
    """
    Calcula la precipitación acumulada de las 12 horas inmediatamente
    anteriores al paso actual.

    f012 -> tp(f012), acumulado 0-12 h
    f024 -> tp(f024) - tp(f012)
    f036 -> tp(f036) - tp(f024)
    ...
    f084 -> tp(f084) - tp(f072)
    """

    if ds_tp_actual is None:
        return None

    tp_actual = ds_tp_actual["tp"]

    if paso <= 12:
        print("Precipitación: H+012 (acumulado 0-12 h)")
        return (tp_actual * 1000.0).clip(min=0)

    ruta_actual = Path(archivo_actual)

    match = re.match(
        r"^(.*_f)(\d{3})(\.grib2)$",
        ruta_actual.name
    )

    if not match:
        raise RuntimeError(
            "No se pudo interpretar el nombre del GRIB para calcular "
            "la precipitación de 12 h. Se esperaba un nombre como "
            "ifs_20260914_06_f084.grib2"
        )

    paso_anterior = paso - 12

    nombre_anterior = (
        f"{match.group(1)}{paso_anterior:03d}{match.group(3)}"
    )

    archivo_anterior = ruta_actual.with_name(nombre_anterior)

    if not archivo_anterior.exists():
        raise FileNotFoundError(
            "Falta el GRIB anterior necesario para calcular "
            f"la precipitación de 12 h: {archivo_anterior}"
        )

    datasets_prev = abrir_grib(str(archivo_anterior))

    ds_tp_prev = buscar_dataset(
        datasets_prev,
        variable="tp"
    )

    if ds_tp_prev is None:
        raise RuntimeError(
            f"El GRIB anterior {archivo_anterior.name} no contiene tp."
        )

    tp_prev = ds_tp_prev["tp"]

    tp_12h_mm = (
        (tp_actual - tp_prev)
        * 1000.0
    ).clip(min=0)

    print(
        f"Precipitación: H+{paso:03d} - H+{paso_anterior:03d} "
        f"(acumulado 12 h)"
    )

    return tp_12h_mm

def main():

    if len(sys.argv) < 3:
        print(
            "Uso: python mapa_superficie_ecmwf_estilo_gfs.py "
            "archivo.grib2 carpeta_salida"
        )
        sys.exit(1)

    archivo = sys.argv[1]
    carpeta_salida = sys.argv[2]

    if not os.path.exists(archivo):
        raise FileNotFoundError(
            f"No existe: {archivo}"
        )

    print(f"Leyendo: {archivo}")

    datasets = abrir_grib(archivo)

    ds_pl = buscar_dataset(
        datasets,
        variable="gh",
        coord="isobaricInhPa"
    )

    ds_msl = buscar_dataset(
        datasets,
        variable="msl"
    )

    ds_tp = buscar_dataset(
        datasets,
        variable="tp"
    )

    ds_10m = buscar_dataset(
        datasets,
        variable="u10"
    )

    ds_t2m = buscar_dataset(
        datasets,
        variable="t2m"
    )

    ds_tcc = buscar_dataset(
        datasets,
        variable="tcc"
    )

    if ds_pl is None:
        raise RuntimeError(
            "No se encontró gh en niveles isobáricos."
        )

    if ds_msl is None:
        raise RuntimeError(
            "No se encontró msl."
        )

    # -----------------------------------------------------
    # CAMPOS
    # -----------------------------------------------------

    gh1000 = ds_pl["gh"].sel(
        isobaricInhPa=1000
    )

    gh500 = ds_pl["gh"].sel(
        isobaricInhPa=500
    )

    # Espesor en decámetros
    espesor = (
        gh500 - gh1000
    ) / 10.0

    # Pa -> hPa
    mslp = (
        ds_msl["msl"]
        / 100.0
    )

    lat = ds_msl["latitude"]
    lon = ds_msl["longitude"]

    # Paso de pronóstico en horas. Se utiliza también para calcular
    # la precipitación del intervalo anterior de 12 h.
    paso = int(
        ds_msl["step"].values / np.timedelta64(1, "h")
    )

    # ECMWF tp es acumulado desde el inicio del pronóstico.
    # Para estas cartas se representa el acumulado de las 12 h
    # inmediatamente anteriores: f024-f012, f036-f024, ..., f084-f072.
    # En f012 se usa directamente el acumulado 0-12 h.
    tp_mm = obtener_precipitacion_12h(
        archivo,
        ds_tp,
        paso
    )

    # Viento 10 m
    u10 = None
    v10 = None

    if (
        ds_10m is not None
        and "v10" in ds_10m.data_vars
    ):
        u10 = ds_10m["u10"]
        v10 = ds_10m["v10"]

    # Temperatura 2 m
    t2m_c = None

    if ds_t2m is not None:
        t2m_c = (
            ds_t2m["t2m"]
            - 273.15
        )

    # Nubosidad total
    tcc_pct = None

    if ds_tcc is not None:

        tcc_pct = ds_tcc["tcc"]

        if float(tcc_pct.max()) <= 1.5:
            tcc_pct = tcc_pct * 100.0

    # Aproximación sencilla de nieve:
    # precipitación de las últimas 12 h >= 0.2 mm y T2m <= 0 °C
    snow_mask = None

    if (
        tp_mm is not None
        and t2m_c is not None
    ):

        snow_mask = np.where(
            (tp_mm >= 0.2)
            & (t2m_c <= 0.0),
            1.0,
            np.nan
        )

    # -----------------------------------------------------
    # FIGURA
    # Ajuste manual para eliminar espacio excesivo arriba
    # -----------------------------------------------------

    fig = plt.figure(
        figsize=(14, 11),
        facecolor=COLOR_FONDO_FIG
    )

    ax = fig.add_axes(
        [0.055, 0.075, 0.83, 0.84],
        projection=ccrs.PlateCarree()
    )

    agregar_base_cartografica(ax)

    # -----------------------------------------------------
    # NUBOSIDAD
    # -----------------------------------------------------

    cf_nub = None

    if tcc_pct is not None:

        niveles_nub = [
            40, 50, 60, 70,
            80, 90, 100
        ]

        cf_nub = ax.contourf(
            lon,
            lat,
            tcc_pct,
            levels=niveles_nub,
            cmap="Greys",
            alpha=0.35,
            extend="max",
            transform=ccrs.PlateCarree(),
            zorder=1
        )

    # -----------------------------------------------------
    # PRECIPITACIÓN
    # -----------------------------------------------------

    cf_pp = None

    if tp_mm is not None:

        niveles_pp = [
            0.2, 0.5, 1, 2, 3,
            4, 5, 10, 15, 20,
            25, 35, 45, 50,
            70, 80, 100, 120, 150
        ]

        colores_pp = [
            "#d9f0ff", "#bdefff", "#8de0ff",
            "#5fc4ff", "#3b8cff",
            "#4666ff", "#6a5cff", "#8c5eff",
            "#a96dd8", "#c97fd8",
            "#dd88cc", "#e885b6", "#f07c9d",
            "#f06a82", "#ee5959",
            "#d96b6b", "#b78484", "#9c8c95"
        ]

        cmap_pp = mcolors.ListedColormap(
            colores_pp
        )

        norm_pp = mcolors.BoundaryNorm(
            niveles_pp,
            cmap_pp.N
        )

        cf_pp = ax.contourf(
            lon,
            lat,
            tp_mm,
            levels=niveles_pp,
            cmap=cmap_pp,
            norm=norm_pp,
            extend="max",
            alpha=0.92,
            transform=ccrs.PlateCarree(),
            zorder=2
        )

    # -----------------------------------------------------
    # ÁREAS CON NIEVE
    # -----------------------------------------------------

    if (
        snow_mask is not None
        and np.isfinite(snow_mask).any()
    ):

        cont_nieve = ax.contour(
            lon,
            lat,
            snow_mask,
            levels=[0.5],
            colors="#cf7d00",
            linewidths=1.10,
            transform=ccrs.PlateCarree(),
            zorder=6.5
        )

        try:
            ax.clabel(
                cont_nieve,
                fmt={0.5: "NIEVE"},
                fontsize=7,
                inline=True,
                colors="#b56d00"
            )
        except Exception:
            pass

    # -----------------------------------------------------
    # ESPESOR 1000/500
    # -----------------------------------------------------

    niveles_esp = np.arange(
        480,
        606,
        6
    )

    especiales = {
        528: "yellow",
        540: "blue",
        550: "green",
        570: "red"
    }

    negros = [
        x
        for x in niveles_esp
        if x not in especiales
    ]

    c_esp = ax.contour(
        lon,
        lat,
        espesor,
        levels=negros,
        colors="black",
        linewidths=0.65,
        linestyles="dashed",
        transform=ccrs.PlateCarree(),
        zorder=7
    )

    ax.clabel(
        c_esp,
        fontsize=7,
        fmt="%d",
        inline=True
    )

    for nivel, color in especiales.items():

        c = ax.contour(
            lon,
            lat,
            espesor,
            levels=[nivel],
            colors=color,
            linewidths=1.8,
            transform=ccrs.PlateCarree(),
            zorder=8
        )

        ax.clabel(
            c,
            fontsize=8,
            fmt="%d",
            inline=True
        )

    # -----------------------------------------------------
    # PRESIÓN NIVEL MEDIO DEL MAR cada 3 hPa
    # -----------------------------------------------------

    pmin = (
        np.floor(
            float(mslp.min()) / 3
        ) * 3
    )

    pmax = (
        np.ceil(
            float(mslp.max()) / 3
        ) * 3
    )

    niveles_presion = np.arange(
        pmin,
        pmax + 3,
        3
    )

    c_p = ax.contour(
        lon,
        lat,
        mslp,
        levels=niveles_presion,
        colors="black",
        linewidths=0.95,
        transform=ccrs.PlateCarree(),
        zorder=9
    )

    ax.clabel(
        c_p,
        fontsize=7.5,
        fmt="%d",
        inline=True
    )

    # -----------------------------------------------------
    # BARBAS DE VIENTO
    # -----------------------------------------------------

    if (
        u10 is not None
        and v10 is not None
    ):

        stride = 8

        ax.barbs(
            lon.values[::stride],
            lat.values[::stride],
            u10.values[::stride, ::stride]
            * 1.94384,
            v10.values[::stride, ::stride]
            * 1.94384,
            length=4.7,
            linewidth=0.42,
            pivot="middle",
            color="black",
            transform=ccrs.PlateCarree(),
            zorder=10
        )

    # -----------------------------------------------------
    # TÍTULOS
    # -----------------------------------------------------

    inicio, valido, paso, salida_z = tiempo_textos(
        ds_msl
    )

    fig.suptitle(
        "Departamento Meteorología Militar - MODELO ECMWF IFS 0.25°",
        fontsize=16,
        fontweight="bold",
        y=0.955
    )

    partes = [
        "Superficie y espesores",
        "precipitación 12 h",
        "viento fuerte"
    ]

    if tcc_pct is not None:
        partes.append(
            "cielo cubierto"
        )

    if snow_mask is not None:
        partes.append(
            "áreas con nieve"
        )

    if len(partes) > 1:
        titulo_producto = (
            ", ".join(partes[:-1])
            + " y "
            + partes[-1]
        )
    else:
        titulo_producto = partes[0]

    ax.set_title(
        titulo_producto
        + "\n"
        + f"Inicio: {inicio} UTC   |   "
          f"Validez: {valido} UTC   "
          f"(H+{paso:02d}, salida {salida_z}Z)",
        fontsize=11.5,
        fontweight="bold",
        pad=6
    )

    # -----------------------------------------------------
    # BARRAS DE COLOR
    # -----------------------------------------------------

    if cf_pp is not None:

        cax1 = fig.add_axes(
            [0.905, 0.29, 0.020, 0.48]
        )

        cb1 = plt.colorbar(
            cf_pp,
            cax=cax1
        )

        cb1.set_label(
            "Precipitación 12 h (mm)",
            fontsize=10
        )

        cb1.ax.tick_params(
            labelsize=8
        )

    if cf_nub is not None:

        cax2 = fig.add_axes(
            [0.905, 0.09, 0.020, 0.14]
        )

        cb2 = plt.colorbar(
            cf_nub,
            cax=cax2
        )

        cb2.set_label(
            "Nubosidad (%)",
            fontsize=9
        )

        cb2.ax.tick_params(
            labelsize=7
        )

    # -----------------------------------------------------
    # GUARDAR
    # -----------------------------------------------------

    salida = preparar_salida(
        archivo,
        carpeta_salida,
        "superficie"
    )

    plt.savefig(
        salida,
        dpi=200,
        facecolor=fig.get_facecolor()
    )

    plt.close()

    print(
        f"Mapa de superficie generado: "
        f"{salida.resolve()}"
    )


if __name__ == "__main__":
    main()

    # Evita el teardown problemático de cfgrib/eccodes en algunos runners Linux
    # una vez que main() terminó correctamente y el PNG ya fue guardado.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)