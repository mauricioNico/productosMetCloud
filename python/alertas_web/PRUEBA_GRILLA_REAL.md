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

## LIMITACIÓN cartográfica obligatoria

Los umbrales están asignados a **unidades puntuales**, NO existe aún
un GeoJSON regional del SMN validado. Este ensayo sólo clasifica celdas
de hasta **120 km** de una unidad con asignación existente en
\`vigilancia/config/unidades.csv\`. Se asigna la región de la unidad
más cercana dentro del radio. Las demás celdas son **SIN REGION**:
no deben colorearse como verdes.

Se usa una cartografía provincial de **referencia** versionada en el
repositorio; reemplazarla por IGN antes de producción.

La clasificación no equivale a un alerta oficial del SMN o de la FAA.
Estos colores son **indicadores experimentales de umbrales numéricos**.
No publicar en \`imagenesmeteorologicas.faa.mil.ar\` hasta validar las
regiones, acumulados y funcionamiento del consenso.

## Artefacto de Github Actions

En Actions abrir \`LAB - Grilla REAL GFS ECMWF (sin publicar)\` y
descargar \`alertas-regionales-reales-EXPERIMENTAL\`.

Contiene:
- \`lluvia_24h.geojson\`, \`lluvia_48h.geojson\`, \`lluvia_72h.geojson\`
- \`viento_24h.geojson\`, \`viento_48h.geojson\`, \`viento_72h.geojson\`
- \`grilla_gfs_ecmwf_real.csv\` (valores diarios equivalentes)
- \`manifest.json\` (cobertura, origen y restricciones)

En el visor v5 se carga **únicamente ese ZIP** para que se dibujen
automáticamente los seis mapas de categorías y las doce cartas de
grilla (dos modelos x tres períodos x dos fenómenos).
