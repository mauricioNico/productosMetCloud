#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sounding_gfs.py

Genera un radiosondeo pronosticado tipo Skew-T / Log-P a partir de un GRIB2 GFS.

Uso:
    python sounding_gfs.py archivo_grib carpeta_salidas lat lon nombre_punto

Ejemplo:
    python python/sounding_gfs.py gribs/20260529/gfs_20260529_06_f024_Tm200_Bm800_L2650_R3350.grib2 salidas/20260529/soundings06 -34.92 -57.95 La_Plata

Requiere:
    pip install xarray cfgrib metpy matplotlib numpy pandas
"""

import sys
import re
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt

from metpy.plots import SkewT
from metpy.units import units
import metpy.calc as mpcalc

logging.getLogger("cfgrib").setLevel(logging.ERROR)
logging.getLogger("eccodes").setLevel(logging.ERROR)

NIVEL_TOPE_HPA = 150.0

NIVELES_VIENTO_SIGNIFICATIVOS = np.array(
    [1000, 850, 700, 500, 400, 300, 250, 200, 150],
    dtype=float
)


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


def obtener_ciclo_desde_nombre(nombre):
    match = re.search(r"gfs_(\d{8})_(\d{2})_f(\d{3})", nombre)
    if match:
        fecha = match.group(1)
        ciclo = match.group(2)
        fff = match.group(3)
        return fecha, ciclo, fff
    return None, None, None


def normalizar_temperatura_celsius(valores):
    valores = np.asarray(valores, dtype=float)
    return np.where(valores > 100, valores - 273.15, valores)


def normalizar_rh_fraccion(valores):
    valores = np.asarray(valores, dtype=float)
    valores = np.where(valores > 1.1, valores / 100.0, valores)
    return np.clip(valores, 0.01, 1.0)


def ordenar_xy_para_interp(x, y):
    """
    np.interp necesita que el eje x esté en orden ascendente.
    Los niveles isobáricos muchas veces vienen de 1000 a 100 hPa,
    por eso hay que ordenarlos antes de interpolar.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    mascara = np.isfinite(x) & np.isfinite(y)
    x = x[mascara]
    y = y[mascara]

    if len(x) == 0 or len(y) == 0:
        return x, y

    orden = np.argsort(x)
    return x[orden], y[orden]


def interp_isobarico_seguro(niveles_origen, valores_origen, niveles_destino):
    x, y = ordenar_xy_para_interp(niveles_origen, valores_origen)

    if len(x) == 0 or len(y) == 0:
        return np.full(len(niveles_destino), np.nan)

    return np.interp(
        niveles_destino,
        x,
        y,
        left=np.nan,
        right=np.nan
    )


