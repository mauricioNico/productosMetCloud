#!/usr/bin/env python
import sys
from pathlib import Path
import re
import logging

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch

logging.getLogger("cfgrib").setLevel(logging.ERROR)
logging.getLogger("eccodes").setLevel(logging.ERROR)


def abrir_por_shortname(archivo, short_name, extra_filters=None):
    filtros = {"shortName": short_name}
    if extra_filters:
        filtros.update(extra_filters)

    try:
        return xr.open_dataset(
            archivo,
            engine="cfgrib",
            backend_kwargs={"filter_by_keys": filtros}
        )
    except Exception:
        return None


def abrir_con_filtros_posibles(archivo, filtros_posibles):
    for filtros in filtros_posibles:
        short_name = filtros.get("shortName")
        extra = {k: v for k, v in filtros.items() if k != "shortName"}

        ds = abrir_por_shortname(archivo, short_name, extra)

        if ds is not None and len(ds.data_vars) > 0:
            return ds

    return None


def seleccionar_punto(ds, lat, lon):
    if ds is None:
        return None

    lon_modelo = lon

    try:
        if "longitude" in ds.coords:
            max_lon = float(ds["longitude"].max())
            if max_lon > 180 and lon < 0:
                lon_modelo = lon + 360.0
    except Exception:
        pass

    try:
        return ds.sel(latitude=lat, longitude=lon_modelo, method="nearest")
    except Exception:
        return None


def extraer_variable_principal(ds):
    if ds is None or len(ds.data_vars) == 0:
        return None
    return ds[list(ds.data_vars)[0]]


def extraer_escalar_desde_ds(ds, lat, lon):
    if ds is None:
        return np.nan

    pto = seleccionar_punto(ds, lat, lon)
    if pto is None:
        return np.nan

    da = extraer_variable_principal(pto)
    if da is None:
        return np.nan

    try:
        return float(np.asarray(da.values).squeeze())
    except Exception:
        return np.nan


def extraer_dataarray_punto(ds, lat, lon):
    if ds is None:
        return None

    pto = seleccionar_punto(ds, lat, lon)
    if pto is None:
        return None

    return extraer_variable_principal(pto)


def extraer_escalar_isobarico(ds, lat, lon, nivel_hpa):
    if ds is None:
        return np.nan

    pto = seleccionar_punto(ds, lat, lon)
    if pto is None:
        return np.nan

    da = extraer_variable_principal(pto)
    if da is None:
        return np.nan

    eje = None

    for c in da.coords:
        if "isobaricInhPa" in c:
            eje = c
            break

    if eje is None:
        for d in da.dims:
            if "isobaricInhPa" in d:
                eje = d
                break

    if eje is None:
        return np.nan

    try:
        da_nivel = da.sel({eje: nivel_hpa}, method="nearest")
        return float(np.asarray(da_nivel.values).squeeze())
    except Exception:
        return np.nan


def extraer_perfil_isobarico(ds, lat, lon):
    if ds is None:
        return None, None

    pto = seleccionar_punto(ds, lat, lon)
    if pto is None:
        return None, None

    da = extraer_variable_principal(pto)
    if da is None:
        return None, None

    eje = None

    for c in da.coords:
        if "isobaricInhPa" in c:
            eje = c
            break

    if eje is None:
        for d in da.dims:
            if "isobaricInhPa" in d:
                eje = d
                break

    if eje is None:
        return None, None

    try:
        niveles = np.asarray(da[eje].values, dtype=float)
        valores = np.asarray(da.values, dtype=float).squeeze()

        if valores.ndim != 1:
            valores = valores.reshape(-1)

        return niveles, valores
    except Exception:
        return None, None


def obtener_datetime_valido(ds):
    if ds is None:
        return None

    try:
        if "valid_time" in ds.coords:
            valor = ds["valid_time"].values

            if np.isscalar(valor):
                return pd.to_datetime(valor)

            return pd.to_datetime(valor[0])
    except Exception:
        pass

    try:
        if "time" in ds.coords and "step" in ds.coords:
            tiempo = ds["time"].values
            paso = ds["step"].values

            if not np.isscalar(tiempo):
                tiempo = tiempo[0]

            if not np.isscalar(paso):
                paso = paso[0]

            return pd.to_datetime(tiempo) + pd.to_timedelta(paso)
    except Exception:
        pass

    return None


