# Monitoreo Extremo — GitHub Pages (producto experimental)

La página es generada automáticamente por `.github/workflows/generar-zip-alertas-web.yml`, en la rama `master`.

- HTML: `web/monitoreo-extremo/index.html`
- Dirección esperada: `https://mauricionico.github.io/productosMetCloud/`
- Datos publicados: `/datos/monitoreo-extremo.zip` y `/datos/publicacion.json`
- Fuente: GRIB reales GFS y ECMWF a 0.25°, dominio 20°S–55°S / 85°O–45°O
- Capas: lluvia y viento en 24, 48 y 72 horas, umbrales regionales provisionales.
- ZIP en Actions: `alertas-regionales-reales-EXPERIMENTAL` (se conserva).
- El navegador carga el ZIP publicado automáticamente al abrir la página: no requiere selección manual.
- El visor conserva la estética azul FAA, favicon, y navegación Día 1/2/3.
- La página indica el ciclo de la fuente y fecha de la última publicación exitosa.

## Habilitación única de GitHub Pages

En **Settings → Pages → Build and deployment → Source**, seleccionar **GitHub Actions**.
Después, ejecutar el workflow manualmente desde **Actions → Monitoreo extremo → Run workflow** en `master`, o esperar la próxima ejecución automática.

**Importante:** `actions/configure-pages` con el `GITHUB_TOKEN` predeterminado **no puede habilitar Pages por primera vez**. Si el job `publicar_pages` falla allí, hay que habilitarlo una sola vez en Settings. No requiere crear repositorios adicionales.

## Seguridad

- El trabajo `publicar_pages` depende del éxito total de `combinar` (que depende de GFS y ECMWF).
- Comprueba que el CSV y el manifiesto compartan ciclo, que estén los dos modelos y seis capas, y que `publicacion_autorizada=false` antes de reemplazar el sitio.
- Si falla GFS, ECMWF, validación o publicación, **no se publica un ZIP nuevo**; GitHub Pages conserva la última versión publicada satisfactoriamente (excepto que un administrador cambie el sitio).
- El sitio es público, pero **no emite alertas oficiales**.
- El workflow productivo `generar-productos-multimodelo.yml` no se modifica.

Los umbrales regionales proceden de mapas SMN 2024 digitalizados desde PDF y requieren validación GIS oficial.

## Anomalía de temperatura a 2 m (desarrollo 24/48/72 horas)

En cada día del visor aparecen dos mapas de anomalía térmica, uno GFS y otro ECMWF, con igual cartografía, zoom y búsqueda GeoRef que los mapas de vigilancia y lluvia.

Se extrae T2m real de ambos modelos para f006,f012,...,f072. Para cada período 0–24,24–48,48–72 horas se promedian cuatro pronósticos separados seis horas. Este promedio es **una aproximación de la media del intervalo de 24 h**, no la integración horaria exacta. Se compara con temperatura media climatológica mensual NASA POWER (basada en MERRA-2, período 1991–2020), interpolada espacialmente y entre centros de mes para la fecha de la ventana.

- Anomalía (°C) = media prevista T2m (°C) − normal climatológica gridded (°C).
- Colores azules corresponden a valores negativos y anaranjados/rojos a positivos. **No hay niveles oficiales de alerta térmica ni umbrales SMN aplicados a esos colores**.
- La climatología en grilla se generó descargando y verificando 16 bloques regionales de NASA POWER; cada mosaico y la captura tienen metadatos de origen y SHA256.
- Fuente observacional nacional adicional: *Servicio Meteorológico Nacional (2023), Estadísticas Climatológicas Normales: República Argentina – Período 1991–2020* (https://repositorio.smn.gob.ar/handle/20.500.12160/2506). Se extrajeron 105 estaciones, 99 dentro del dominio y seis en Antártida; nueve normales mensuales son S/D y se conservan nulas. Trece estaciones cuentan con un período inferior a 1991–2020: el campo \`periodo\` individual se conserva.
- Archivo de las normales SMN: \`normales_temperatura_smn_1991_2020.json\`. La validación \`validacion_smn_nasa.json\` contrasta NASA vs SMN en 1.179 pares estación-mes: sesgo espacial promedio −0,248 °C, diferencia absoluta media 1,177 °C, y máximo absoluto 16,33 °C. Los máximos muestran que la topografía, la altitud y las fuentes de reanálisis **no son intercambiables con observaciones puntuales**.
- **No se ha realizado corrección del sesgo de cada modelo** ni ajuste altitudinal ni atribución de anomalías al fenómeno ENOS. La comparación de 72 horas no basta para atribuir influencia causal al Niño/La Niña.
- Las seis capas regionales previas lluvia/viento se mantienen iguales y sus umbrales no intervienen en el cálculo de anomalías.

**Fuente climatológica del mapa:** NASA POWER T2M/MERRA-2 1991–2020.
**Control observacional complementario:** SMN normales 1991–2020 por estación; no se presentan como una superficie continua oficial.