def preparar_perfiles(archivo, lat, lon):
    ds_t = abrir_por_shortname(archivo, "t", {"typeOfLevel": "isobaricInhPa"})
    ds_r = abrir_por_shortname(archivo, "r", {"typeOfLevel": "isobaricInhPa"})
    ds_u = abrir_por_shortname(archivo, "u", {"typeOfLevel": "isobaricInhPa"})
    ds_v = abrir_por_shortname(archivo, "v", {"typeOfLevel": "isobaricInhPa"})

    # Algunos GRIB pueden traer gh o z. No es obligatorio para el Skew-T,
    # pero lo dejamos abierto por si se quiere extender luego.
    ds_gh = abrir_por_shortname(archivo, "gh", {"typeOfLevel": "isobaricInhPa"})
    if ds_gh is None:
        ds_gh = abrir_por_shortname(archivo, "z", {"typeOfLevel": "isobaricInhPa"})

    p_t, t = extraer_perfil_isobarico(ds_t, lat, lon)
    p_r, rh = extraer_perfil_isobarico(ds_r, lat, lon)
    p_u, u = extraer_perfil_isobarico(ds_u, lat, lon)
    p_v, v = extraer_perfil_isobarico(ds_v, lat, lon)

    if p_t is None or t is None:
        raise RuntimeError("No se pudo leer temperatura isobárica del GRIB.")
    if p_r is None or rh is None:
        raise RuntimeError("No se pudo leer humedad relativa isobárica del GRIB.")
    if p_u is None or u is None or p_v is None or v is None:
        raise RuntimeError("No se pudo leer viento isobárico U/V del GRIB.")

    # Eje principal: niveles donde existe temperatura.
    pres = np.asarray(p_t, dtype=float)
    temp_c = normalizar_temperatura_celsius(t)

    # Corregido: antes de interpolar, se ordena cada eje de presión.
    # Si no se hace esto, np.interp puede devolver todo NaN y el perfil queda vacío.
    rh_interp = interp_isobarico_seguro(p_r, rh, pres)
    u_interp = interp_isobarico_seguro(p_u, u, pres)
    v_interp = interp_isobarico_seguro(p_v, v, pres)

    rh_frac = normalizar_rh_fraccion(rh_interp)

    mascara = (
        np.isfinite(pres) &
        np.isfinite(temp_c) &
        np.isfinite(rh_frac) &
        np.isfinite(u_interp) &
        np.isfinite(v_interp) &
        (pres > 0)
    )

    pres = pres[mascara]
    temp_c = temp_c[mascara]
    rh_frac = rh_frac[mascara]
    u_interp = u_interp[mascara]
    v_interp = v_interp[mascara]

    if len(pres) < 3:
        raise RuntimeError(
            "El perfil quedó con menos de 3 niveles válidos. "
            "Revise si el GRIB tiene niveles isobáricos completos para ese punto."
        )

    # Skew-T espera presiones ordenadas de mayor a menor.
    orden = np.argsort(pres)[::-1]
    pres = pres[orden]
    temp_c = temp_c[orden]
    rh_frac = rh_frac[orden]
    u_interp = u_interp[orden]
    v_interp = v_interp[orden]

    print(f"Perfil válido: {len(pres)} niveles | "
          f"Presión máx={np.nanmax(pres):.0f} hPa | "
          f"Presión mín={np.nanmin(pres):.0f} hPa")

    p = pres * units.hPa
    T = temp_c * units.degC
    RH = rh_frac * units.dimensionless
    Td = mpcalc.dewpoint_from_relative_humidity(T, RH)
    U = u_interp * units("m/s")
    V = v_interp * units("m/s")

    return p, T, Td, U, V, ds_t


def calcular_indices(p, T, Td):
    indices = {
        "LCL": np.nan,
        "CAPE": np.nan,
        "CIN": np.nan,
        "LI": np.nan,
        "K": np.nan,
        "TT": np.nan,
        "PWAT": np.nan,
        "parcel_profile": None
    }

    if len(p) < 3:
        return indices

    try:
        lcl_p, lcl_t = mpcalc.lcl(p[0], T[0], Td[0])
        indices["LCL"] = float(lcl_p.to("hPa").magnitude)
    except Exception as e:
        print(f"⚠ No se pudo calcular LCL: {e}")

    try:
        prof = mpcalc.parcel_profile(p, T[0], Td[0])
        indices["parcel_profile"] = prof
    except Exception as e:
        print(f"⚠ No se pudo calcular perfil de parcela: {e}")
        prof = None

    if prof is not None:
        try:
            cape, cin = mpcalc.cape_cin(p, T, Td, prof)
            indices["CAPE"] = float(cape.to("J/kg").magnitude)
            indices["CIN"] = float(cin.to("J/kg").magnitude)
        except Exception as e:
            print(f"⚠ No se pudo calcular CAPE/CIN: {e}")

        try:
            pres_asc = p.magnitude[::-1]
            temp_asc = T.to("degC").magnitude[::-1]
            prof_asc = prof.to("degC").magnitude[::-1]

            if np.nanmin(p.magnitude) <= 500.0 <= np.nanmax(p.magnitude):
                t500 = np.interp(500.0, pres_asc, temp_asc)
                parcel500 = np.interp(500.0, pres_asc, prof_asc)
                indices["LI"] = float(t500 - parcel500)
        except Exception as e:
            print(f"⚠ No se pudo calcular LI: {e}")

    # K Index necesita niveles clásicos como 850/700/500 hPa.
    try:
        if np.nanmin(p.magnitude) <= 500 and np.nanmax(p.magnitude) >= 850:
            indices["K"] = float(mpcalc.k_index(p, T, Td).magnitude)
    except Exception as e:
        print(f"⚠ No se pudo calcular K Index: {e}")

    # Total Totals también depende de 850 y 500 hPa.
    try:
        if np.nanmin(p.magnitude) <= 500 and np.nanmax(p.magnitude) >= 850:
            indices["TT"] = float(mpcalc.total_totals_index(p, T, Td).magnitude)
    except Exception as e:
        print(f"⚠ No se pudo calcular Total Totals: {e}")

    try:
        pw = mpcalc.precipitable_water(p, Td)
        indices["PWAT"] = float(pw.to("mm").magnitude)
    except Exception as e:
        print(f"⚠ No se pudo calcular PWAT: {e}")

    return indices


