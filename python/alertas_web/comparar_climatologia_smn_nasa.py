#!/usr/bin/env python3
"""Control independiente de NASA POWER/MERRA-2 frente a normales observadas SMN 1991-2020.

El archivo de salida es una auditoría; NO se interpola SMN para crear nuevas
normales y NO se corrige NASA con estaciones sin validación de relieve/altitud.
"""
import json
from pathlib import Path
import numpy as np
from scipy.interpolate import RegularGridInterpolator

root=Path(__file__).resolve().parents[2]
clim=json.loads((root/"web/monitoreo-extremo/climatologia_t2m_1991_2020.json").read_text())
smn=json.loads((root/"web/monitoreo-extremo/normales_temperatura_smn_1991_2020.json").read_text())
lat=np.asarray(clim["lat"],float)
lon=np.asarray(clim["lon"],float)
temps=np.asarray(clim["valores"],float)
assert temps.shape==(12,71,65)
rows=[]
for station in smn["estaciones"]:
    if not (-55<=station["lat"]<=-20 and -85<=station["lon"]<=-45):continue
    normals=station["temp_media_mensual_c"]
    p=np.array([[station["lat"],station["lon"]]],dtype=float)
    nasa=[float(RegularGridInterpolator((lat,lon),t)(p)[0]) for t in temps]
    comparisons=[None if v is None else round(nasa[m]-v,2) for m,v in enumerate(normals)]
    rows.append({"nombre":station["nombre"],"lat":station["lat"],"lon":station["lon"],
                 "altitud_m":station["altitud_m"],"periodo":station["periodo"],
                 "dif_nasa_menos_smn_c":comparisons,
                 "smn_media_mensual_c":normals})
assert len(rows)==99
all_diffs=np.array([v for r in rows for v in r["dif_nasa_menos_smn_c"] if v is not None])
out={"descripcion":"Diferencia climatológica NASA POWER MERRA-2 menos estaciones SMN; valor positivo indica NASA más cálido",
     "periodo":"1991-2020",
     "advertencia":"NO es una evaluación de pronósticos ni una corrección espacial; fuentes con distinta topografía, representación y homogeneidad",
     "estaciones_territorio":len(rows),
     "pares_mes_validos":len(all_diffs),
     "sesgo_promedio_c":round(float(np.mean(all_diffs)),3),
     "error_medio_absoluto_c":round(float(np.mean(abs(all_diffs))),3),
     "p90_abs_c":round(float(np.percentile(abs(all_diffs),90)),3),
     "max_abs_c":round(float(np.max(abs(all_diffs))),3),
     "estaciones":rows}
dst=root/"web/monitoreo-extremo/validacion_smn_nasa.json"
dst.write_text(json.dumps(out,ensure_ascii=False,separators=(",",":"))+"\n")
print({k:v for k,v in out.items() if k!="estaciones"})
print("Mayores discrepancias estación/mes:", sorted(((abs(v),r["nombre"],m+1,v) for r in rows
    for m,v in enumerate(r["dif_nasa_menos_smn_c"]) if v is not None),reverse=True)[:14])
