# -*- coding: utf-8 -*-
"""Selección de proyección para dominios regionales de altas latitudes.

La lógica está pensada para NO alterar el dominio operativo normal del
workflow multimodelo (aprox. 20S-80S). Solo activa proyección polar cuando
el área está realmente enfocada en altas latitudes.

Ejemplos:
- 20S-80S  -> PlateCarree (flujo normal, sin cambios)
- 45S-85S  -> SouthPolarStereo
- 40N-80N  -> NorthPolarStereo
"""

import cartopy.crs as ccrs

UMBRAL_BORDE_POLAR = 70.0
UMBRAL_CENTRO_POLAR = 55.0


def normalizar_longitud(lon):
    """Normaliza una longitud a [-180, 180)."""
    lon = float(lon)
    return ((lon + 180.0) % 360.0) - 180.0


def limites_longitud_mapa(left, right):
    """Devuelve límites normalizados adecuados para set_extent."""
    return normalizar_longitud(left), normalizar_longitud(right)


def dominio_polar_enfocado(top, bottom):
    """True cuando el dominio está centrado suficientemente cerca del polo.

    Se exige:
    - ambos límites en el mismo hemisferio;
    - al menos un borde a 70° o más de latitud absoluta;
    - latitud media absoluta >= 55°.

    Esto preserva el dominio multimodelo habitual 20S-80S porque su
    latitud media es 50S.
    """
    top = float(top)
    bottom = float(bottom)

    mismo_hemisferio = (top < 0.0 and bottom < 0.0) or (top > 0.0 and bottom > 0.0)
    if not mismo_hemisferio:
        return False

    borde_max = max(abs(top), abs(bottom))
    centro = abs((top + bottom) / 2.0)

    return borde_max >= UMBRAL_BORDE_POLAR and centro >= UMBRAL_CENTRO_POLAR


def elegir_proyeccion(top, bottom, left, right):
    """Retorna (map_crs, data_crs, polar, hemisferio, left_map, right_map)."""
    data_crs = ccrs.PlateCarree()

    left_map, right_map = limites_longitud_mapa(left, right)

    if not dominio_polar_enfocado(top, bottom):
        return data_crs, data_crs, False, "", float(left), float(right)

    # Centro longitudinal teniendo en cuenta dominios expresados 0..360.
    if right_map < left_map:
        right_aux = right_map + 360.0
        central_lon = (left_map + right_aux) / 2.0
        if central_lon > 180.0:
            central_lon -= 360.0
    else:
        central_lon = (left_map + right_map) / 2.0

    centro_lat = (float(top) + float(bottom)) / 2.0

    if centro_lat < 0:
        map_crs = ccrs.SouthPolarStereo(central_longitude=central_lon)
        hemisferio = "SUR"
    else:
        map_crs = ccrs.NorthPolarStereo(central_longitude=central_lon)
        hemisferio = "NORTE"

    return map_crs, data_crs, True, hemisferio, left_map, right_map