def fmt_indice(valor, decimales=0, unidad=""):
    if not np.isfinite(valor):
        return "s/d"
    return f"{valor:.{decimales}f}{unidad}"


def filtrar_perfil_hasta_150_hpa(p, T, Td, U, V):
    """
    Limita el perfil al tramo 1000-150 hPa.

    El GFS puede traer niveles muy altos, incluso 100, 70, 50, 30, 20, 10, 5 y 1 hPa.
    Para un sondeo operativo más legible se corta en 150 hPa.
    """
    try:
        mascara = p.magnitude >= NIVEL_TOPE_HPA

        p = p[mascara]
        T = T[mascara]
        Td = Td[mascara]
        U = U[mascara]
        V = V[mascara]

        if len(p) < 3:
            raise RuntimeError(
                "El perfil quedó con menos de 3 niveles luego de limitarlo a 150 hPa."
            )

        print(
            f"Perfil graficado: {len(p)} niveles | "
            f"Presión máx={np.nanmax(p.magnitude):.0f} hPa | "
            f"Presión mín={np.nanmin(p.magnitude):.0f} hPa"
        )

        return p, T, Td, U, V

    except Exception as e:
        raise RuntimeError(f"No se pudo filtrar el perfil hasta 150 hPa: {e}")


def graficar_barbas_niveles_significativos(skew, p, U, V):
    """
    Grafica viento solo en niveles significativos:
    1000, 850, 700, 500, 400, 300, 250, 200 y 150 hPa.

    Si el GRIB no trae exactamente un nivel, se usa el más cercano dentro de una tolerancia.
    """
    try:
        p_hpa = np.asarray(p.magnitude, dtype=float)
        u_kt = np.asarray(U.to("kt").magnitude, dtype=float)
        v_kt = np.asarray(V.to("kt").magnitude, dtype=float)

        niveles = []
        u_sel = []
        v_sel = []

        for nivel in NIVELES_VIENTO_SIGNIFICATIVOS:
            if len(p_hpa) == 0:
                continue

            idx = int(np.nanargmin(np.abs(p_hpa - nivel)))
            diferencia = abs(p_hpa[idx] - nivel)

            # Tolerancia para aceptar el nivel más cercano.
            # En GFS normalmente existen estos niveles exactos.
            if np.isfinite(diferencia) and diferencia <= 30:
                niveles.append(p_hpa[idx])
                u_sel.append(u_kt[idx])
                v_sel.append(v_kt[idx])

        if len(niveles) == 0:
            print("⚠ No se encontraron niveles válidos para graficar barbas de viento.")
            return

        skew.plot_barbs(
            np.asarray(niveles) * units.hPa,
            np.asarray(u_sel) * units.kt,
            np.asarray(v_sel) * units.kt
        )

        niveles_txt = ", ".join(f"{n:.0f}" for n in niveles)
        print(f"Barbas de viento graficadas en niveles hPa: {niveles_txt}")

    except Exception as e:
        print(f"⚠ No se pudieron graficar las barbas de viento: {e}")


