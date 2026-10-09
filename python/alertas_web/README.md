# Monitoreo de Eventos Extremos — prototipo cartográfico

**Estado: EXPERIMENTAL. NO PUBLICAR COMO VIGILANCIA REAL.**

Este modulo genera seis capas GeoJSON: lluvia/viento × períodos 0–24,
24–48 y 48–72 horas. Reutiliza el archivo real
\`vigilancia/config/umbrales.csv\` y conserva fuentes/confianza.
No modifica la vigilancia FAA operativa ni publica en GitHub Pages.

## Prueba automatizada en rama de laboratorio

El workflow \`.github/workflows/probar-alertas-web.yml\` corre con
\`push\` sobre \`test/alertas-web-lluvia-viento\`.
Instala \`numpy\` y \`shapely\`, ejecuta \`unittest\`, genera **datos falsos
deterministas** y comprueba que se producen los seis GeoJSON y el manifest.
El artifact del workflow se llama \`alertas-web-simulacion\`.

## Contrato de entradas (NPZ por modelo)

- \`steps\`: plazos en horas (3,6,...,96), estrictamente ascendentes.
- \`interval_hours\`: longitud del intervalo terminado en cada plazo.
- \`lats\` / \`lons\`: centros geográficos de la grilla regular.
- \`run_time\`: misma corrida UTC en los dos modelos para esta primera versión.
- \`precip_interval_mm\`: \`[tiempo, lat, lon]\`, mm incrementales por intervalo.
- \`wind_kmh\`, \`gust_kmh\`: \`[tiempo, lat, lon]\`, km/h.
- \`region_lluvia\`, \`region_viento\`: matrices \`[lat,lon]\` con regiones
  **cartográficas verificadas**, por ejemplo \`PP_R8\` o \`WIND_R2\`.
  Las etiquetas no deben inferirse extendiendo arbitrariamente una estación.

\`--mask\` debe apuntar a un GeoJSON real que permita recortar el análisis
a Argentina sudamericana. Para producción puede obtenerse del IGN/Georef
(https://www.argentina.gob.ar/georef/descarga-de-la-base-completa).
El demo emplea expresamente un rectángulo **ficticio**, no un mapa de Argentina.

## Cómo probar localmente

\`\`\`bash
python -m pip install numpy shapely
python -m unittest discover -s python/alertas_web/tests -v
python python/alertas_web/crear_demo.py --output /tmp/alertas_demo
python python/alertas_web/generar_alertas_web.py \
  --gfs /tmp/alertas_demo/gfs.npz \
  --ecmwf /tmp/alertas_demo/ecmwf.npz \
  --mask /tmp/alertas_demo/mascara_ficticia.geojson \
  --thresholds vigilancia/config/umbrales.csv \
  --simulacion --output /tmp/alertas_salida
\`\`\`

## Pasos pendientes para publicación real

1. Crear la regionalización GIS verificada por fenómeno y provincia.
2. Adaptar la lectura GRIB GFS/ECMWF a los NPZ de este contrato.
   **Los CSV puntuales existentes no sustituyen la grilla espacial.**
3. Validar decodificación de acumulados/ráfagas, calidad y disponibilidad.
4. Reconciliar fechas UTC válidas si las corridas de ambos modelos difieren.
5. Revisar niveles, ventanas y geometría junto a pronosticadores.
6. Añadir publicación al front con chequeo de completitud y antigüedad.

El manifest y todos los features declaran que son simulación cuando se
usa \`--simulacion\`. **\`publicacion_autorizada\` es siempre false
en esta fase**: el workflow no hace despliegue público.

Los valores rojos/naranjas/amarillos de la prueba son sintéticos y
no describen ninguna situación meteorológica real.
