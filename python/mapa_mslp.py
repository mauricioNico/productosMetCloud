#!/usr/bin/env python
import sys
from pathlib import Path
import datetime as dt
import re
import logging

import numpy as np
import xarray as xr
import cfgrib
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

from matplotlib.colors import ListedColormap, BoundaryNorm, LinearSegmentedColormap
from matplotlib.ticker import FixedLocator
from matplotlib.cm import ScalarMappable
from scipy.ndimage import maximum_filter, minimum_filter

logging.getLogger("cfgrib").setLevel(logging.ERROR)
logging.getLogger("eccodes").setLevel(logging.ERROR)


def abrir_cfgrib(archivo, filtros):
    try:
        return xr.open_dataset(
            archivo,
            engine="cfgrib",
            backend_kwargs={"filter_by_keys": filtros}
        )
    except Exception as e:
        print(f"  ⚠ No se pudo abrir con filtros {filtros}: {e}")
        return None


def elegir_var(ds, candidatos):
    if ds is None:
        return None

    cand = {c.lower() for c in candidatos}

    for nombre in ds.data_vars:
        if nombre.lower() in cand:
            return nombre

    for nombre, da in ds.data_vars.items():
        short = str(da.attrs.get("shortName", "")).lower()
        if short in cand:
            return nombre

    return None


def npdatetime_a_datetime(np_dt):
    try:
        iso = np.datetime_as_string(np_dt, unit="h")
        return dt.datetime.fromisoformat(iso)
    except Exception:
        return None


def formatear_fecha_es(fecha_dt):
    if fecha_dt is None:
        return "N/D"

    dias = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    meses = ["ene", "feb", "mar", "abr", "may", "jun",
             "jul", "ago", "sep", "oct", "nov", "dic"]

    return f"{dias[fecha_dt.weekday()]} {fecha_dt.day:02d} {meses[fecha_dt.month-1]} {fecha_dt.year}, {fecha_dt:%H} UTC"


def agregar_fondo_gradiente(fig):
    try:
        ax_bg = fig.add_axes([0, 0, 1, 1], zorder=-1)
        ax_bg.set_axis_off()

        grad = np.linspace(0, 1, 512).reshape(512, 1)

        cmap = LinearSegmentedColormap.from_list(
            "fondo_gradiente",
            [
                (0.00, "#6db3f2"),
                (0.37, "#54a3ee"),
                (0.64, "#54a3ee"),
                (1.00, "#1e69de"),
            ]
        )

        ax_bg.imshow(
            grad,
            aspect="auto",
            cmap=cmap,
            origin="upper",
            extent=[0, 1, 0, 1]
        )

    except Exception as e:
        print(f"⚠ No se pudo dibujar el fondo gradiente: {e}")


def seleccionar_tiempo_unico(da):
    if da is None:
        return None

    if "step" in da.dims:
        try:
            da = da.isel(step=-1)
        except Exception:
            pass

    if "time" in da.dims:
        try:
            da = da.isel(time=0)
        except Exception:
            pass

    if "valid_time" in da.dims:
        try:
            da = da.isel(valid_time=0)
        except Exception:
            pass

    return da


def recortar_area(da, top, bottom, left, right):
    if da is None:
        return None

    try:
        lat_vals = da["latitude"].values
        lat_asc = lat_vals[0] < lat_vals[-1]

        if lat_asc:
            lat_slice = slice(bottom, top)
        else:
            lat_slice = slice(top, bottom)

        return da.sel(
            latitude=lat_slice,
            longitude=slice(left, right)
        )

    except Exception as e:
        print(f"⚠ Error recortando área: {e}")
        return da


def normalizar_porcentaje(da):
    if da is None:
        return None

    try:
        if float(da.max()) <= 1.1:
            da = da * 100.0
    except Exception:
        pass

    return da