def generar_sounding(archivo, carpeta_salidas, lat, lon, nombre_punto):
    carpeta_salidas.mkdir(parents=True, exist_ok=True)

    p, T, Td, U, V, ds_t = preparar_perfiles(archivo, lat, lon)

    # Se limita el sondeo a 150 hPa para evitar graficar niveles estratosféricos
    # innecesarios y para mantener una escala más útil en el análisis operativo.
    p, T, Td, U, V = filtrar_perfil_hasta_150_hpa(p, T, Td, U, V)

    indices = calcular_indices(p, T, Td)

    fecha, ciclo, fff = obtener_ciclo_desde_nombre(archivo.name)
    valid_time = obtener_datetime_valido(ds_t)

    fig = plt.figure(figsize=(10, 10))
    skew = SkewT(fig, rotation=45)

    skew.plot(p, T, "red", linewidth=2.0, label="T")
    skew.plot(p, Td, "green", linewidth=2.0, label="Td")

    if indices["parcel_profile"] is not None:
        try:
            skew.plot(p, indices["parcel_profile"], "black", linewidth=1.4, linestyle="--", label="Parcela")
        except Exception as e:
            print(f"⚠ No se pudo graficar la parcela: {e}")

    # Viento en niveles significativos.
    graficar_barbas_niveles_significativos(skew, p, U, V)

    skew.ax.set_ylim(1000, NIVEL_TOPE_HPA)
    skew.ax.set_xlim(-45, 35)
    skew.ax.set_xlabel("Temperatura (°C)")
    skew.ax.set_ylabel("Presión (hPa)")
    skew.ax.grid(True, linestyle="--", alpha=0.45)

    try:
        skew.plot_dry_adiabats(alpha=0.35)
        skew.plot_moist_adiabats(alpha=0.35)
        skew.plot_mixing_lines(alpha=0.25)
    except Exception:
        pass

    titulo = f"Sondeo: {nombre_punto}"
    subtitulo = f"Lat {lat:.2f} | Lon {lon:.2f}"

    if fecha and ciclo and fff:
        subtitulo += f" | Corrida {fecha} {ciclo}Z | f{fff}"

    if valid_time is not None:
        subtitulo += f" | Válido {pd.to_datetime(valid_time).strftime('%d/%m/%Y %HZ')}"

    skew.ax.set_title(titulo, loc="left", fontsize=14, fontweight="bold")
    skew.ax.set_title(subtitulo, loc="right", fontsize=9)

    texto = (
        f"LCL: {fmt_indice(indices['LCL'], 0, ' hPa')}\n"
        f"CAPE: {fmt_indice(indices['CAPE'], 0, ' J/kg')}\n"
        f"CIN: {fmt_indice(indices['CIN'], 0, ' J/kg')}\n"
        f"LI: {fmt_indice(indices['LI'], 1, '')}\n"
        f"K: {fmt_indice(indices['K'], 1, '')}\n"
        f"TT: {fmt_indice(indices['TT'], 1, '')}\n"
        f"PWAT: {fmt_indice(indices['PWAT'], 1, ' mm')}"
    )

    skew.ax.text(
        0.02,
        0.03,
        texto,
        transform=skew.ax.transAxes,
        fontsize=9,
        va="bottom",
        ha="left",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85)
    )

    skew.ax.legend(loc="upper right", fontsize=9)

    nombre_limpio = re.sub(r"[^A-Za-z0-9_\-]", "_", nombre_punto)
    fff_salida = fff if fff else f"{obtener_hora_pronostico_desde_nombre(archivo.name) or 0:03d}"
    salida = carpeta_salidas / f"sounding_{nombre_limpio}_f{fff_salida}.png"

    plt.savefig(salida, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"✔ Sounding generado: {salida.resolve()}")
    return salida


def main():
    print("Usando sounding_gfs.py version defensiva v4 - perfil hasta 150 hPa")

    if len(sys.argv) < 6:
        print("Uso: sounding_gfs.py archivo_grib carpeta_salidas lat lon nombre_punto")
        sys.exit(1)

    archivo = Path(sys.argv[1])
    carpeta_salidas = Path(sys.argv[2])
    lat = float(sys.argv[3])
    lon = float(sys.argv[4])
    nombre_punto = sys.argv[5]

    if not archivo.exists():
        print(f"❌ No existe el archivo GRIB: {archivo}")
        sys.exit(1)

    try:
        generar_sounding(archivo, carpeta_salidas, lat, lon, nombre_punto)
    except Exception as e:
        print(f"❌ Error generando sounding: {e}")
        print("Detalle técnico:")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()