def obtener_hora_pronostico_desde_nombre(nombre):
    match = re.search(r"_f(\d{3})", nombre)
    if match:
        return int(match.group(1))
    return None


def dewpoint_simple(tc, rh):
    a = 17.27
    b = 237.7

    rh = np.clip(rh, 1, 100)

    gamma = (a * tc / (b + tc)) + np.log(rh / 100.0)
    td = (b * gamma) / (a - gamma)

    return td


def normalizar_porcentaje(val):
    if not np.isfinite(val):
        return np.nan

    if val <= 1.1:
        return val * 100.0

    return val


def normalizar_mslp(mslp):
    if np.isfinite(mslp) and mslp > 2000:
        return mslp / 100.0
    return mslp


def normalizar_t_kelvin(t):
    if np.isfinite(t) and t > 100:
        return t - 273.15
    return t


def normalizar_z500(z):
    if not np.isfinite(z):
        return np.nan

    if z > 10000:
        return z / 9.80665

    return z


def normalizar_precip_mm_desde_da(da):
    if da is None:
        return np.nan

    try:
        val = float(np.asarray(da.values).squeeze())
    except Exception:
        return np.nan

    if not np.isfinite(val):
        return np.nan

    unidades = str(da.attrs.get("units", "")).lower().strip()

    if unidades in ["m", "meter", "metre", "meters", "metres"]:
        return val * 1000.0

    if "kg" in unidades or "mm" in unidades:
        return val

    return val


def leer_tiempo_archivo(archivo):
    candidatos = [
        abrir_por_shortname(archivo, "prmsl"),
        abrir_por_shortname(archivo, "msl"),
        abrir_por_shortname(archivo, "2t"),
        abrir_por_shortname(archivo, "2r"),
        abrir_por_shortname(archivo, "10u"),
        abrir_por_shortname(archivo, "t", {"typeOfLevel": "isobaricInhPa"}),
    ]

    for ds in candidatos:
        t = obtener_datetime_valido(ds)
        if t is not None:
            return t

    return obtener_hora_pronostico_desde_nombre(archivo.name)


def interp_perfil(niveles_origen, valores_origen, niveles_destino):
    if niveles_origen is None or valores_origen is None:
        return np.full(len(niveles_destino), np.nan)

    try:
        niveles_origen = np.asarray(niveles_origen, dtype=float)
        valores_origen = np.asarray(valores_origen, dtype=float)

        orden = np.argsort(niveles_origen)
        x = niveles_origen[orden]
        y = valores_origen[orden]

        return np.interp(niveles_destino, x, y, left=np.nan, right=np.nan)
    except Exception:
        return np.full(len(niveles_destino), np.nan)


def calcular_precipitacion_intervalo(tp_acum):
    serie = pd.Series(tp_acum, dtype="float64")
    pp = serie.diff()

    if len(pp) > 0:
        pp.iloc[0] = 0.0

    pp = pp.where(pp >= 0, 0.0)
    pp = pp.where(pp <= 100, np.nan)

    return pp.values


def fijar_escala_precipitacion(ax, valores):
    pp_max = np.nanmax(valores)

    if np.isfinite(pp_max):
        if pp_max <= 1:
            ax.set_ylim(0, 1)
        elif pp_max <= 5:
            ax.set_ylim(0, 5)
        elif pp_max <= 10:
            ax.set_ylim(0, 10)
        elif pp_max <= 25:
            ax.set_ylim(0, 25)
        else:
            ax.set_ylim(0, 50)
    else:
        ax.set_ylim(0, 1)


def fijar_escala_cape(ax, valores):
    ax.set_ylim(0, 3000)
    ax.set_yticks([0, 500, 1000, 1500, 2000, 2500, 3000])


def fijar_escala_lifted(ax, valores):
    ax.set_ylim(-8, 4)
    ax.set_yticks([-8, -6, -4, -2, 0, 2, 4])


def fijar_escala_omega(ax, valores):
    omin = np.nanmin(valores)
    omax = np.nanmax(valores)

    if not np.isfinite(omin) or not np.isfinite(omax):
        ax.set_ylim(-0.25, 0.15)
        return

    lim = max(abs(omin), abs(omax), 0.10)
    lim = min(max(lim * 1.25, 0.15), 1.0)

    ax.set_ylim(-lim, lim)