def cargar_campo_simple(archivo_grib, filtros, candidatos, top, bottom, left, right):
    ds = abrir_cfgrib(archivo_grib, filtros)
    if ds is None:
        return None

    var = elegir_var(ds, candidatos)
    if var is None:
        return None

    da = ds[var]
    da = recortar_area(da, top, bottom, left, right)
    da = seleccionar_tiempo_unico(da)

    return da


def construir_nubosidad_total(archivo_grib, top, bottom, left, right):
    print("→ Cargando nubosidad total / cielo cubierto...")

    filtros_tcc = [
        {"shortName": "tcc", "typeOfLevel": "atmosphere", "stepType": "instant"},
        {"shortName": "tcc", "typeOfLevel": "atmosphere", "stepType": "avg"},
        {"shortName": "tcc", "typeOfLevel": "entireAtmosphere"},
        {"shortName": "tcc", "typeOfLevel": "atmosphere"},
        {"shortName": "tcc", "typeOfLevel": "unknown"},
        {"shortName": "tcc"},
        {"shortName": "tcdc"},
    ]

    for filtros in filtros_tcc:
        da = cargar_campo_simple(
            archivo_grib,
            filtros,
            {"tcc", "tcdc"},
            top,
            bottom,
            left,
            right
        )

        if da is not None:
            da = normalizar_porcentaje(da)
            print(f"✔ Nubosidad total encontrada con filtros: {filtros}")
            return da

    print("⚠ No se encontró TCC. Se intenta construir con LCC + MCC + HCC...")

    lcc = cargar_campo_simple(
        archivo_grib,
        {"shortName": "lcc"},
        {"lcc"},
        top,
        bottom,
        left,
        right
    )

    mcc = cargar_campo_simple(
        archivo_grib,
        {"shortName": "mcc"},
        {"mcc"},
        top,
        bottom,
        left,
        right
    )

    hcc = cargar_campo_simple(
        archivo_grib,
        {"shortName": "hcc"},
        {"hcc"},
        top,
        bottom,
        left,
        right
    )

    capas = []
    for capa in [lcc, mcc, hcc]:
        if capa is not None:
            capa = normalizar_porcentaje(capa)
            capas.append(capa)

    if len(capas) == 0:
        print("⚠ No se pudo cargar nubosidad.")
        return None

    try:
        nub = xr.concat(capas, dim="cloud_layer").max(dim="cloud_layer")
        print("✔ Nubosidad construida usando máximo entre capas disponibles.")
        return nub
    except Exception as e:
        print(f"⚠ No se pudo construir nubosidad desde capas: {e}")
        return capas[0]


