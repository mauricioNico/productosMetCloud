# LABORATORIO: lluvia y viento GFS / ECMWF, no operativo

## Seguridad

Se trabaja exclusivamente sobre la rama
\`test/alertas-web-lluvia-viento\`, con el workflow aislado
\`.github/workflows/probar-grilla-real.yml\`. **No modifica**
\`generar-productos-multimodelo.yml\`, **no** ejecuta push a \`master\`,
**no** usa credenciales para publicar y **no** emite alertas.

## Dominio

Latitud: **20°S–55°S** (de -20 a -55)
Longitud: **85°O–45°O** (de -85 a -45)
Resolución nativa de grilla: **0.25°** en ambos modelos.

El dominio incluye mar y países vecinos para contexto, pero solamente
las celdas terrestres dentro de geometrías provinciales de Argentina
se exportan al CSV cartográfico.

## Procesamiento

1. Descarga GFS NOAA S3 con índices GRIB y rangos HTTP.
2. Descarga ECMWF IFS Open Data para pasos f006/f012/.../f072.
3. Guarda en CSV valores de precipitación con su intervalo GRIB
   **real**, viento a 10 m y ráfagas, cada seis horas.
4. Reconstituye lluvia por intervalo de 6 h:
   - GFS puede mezclar ventanas \`0-fN\` y \`f(N-6)-fN\`.
   - ECMWF entrega acumulados \`0-fN\`.
   - Se normalizan sin sumar dos veces el mismo intervalo.
5. Para cada período 0–24 / 24–48 / 48–72 obtiene
   - lluvia de 24 horas;
   - máximo de ventanas de 12 horas (deslizamiento 6 h);
   - máximo de viento/ráfagas **muestreados** cada 6 h.
6. Aplica los umbrales de \`vigilancia/config/umbrales.csv\` y el
   consenso conservador ya implementado, devolviendo seis capas GeoJSON.
7. Produce \`grilla_gfs_ecmwf_real.csv\` y \`manifest.json\`.

## Regionalización geográfica digitalizada (SMN, julio de 2024)

Se recuperó el documento **“Umbrales para los alertas”**, segunda edición,
julio de 2024, del Servicio Meteorológico Nacional. Las regiones coloreadas
de la **página 4** (lluvia) y **página 6** (viento) se extrajeron del PDF
y se registraron aproximadamente frente al contorno provincial de referencia.

\`python/alertas_web/regiones_smn2024.py\` contiene las máscaras
raster comprimidas para ocho categorías \`PP_R1..PP_R8\` de lluvia
y tres \`WIND_R1..WIND_R3\` de viento.

**Ya no se aplica el radio de 120 km alrededor de las unidades.**
Cada coordenada de malla se asigna a la máscara digitalizada y se
aplican los umbrales de \`vigilancia/config/umbrales.csv\`.

**Precauciones importantes:**

- La fuente es un **mapa PDF raster de baja resolución**, no el archivo
  vectorial regional del SMN; su georreferenciación es aproximada y la
  correspondencia de los bordes debe corroborarse visualmente.
- Un margen de **dos píxeles de imagen original** deja las celdas
  próximas a bordes sin región, en lugar de asignarles un umbral ambiguo.
- La zona coloreada específicamente como **Zonda** no se considera
  automáticamente \`WIND_R1\`: Zonda exige diagnóstico independiente.
- Se utiliza una cartografía provincial **de referencia**, no el dataset
  verificado IGN/Georef. No se incluyen sectores antárticos.
- Los indicadores coloreados **no son alertas oficiales** y el manifest
  sigue con \`publicacion_autorizada=false\`.

En la ejecución de laboratorio \`37985421539\`, de 4.436 celdas
argentinas, 3.387 recibieron clase de lluvia y 3.210 clase de viento.
Las demás permanecen **SIN_REGION_O_DATOS**.

## GIS para inspección

El artefacto incluye dos capas GIS adicionales con geometrías recortadas:
- \`regiones_umbrales_lluvia_smn2024_PRELIMINAR.geojson\`
- \`regiones_umbrales_viento_smn2024_PRELIMINAR.geojson\`

Contienen metadatos \`uso_operativo_autorizado:false\` y estado
\`PRELIMINAR_SIN_VALIDACION_GIS\`. No deben circular como cartografía
oficial del SMN.

## Artefacto de Github Actions

En Actions abrir \`LAB - Grilla REAL GFS ECMWF (sin publicar)\` y
descargar \`alertas-regionales-reales-EXPERIMENTAL\`.

Contiene:
- \`lluvia_24h.geojson\`, \`lluvia_48h.geojson\`, \`lluvia_72h.geojson\`
- \`viento_24h.geojson\`, \`viento_48h.geojson\`, \`viento_72h.geojson\`
- \`grilla_gfs_ecmwf_real.csv\` (valores diarios equivalentes)
- \`manifest.json\` (cobertura, origen y restricciones)

En el visor v6 se carga **únicamente ese ZIP** para que se dibujen
automáticamente los seis mapas de categorías y las doce cartas de
grilla (dos modelos x tres períodos x dos fenómenos).