def color_cape(valor):
    if not np.isfinite(valor):
        return "#cccccc"

    if valor < 500:
        return "#1fc83a"

    if valor < 1000:
        return "#fff000"

    if valor < 1500:
        return "#ff9d00"

    if valor < 2000:
        return "#ff2d2d"

    return "#8b00a8"


def main():
    if len(sys.argv) < 6:
        print("Uso: meteograma_gfs.py carpeta_gribs carpeta_salidas lat lon nombre_punto")
        sys.exit(1)

    carpeta_gribs = Path(sys.argv[1])
    carpeta_salidas = Path(sys.argv[2])
    lat = float(sys.argv[3])
    lon = float(sys.argv[4])
    nombre_punto = sys.argv[5]

    if not carpeta_gribs.exists():
        print(f"❌ No existe la carpeta: {carpeta_gribs}")
        sys.exit(1)

    carpeta_salidas.mkdir(parents=True, exist_ok=True)

    archivos = sorted(carpeta_gribs.glob("*.grib2"))
    if not archivos:
        print("❌ No se encontraron archivos GRIB2.")
        sys.exit(1)

    niveles_verticales = np.array(
        [1000, 950, 925, 900, 850, 800, 750, 700, 650, 600, 550, 500, 450, 400],
        dtype=float
    )

    tiempos = []

    mslp_list = []
    z500_list = []
    cape_list = []
    lifted_list = []
    omega700_list = []

    t2m_list = []
    rh2m_list = []
    u10_list = []
    v10_list = []
    tp_acum_list = []

    perfiles_t = []
    perfiles_rh = []
    perfiles_u = []
    perfiles_v = []

    for archivo in archivos:
        print(f"\nProcesando {archivo.name}")

        tiempo = leer_tiempo_archivo(archivo)
        if tiempo is None:
            print("  ⚠ No se pudo determinar el tiempo.")
            continue

        ds_prmsl = abrir_por_shortname(archivo, "prmsl")
        ds_msl = abrir_por_shortname(archivo, "msl")

        ds_2t = abrir_por_shortname(archivo, "2t")
        ds_2r = abrir_por_shortname(archivo, "2r")

        ds_10u = abrir_por_shortname(archivo, "10u")
        ds_10v = abrir_por_shortname(archivo, "10v")

        ds_tp = abrir_por_shortname(archivo, "tp")
        if ds_tp is None:
            ds_tp = abrir_por_shortname(archivo, "acpcp")

        ds_cape = abrir_con_filtros_posibles(archivo, [
            {"shortName": "cape", "typeOfLevel": "surface"},
            {"shortName": "cape", "typeOfLevel": "heightAboveGround"},
            {"shortName": "cape", "typeOfLevel": "atmosphere"},
            {"shortName": "cape"}
        ])

        ds_lifted = abrir_con_filtros_posibles(archivo, [
            {"shortName": "lftx", "typeOfLevel": "surface"},
            {"shortName": "4lftx", "typeOfLevel": "surface"},
            {"shortName": "lftx"},
            {"shortName": "4lftx"}
        ])

        ds_w = abrir_por_shortname(
            archivo,
            "w",
            {"typeOfLevel": "isobaricInhPa"}
        )

        ds_t = abrir_por_shortname(
            archivo,
            "t",
            {"typeOfLevel": "isobaricInhPa"}
        )

        ds_r = abrir_por_shortname(
            archivo,
            "r",
            {"typeOfLevel": "isobaricInhPa"}
        )

        ds_u = abrir_por_shortname(
            archivo,
            "u",
            {"typeOfLevel": "isobaricInhPa"}
        )

        ds_v = abrir_por_shortname(
            archivo,
            "v",
            {"typeOfLevel": "isobaricInhPa"}
        )

        ds_gh = abrir_por_shortname(
            archivo,
            "gh",
            {"typeOfLevel": "isobaricInhPa"}
        )

        if ds_gh is None:
            ds_gh = abrir_por_shortname(
                archivo,
                "z",
                {"typeOfLevel": "isobaricInhPa"}
            )

        mslp = extraer_escalar_desde_ds(ds_prmsl, lat, lon)
        if not np.isfinite(mslp):
            mslp = extraer_escalar_desde_ds(ds_msl, lat, lon)
        mslp = normalizar_mslp(mslp)

        z500 = extraer_escalar_isobarico(ds_gh, lat, lon, 500)
        z500 = normalizar_z500(z500)

        cape = extraer_escalar_desde_ds(ds_cape, lat, lon)
        lifted = extraer_escalar_desde_ds(ds_lifted, lat, lon)
        omega700 = extraer_escalar_isobarico(ds_w, lat, lon, 700)

        t2m = extraer_escalar_desde_ds(ds_2t, lat, lon)
        t2m = normalizar_t_kelvin(t2m)

        rh2m = extraer_escalar_desde_ds(ds_2r, lat, lon)
        rh2m = normalizar_porcentaje(rh2m)

        u10 = extraer_escalar_desde_ds(ds_10u, lat, lon)
        v10 = extraer_escalar_desde_ds(ds_10v, lat, lon)

        da_tp = extraer_dataarray_punto(ds_tp, lat, lon)
        tp = normalizar_precip_mm_desde_da(da_tp)

        lev_t, val_t = extraer_perfil_isobarico(ds_t, lat, lon)
        lev_r, val_r = extraer_perfil_isobarico(ds_r, lat, lon)
        lev_u, val_u = extraer_perfil_isobarico(ds_u, lat, lon)
        lev_v, val_v = extraer_perfil_isobarico(ds_v, lat, lon)

        perfil_t = interp_perfil(lev_t, val_t, niveles_verticales)
        perfil_t = np.where(perfil_t > 100, perfil_t - 273.15, perfil_t)

        perfil_r = interp_perfil(lev_r, val_r, niveles_verticales)
        perfil_r = np.array([normalizar_porcentaje(x) for x in perfil_r])

        perfil_u = interp_perfil(lev_u, val_u, niveles_verticales)
        perfil_v = interp_perfil(lev_v, val_v, niveles_verticales)

        unidades_tp = ""
        if da_tp is not None:
            unidades_tp = str(da_tp.attrs.get("units", ""))

        print(
            f"  MSLP={mslp:.1f} | Z500={z500:.0f} | CAPE={cape:.1f} | "
            f"LI={lifted:.1f} | Omega700={omega700:.3f} | "
            f"T2m={t2m:.1f} | RH2m={rh2m:.1f} | "
            f"U10={u10:.1f} V10={v10:.1f} | "
            f"TPacum={tp:.3f} mm | unidades={unidades_tp}"
        )

        tiempos.append(tiempo)

        mslp_list.append(mslp)
        z500_list.append(z500)
        cape_list.append(cape)
        lifted_list.append(lifted)
        omega700_list.append(omega700)

        t2m_list.append(t2m)
        rh2m_list.append(rh2m)
        u10_list.append(u10)
        v10_list.append(v10)
        tp_acum_list.append(tp)

        perfiles_t.append(perfil_t)
        perfiles_rh.append(perfil_r)
        perfiles_u.append(perfil_u)
        perfiles_v.append(perfil_v)

    if not tiempos:
        print("❌ No se pudieron construir series.")
        sys.exit(1)

    df = pd.DataFrame({
        "tiempo": tiempos,
        "mslp": mslp_list,
        "z500": z500_list,
        "cape": cape_list,
        "lifted": lifted_list,
        "omega700": omega700_list,
        "t2m": t2m_list,
        "rh2m": rh2m_list,
        "u10": u10_list,
        "v10": v10_list,
        "tp_acum": tp_acum_list
    })

    df["tiempo"] = pd.to_datetime(df["tiempo"])

    orden = np.argsort(df["tiempo"].values)

    df = df.iloc[orden].reset_index(drop=True)

    perfiles_t = np.asarray(perfiles_t, dtype=float)[orden]
    perfiles_rh = np.asarray(perfiles_rh, dtype=float)[orden]
    perfiles_u = np.asarray(perfiles_u, dtype=float)[orden]
    perfiles_v = np.asarray(perfiles_v, dtype=float)[orden]

    df["td2m"] = np.where(
        np.isfinite(df["t2m"]) & np.isfinite(df["rh2m"]),
        dewpoint_simple(df["t2m"].values, df["rh2m"].values),
        np.nan
    )

    df["wind10_kt"] = np.sqrt(df["u10"] ** 2 + df["v10"] ** 2) * 1.94384
    df["tp_intervalo"] = calcular_precipitacion_intervalo(df["tp_acum"].values)

    x = df["tiempo"]

    if len(df) >= 2:
        difs = np.diff(mdates.date2num(pd.to_datetime(x)))
        difs = difs[np.isfinite(difs)]
        ancho_barra = max(0.03, float(np.min(difs) * 0.65)) if len(difs) else 0.12
    else:
        ancho_barra = 0.12

    fig, axes = plt.subplots(
        7,
        1,
        figsize=(14, 11),
        sharex=True,
        gridspec_kw={
            "height_ratios": [4.8, 1.0, 1.35, 1.0, 1.25, 1.0, 1.15],
            "hspace": 0.04
        }
    )

    fig.suptitle(
        f"Meteograma para {nombre_punto} basado en GFS 0.25",
        fontsize=17,
        fontweight="bold",
        y=0.985
    )

    # -------------------------
    # 1) PERFIL VERTICAL
    # -------------------------
    ax0 = axes[0]

    niveles_hr = [40, 50, 60, 70, 80, 90, 100]

    colores_hr = [
        "#f3fff3",
        "#d6ffd6",
        "#aaffaa",
        "#6cff6c",
        "#00e000",
        "#00a000"
    ]

    cmap_hr = ListedColormap(colores_hr)
    norm_hr = BoundaryNorm(niveles_hr, cmap_hr.N)

    cf = ax0.contourf(
        x,
        niveles_verticales,
        perfiles_rh.T,
        levels=niveles_hr,
        cmap=cmap_hr,
        norm=norm_hr,
        extend="max"
    )

    niveles_temp = np.arange(-40, 31, 5)

    cs_temp = ax0.contour(
        x,
        niveles_verticales,
        perfiles_t.T,
        levels=niveles_temp,
        linewidths=1.0,
        cmap="cool"
    )

    ax0.clabel(
        cs_temp,
        fontsize=8,
        inline=True,
        fmt="%d"
    )

    try:
        cs0 = ax0.contour(
            x,
            niveles_verticales,
            perfiles_t.T,
            levels=[0],
            colors=["#ff1493"],
            linewidths=1.5
        )

        ax0.clabel(
            cs0,
            fontsize=8,
            inline=True,
            fmt={0: "0"}
        )
    except Exception:
        pass

    u_kt = perfiles_u * 1.94384
    v_kt = perfiles_v * 1.94384

    paso_t = max(1, len(x) // 35)
    paso_z = 1

    ax0.barbs(
        mdates.date2num(x)[::paso_t],
        niveles_verticales[::paso_z],
        u_kt[::paso_t, ::paso_z].T,
        v_kt[::paso_t, ::paso_z].T,
        length=5,
        linewidth=0.45
    )

    ax0.set_ylim(1000, 400)
    ax0.set_ylabel("Presión\n(hPa)")
    ax0.grid(True, linestyle="--", alpha=0.45)
    ax0.set_title("HR en altura, temperatura y viento", loc="left", fontsize=10)

    cax_hr = fig.add_axes([0.93, 0.66, 0.012, 0.22])

    cbar = plt.colorbar(
        cf,
        cax=cax_hr,
        orientation="vertical"
    )

    cbar.set_label("HR (%)", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    # -------------------------
    # 2) MSLP + Z500
    # -------------------------
    ax1 = axes[1]

    ax1.plot(
        x,
        df["mslp"],
        color="#004cff",
        linewidth=1.8
    )

    ax1.set_ylabel("SLP\n(hPa)")
    ax1.grid(True, linestyle="--", alpha=0.45)

    ax1b = ax1.twinx()

    ax1b.plot(
        x,
        df["z500"],
        color="#00bcd4",
        linestyle="--",
        linewidth=1.3
    )

    ax1b.set_ylabel("Z500\n(m)")

    # -------------------------
    # 3) CAPE + Lifted Index
    # -------------------------
    ax2 = axes[2]

    colores_cape = [color_cape(v) for v in df["cape"].values]

    ax2.bar(
        x,
        df["cape"],
        width=ancho_barra * 0.75,
        color=colores_cape,
        alpha=0.95,
        edgecolor="white",
        linewidth=0.3,
        zorder=2
    )

    ax2.set_ylabel("CAPE\n(J/kg)")
    fijar_escala_cape(ax2, df["cape"].values)
    ax2.grid(True, linestyle="--", alpha=0.45, zorder=0)

    legend_cape = [
        Patch(facecolor="#8b00a8", label="> 2000"),
        Patch(facecolor="#ff2d2d", label="1500 - 2000"),
        Patch(facecolor="#ff9d00", label="1000 - 1500"),
        Patch(facecolor="#fff000", label="500 - 1000"),
        Patch(facecolor="#1fc83a", label="0 - 500"),
    ]

    ax2.legend(
        handles=legend_cape,
        loc="upper left",
        fontsize=6,
        framealpha=0.85,
        borderpad=0.4
    )

    ax2b = ax2.twinx()

    ax2b.plot(
        x,
        df["lifted"],
        color="black",
        linestyle="--",
        linewidth=1.5,
        zorder=5
    )

    ax2b.axhline(
        0,
        color="black",
        linestyle=":",
        linewidth=0.9,
        alpha=0.8
    )

    ax2b.set_ylabel("LI\n(°C)")
    fijar_escala_lifted(ax2b, df["lifted"].values)
    ax2b.tick_params(axis="y", labelsize=8)

    # -------------------------
    # 4) Viento 10 m
    # -------------------------
    ax3 = axes[3]

    ax3.plot(
        x,
        df["wind10_kt"],
        color="#ff7f00",
        linewidth=1.5
    )

    ax3.set_ylabel("Viento\n10m kt")
    ax3.grid(True, linestyle="--", alpha=0.45)

    ybarb = np.full(
        len(df),
        np.nanmean(df["wind10_kt"]) if np.isfinite(df["wind10_kt"]).any() else 0
    )

    ax3.barbs(
        mdates.date2num(x),
        ybarb,
        df["u10"].values * 1.94384,
        df["v10"].values * 1.94384,
        length=5,
        linewidth=0.55,
        color="#8b5a2b"
    )

    # -------------------------
    # 5) T2m + Td2m
    # -------------------------
    ax4 = axes[4]

    ax4.plot(
        x,
        df["t2m"],
        color="#ff0000",
        linewidth=1.7,
        label="T 2m"
    )

    ax4.plot(
        x,
        df["td2m"],
        color="#6b3f1d",
        linestyle="--",
        linewidth=1.5,
        label="Td 2m"
    )

    base = np.nanmin([df["t2m"].min(), df["td2m"].min()])
    topv = np.nanmax([df["t2m"].max(), df["td2m"].max()])

    if np.isfinite(base) and np.isfinite(topv):
        ax4.fill_between(
            x,
            df["td2m"],
            base - 2,
            color="#2693ff",
            alpha=0.85
        )

        ax4.fill_between(
            x,
            df["t2m"],
            df["td2m"],
            color="#25e225",
            alpha=0.65
        )

    ax4.set_ylabel("Temp\n°C")
    ax4.grid(True, linestyle="--", alpha=0.45)
    ax4.legend(loc="upper right", fontsize=8)

    # -------------------------
    # 6) Omega 700 hPa
    # -------------------------
    ax5 = axes[5]

    ax5.plot(
        x,
        df["omega700"],
        color="#004cff",
        linewidth=1.7
    )

    ax5.axhline(
        0,
        color="#777777",
        linestyle="--",
        linewidth=0.9
    )

    fijar_escala_omega(ax5, df["omega700"].values)

    ax5.set_ylabel("Omega 700\n(Pa/s)")
    ax5.grid(True, linestyle="--", alpha=0.45)

    # -------------------------
    # 7) Precipitación por intervalo
    # -------------------------
    ax6 = axes[6]

    ax6.bar(
        x,
        df["tp_intervalo"],
        width=ancho_barra,
        color="#00c83a",
        alpha=0.9
    )

    ax6.set_ylabel("PP\nmm")
    fijar_escala_precipitacion(ax6, df["tp_intervalo"].values)
    ax6.grid(True, linestyle="--", alpha=0.45)

    ax6.xaxis.set_major_formatter(
        mdates.DateFormatter("%d%b\n%HZ")
    )

    for ax in axes[:-1]:
        plt.setp(ax.get_xticklabels(), visible=False)

    nombre_archivo = re.sub(r"[^A-Za-z0-9_\-]", "_", nombre_punto)
    salida = carpeta_salidas / f"meteograma_{nombre_archivo}.png"

    plt.tight_layout(rect=[0, 0, 0.92, 0.975])
    plt.savefig(salida, dpi=150, bbox_inches="tight")
    plt.close()

    print(f"\n✔ Meteograma generado: {salida.resolve()}")


if __name__ == "__main__":
    main()