def main():
    if len(sys.argv) < 7:
        print("Uso: mapa_mslp.py archivo.grib2 salida.png top bottom left right")
        sys.exit(1)

    archivo_grib = Path(sys.argv[1])
    archivo_salida_cli = Path(sys.argv[2])

    top = float(sys.argv[3])
    bottom = float(sys.argv[4])
    left = float(sys.argv[5])
    right = float(sys.argv[6])

    if top < 0 and bottom > 0:
        print(f"⚠ bottom={bottom} parece hemisferio sur. Se corrige a {-bottom}.")
        bottom = -bottom

    precip = None
    thickness = None
    nubosidad = None
    u10 = None
    v10 = None

    pat = re.search(r"(20\d{6})", archivo_grib.name)
    if pat:
        fecha_str = pat.group(1)
    else:
        fecha_str = dt.datetime.utcnow().strftime("%Y%m%d")

    carpeta_gribs = Path("gribs") / fecha_str

    carpeta_gribs.mkdir(parents=True, exist_ok=True)

    archivo_salida_cli.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if archivo_grib.exists() and archivo_grib.parent.resolve() != carpeta_gribs.resolve():
        destino = carpeta_gribs / archivo_grib.name
        try:
            archivo_grib.replace(destino)
            archivo_grib = destino
        except Exception as e:
            print(f"⚠ No se pudo mover el GRIB a {destino}: {e}")

    if not archivo_grib.exists():
        print(f"No se encontro el archivo: {archivo_grib}")
        sys.exit(1)

    archivo_salida = archivo_salida_cli
    print(f"Salida PNG solicitada por Java: {archivo_salida}")
    print(f"\n=== Abriendo archivo {archivo_grib.name} ===\n")

    # ---------------- MSLP ----------------
    print("→ Cargando MSLP...")
    ds_mslp = abrir_cfgrib(
        archivo_grib,
        {"typeOfLevel": "meanSea", "stepType": "instant"}
    )

    if ds_mslp is None:
        print("⚠ No se pudo abrir el GRIB para MSLP.")
        sys.exit(1)

    mslp_var = elegir_var(ds_mslp, {"prmsl", "msl", "mslet"})
    if mslp_var is None:
        print("⚠ No se encontro variable de MSLP.")
        sys.exit(1)

    mslp = ds_mslp[mslp_var]
    mslp = recortar_area(mslp, top, bottom, left, right)
    mslp = seleccionar_tiempo_unico(mslp)

    try:
        if float(mslp.max()) > 2000:
            mslp = mslp / 100.0
    except Exception:
        pass

    lats = mslp["latitude"]
    lons = mslp["longitude"]

    horas_pron = 0
    try:
        step = ds_mslp["step"].values
        if isinstance(step, np.ndarray):
            step = step[0]
        horas_pron = int(step / np.timedelta64(1, "h"))
    except Exception:
        horas_pron = 0

    init_dt = None
    valid_dt = None
    try:
        if "time" in ds_mslp.coords:
            v = ds_mslp["time"].values
            init_np = v if np.isscalar(v) else v[0]
            init_dt = npdatetime_a_datetime(init_np)

        if "valid_time" in ds_mslp.coords:
            v = ds_mslp["valid_time"].values
            valid_np = v if np.isscalar(v) else v[0]
            valid_dt = npdatetime_a_datetime(valid_np)
        elif init_dt is not None:
            valid_dt = init_dt + dt.timedelta(hours=horas_pron)

    except Exception as e:
        print(f"⚠ No se pudo determinar fecha/hora valida: {e}")

    init_str = formatear_fecha_es(init_dt)
    valid_str = formatear_fecha_es(valid_dt)

    # ---------------- ESPESOR 500/1000 ----------------
    print("→ Cargando espesores 500/1000...")

    ds_gh = abrir_cfgrib(
        archivo_grib,
        {"typeOfLevel": "isobaricInhPa", "stepType": "instant"}
    )

    if ds_gh is not None:
        gh_var = elegir_var(ds_gh, {"gh", "z", "hgt"})

        if gh_var is not None:
            gh = ds_gh[gh_var]
            gh = recortar_area(gh, top, bottom, left, right)
            gh = seleccionar_tiempo_unico(gh)

            lev_name = "isobaricInhPa"
            try:
                z500 = gh.sel({lev_name: 500})
                z1000 = gh.sel({lev_name: 1000})
                thickness = z500 - z1000

                if float(thickness.max()) > 2000:
                    thickness = thickness / 10.0

            except Exception as e:
                print(f"⚠ No se pudo calcular espesor 500/1000: {e}")
        else:
            print("⚠ No se encontró variable GH/Z/HGT para espesores.")
    else:
        print("⚠ No se pudieron cargar datos isobáricos para espesores.")

    # ---------------- PRECIPITACION ----------------
    print("→ Cargando precipitacion acumulada...")

    ds_surface_accum = abrir_cfgrib(
        archivo_grib,
        {"typeOfLevel": "surface", "stepType": "accum"}
    )

    if ds_surface_accum is not None:
        precip_var = elegir_var(ds_surface_accum, {"tp", "prate", "acpcp"})

        if precip_var:
            precip = ds_surface_accum[precip_var]
            precip = recortar_area(precip, top, bottom, left, right)
            precip = seleccionar_tiempo_unico(precip)

            try:
                if float(precip.max()) < 10:
                    precip = precip * 1000.0
            except Exception:
                pass
        else:
            print("⚠ No se encontro variable de precipitacion.")
    else:
        print("⚠ No hay datos de precipitacion acumulada en este GRIB.")

    nubosidad = construir_nubosidad_total(
        archivo_grib,
        top,
        bottom,
        left,
        right
    )

    # ---------------- VIENTO 10 m ----------------
    print("→ Cargando viento 10 m...")

    try:
        ds_u = xr.open_dataset(
            archivo_grib,
            engine="cfgrib",
            backend_kwargs={"filter_by_keys": {"shortName": "10u"}}
        )
        var_u = elegir_var(ds_u, {"10u"}) or list(ds_u.data_vars)[0]
        u10 = ds_u[var_u]

        ds_v = xr.open_dataset(
            archivo_grib,
            engine="cfgrib",
            backend_kwargs={"filter_by_keys": {"shortName": "10v"}}
        )
        var_v = elegir_var(ds_v, {"10v"}) or list(ds_v.data_vars)[0]
        v10 = ds_v[var_v]

        u10 = recortar_area(u10, top, bottom, left, right)
        v10 = recortar_area(v10, top, bottom, left, right)

        u10 = seleccionar_tiempo_unico(u10)
        v10 = seleccionar_tiempo_unico(v10)

        print("✔ Viento 10 m cargado.")

    except Exception as e:
        print(f"⚠ No se pudo cargar viento 10 m: {e}")
        u10 = v10 = None

    # ---------------- FIGURA ----------------
    print("\n→ Generando carta...\n")

    proj = ccrs.PlateCarree()

    fig, ax = plt.subplots(
        figsize=(11.053, 9.053),
    subplot_kw={"projection": proj}
    )

    # Mapa casi a todo el ancho, dejando columna fina para escalas.
    fig.subplots_adjust(left=0.025, right=0.905, top=0.915, bottom=0.045)

    fig.patch.set_alpha(0.0)
    agregar_fondo_gradiente(fig)
    ax.set_facecolor("none")

    ax.set_extent([left, right, bottom, top], crs=proj)

    gl = ax.gridlines(
        crs=proj,
        draw_labels=True,
        linewidth=0.6,
        color="gray",
        linestyle="--",
        alpha=0.6
    )
    gl.xlocator = FixedLocator(np.arange(left, right + 1, 10))
    gl.ylocator = FixedLocator(np.arange(bottom, top + 1, 10))
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {"size": 7}
    gl.ylabel_style = {"size": 7}

    # ---------------- FONDO CARTOGRÁFICO ESTILO ECMWF / METEORED ----------------
    # Se dibuja con zorder bajo para que las capas meteorológicas queden encima.
    ax.add_feature(cfeature.OCEAN.with_scale("50m"), facecolor="#a9c9e8", zorder=0)
    ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#e8c7ae", zorder=0)
    ax.add_feature(cfeature.LAKES.with_scale("50m"), facecolor="#a9c9e8", zorder=0)

    # Las costas, fronteras y provincias se vuelven a dibujar más abajo, por encima
    # de la precipitación. Acá quedan como base inicial.
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), linewidth=0.7, edgecolor="#ffffff", zorder=3)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), linewidth=0.45, edgecolor="#5c4738", zorder=3)

    # ---------------- NUBOSIDAD TOTAL / CIELO CUBIERTO ----------------
    cmap_nub = ListedColormap([
        "#f4f4f4",
        "#d9d9d9",
        "#bdbdbd",
        "#969696",
        "#737373",
        "#525252"
    ])

    niveles_nub = [40, 50, 60, 70, 80, 90, 100]
    norm_nub = BoundaryNorm(niveles_nub, cmap_nub.N)

    if nubosidad is not None:
        try:
            ax.contourf(
                lons,
                lats,
                nubosidad,
                levels=niveles_nub,
                cmap=cmap_nub,
                norm=norm_nub,
                alpha=0.36,
                transform=proj,
                extend="max",
                zorder=1
            )
            print("✔ Nubosidad / cielo cubierto dibujado.")
        except Exception as e:
            print(f"⚠ Error al dibujar nubosidad: {e}")
    else:
        print("⚠ No se dibuja nubosidad porque no fue cargada.")

    # ---------------- PRECIPITACIÓN ESTILO ECMWF / METEORED ----------------
    # Importante: zorder bajo + alpha moderado. Así la precipitación NO tapa
    # límites, isobaras, espesores, contornos de nieve ni barbas de viento.
    if precip is not None:
        try:
            bounds = [
                0.2, 0.5, 1, 2, 3, 4, 5,
                10, 15, 20, 25, 30, 35, 40, 45, 50,
                60, 70, 80, 100, 120, 150
            ]

            colors = [
                "#dffcff",
                "#a8f6ff",
                "#63eaff",
                "#28cfff",
                "#149cff",
                "#006dff",
                "#003cff",
                "#1717c8",
                "#1b007a",
                "#3b006f",
                "#5a008c",
                "#7b20a3",
                "#9b45bd",
                "#c261d0",
                "#f07bd8",
                "#ff9bbb",
                "#ff6b75",
                "#e60000",
                "#b80000",
                "#7a1e1e",
                "#4a1a1a",
            ]

            cmap_p = ListedColormap(colors)
            norm_p = BoundaryNorm(bounds, cmap_p.N)

            cf_p = ax.contourf(
                lons,
                lats,
                precip,
                levels=bounds,
                cmap=cmap_p,
                norm=norm_p,
                extend="max",
                alpha=0.60,
                transform=proj,
                zorder=2
            )

            # Escala fina de precipitación.
            cax_p = fig.add_axes([0.925, 0.33, 0.018, 0.50])

            cbar_p = plt.colorbar(
                cf_p,
                cax=cax_p,
                ticks=bounds,
                label="Precipitación (mm)"
            )
            cbar_p.ax.tick_params(labelsize=7)
            cbar_p.set_label("Precipitación (mm)", fontsize=9)

        except Exception as e:
            print(f"⚠ Error al dibujar precipitación: {e}")

    # ---------------- LÍMITES SOBRE CAPAS METEOROLÓGICAS ----------------
    # Se dibujan DESPUÉS de la precipitación para que no desaparezcan.
    try:
        provincias = cfeature.NaturalEarthFeature(
            "cultural",
            "admin_1_states_provinces_lines",
            "10m",
            edgecolor="#5c4738",
            facecolor="none"
        )
        ax.add_feature(provincias, linewidth=0.55, alpha=0.95, zorder=7)
    except Exception as e:
        print(f"⚠ No se pudieron dibujar límites provinciales: {e}")

    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), linewidth=0.8, edgecolor="#ffffff", zorder=7)
    ax.add_feature(cfeature.BORDERS.with_scale("50m"), linewidth=0.55, edgecolor="#4d3a2f", zorder=7)

    # ---------------- ESCALA FINA DE NUBOSIDAD ----------------
    try:
        if nubosidad is not None:
            cax_n = fig.add_axes([0.925, 0.105, 0.018, 0.16])

            sm_nub = ScalarMappable(norm=norm_nub, cmap=cmap_nub)
            sm_nub.set_array([])

            cbar_nub = plt.colorbar(
                sm_nub,
                cax=cax_n,
                orientation="vertical",
                ticks=niveles_nub
            )

            cbar_nub.set_label("Nubosidad (%)", fontsize=7)
            cbar_nub.ax.tick_params(labelsize=6)

    except Exception as e:
        print(f"⚠ Error creando escala de nubosidad: {e}")

    # ---------------- CONTORNO DE ZONA DE NIEVE ----------------
    # Solo marca el borde probable de nieve. No rellena, no tapa la precipitación.
    if precip is not None and thickness is not None:
        try:
            nieve = xr.where((precip >= 0.2) & (thickness <= 540), 1.0, 0.0)

            cs_nieve = ax.contour(
                lons,
                lats,
                nieve,
                levels=[0.5],
                colors=["#b36b00"],
                linewidths=0.9,
                linestyles="-",
                transform=proj,
                zorder=8
            )

            ax.clabel(
                cs_nieve,
                inline=True,
                fontsize=7,
                fmt={0.5: "NIEVE"}
            )

            print("✔ Contorno de zona de nieve dibujado.")

        except Exception as e:
            print(f"⚠ Error al dibujar contorno de nieve: {e}")

    # ---------------- ESPESOR 500/1000 ----------------
    if thickness is not None:
        try:
            base_min = int(np.floor(float(thickness.min()) / 6) * 6)
            base_max = int(np.ceil(float(thickness.max()) / 6) * 6)
            niveles_th = np.arange(base_min, base_max + 1, 6)

            ax.contour(
                lons,
                lats,
                thickness,
                levels=niveles_th,
                colors="black",
                linewidths=0.6,
                linestyles="--",
                transform=proj,
                zorder=8
            )

            especiales = {
                570: "red",
                550: "green",
                540: "blue",
                528: "yellow"
            }

            for lvl, col in especiales.items():
                if base_min <= lvl <= base_max:
                    c = ax.contour(
                        lons,
                        lats,
                        thickness,
                        levels=[lvl],
                        colors=col,
                        linewidths=1.4,
                        transform=proj,
                        zorder=9
                    )
                    ax.clabel(c, inline=True, fontsize=7, fmt="%.0f")

        except Exception as e:
            print(f"⚠ Error al dibujar espesores: {e}")

    # ---------------- MSLP cada 3 hPa ----------------
    try:
        minp = int(float(mslp.min())) - 3
        maxp = int(float(mslp.max())) + 3
        niveles_mslp = np.arange(minp, maxp + 1, 3)

        cs = ax.contour(
            lons,
            lats,
            mslp,
            levels=niveles_mslp,
            colors="black",
            linewidths=0.9,
            transform=proj,
            zorder=10
        )
        ax.clabel(cs, inline=True, fontsize=7, fmt="%.0f")

    except Exception as e:
        print(f"⚠ Error al dibujar MSLP: {e}")




    # ---------------- VIENTO 10 m > 15 kt ----------------
    if u10 is not None and v10 is not None:
        try:
            print("→ Dibujando viento 10 m > 15 kt...")

            Lon2, Lat2 = np.meshgrid(lons.values, lats.values)

            u_arr = u10.values
            v_arr = v10.values

            spd = np.sqrt(u_arr ** 2 + v_arr ** 2) * 1.94384

            u_plot = np.where(spd < 15.0, np.nan, u_arr)
            v_plot = np.where(spd < 15.0, np.nan, v_arr)

            paso = 6

            ax.barbs(
                Lon2[::paso, ::paso],
                Lat2[::paso, ::paso],
                u_plot[::paso, ::paso],
                v_plot[::paso, ::paso],
                length=5,
                linewidth=0.5,
                transform=proj,
                zorder=11
            )

        except Exception as e:
            print(f"⚠ Error al dibujar viento 10m: {e}")
    else:
        print("⚠ No se pudo dibujar viento 10 m.")

    ciclo_txt = "??Z"
    try:
        partes = archivo_grib.stem.split("_")
        if len(partes) >= 3:
            ciclo_txt = partes[2] + "Z"
    except Exception:
        pass

    titulo = (
        "Departamento Meteorología Militar\n"
        "Superficie y espesores, precipitación, viento fuerte, cielo cubierto y áreas con nieve\n"
        f"Inicio: {init_str}  |  Validez: {valid_str}  (H+{horas_pron}, salida {ciclo_txt})"
    )

    ax.set_title(
        titulo,
        fontsize=11,
        fontweight="bold",
        pad=10,
        color="black"
    )

    plt.savefig(
        archivo_salida,
    dpi=150,
    pad_inches=0.02,
    facecolor=fig.get_facecolor()
    )

    plt.close()

    print(f"✔ Carta generada: {archivo_salida.resolve()}")


if __name__ == "__main__":
    main()
