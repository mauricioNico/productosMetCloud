# Prueba independiente: grilla meteorologica REAL

Se ejecuta en \`test/alertas-web-lluvia-viento\`, sin modificar el
workflow productivo \`.github/workflows/generar-productos-multimodelo.yml\`.

## Que hace

- Descarga de **NOAA GFS 0.25°** (sólo mensajes U/V 10 m, APCP y ráfagas
  cuando disponibles) usando byte ranges e índices S3.
- Descarga de **ECMWF IFS Open Data 0.25°** con 10u, 10v, tp y ráfaga opcional.
- Extrae grillas del recorte **lat -40 a -30, lon -68 a -54**.
- Extrae 24, 48 y 72 horas pronosticadas, sin confundir horas de validez
  con intervalos de acumulación.
- Genera CSV compatible con \`visor_alertas_grilla_provincias.html\` y
  un JSON por modelo con los metadatos GRIB de precipitación.
- Une ambos CSV en \`grilla_gfs_ecmwf_real.csv\` para carga en el visor.

## Interpretacion correcta

El fichero de prueba **NO genera niveles verde/amarillo/naranja/rojo**.
Es una prueba de lectura de **puntos reales** de grilla, antes de asignar
regiones de umbral cartográficas validadas. Campos \`precip_interval_mm\`
y \`precip_window_h\` representan el período **real del GRIB**, no
necesariamente el rango 0-24, 24-48 o 48-72. Cuando no es posible
validar su ventana, se deja precipitación en blanco.

Tanto f024 como f048 y f072 indican **hora válida**. Los vientos son
valores instantáneos válidos a esa hora, no máximo del intervalo 24 h.

## Como ejecutar

Abrir la pestaña Actions del repositorio y buscar
\`LAB - Grilla REAL GFS ECMWF (sin publicar)\`.
También se ejecuta una sola vez automáticamente al actualizar su
definición en la rama de laboratorio.

Descargar el artifact \`grilla-real-gfs-ecmwf-experimental\` y
descomprimirlo. En el visor usar **Datos meteorológicos de grilla
(CSV)** y seleccionar \`grilla_gfs_ecmwf_real.csv\`.
Acercar el mapa para ver puntos de 0.25° y hacer clic.

## Seguridad

No existe commit a la rama principal, no hay programación periódica,
no usa secrets, no realiza push ni despliegue y el permiso de
\`GITHUB_TOKEN\` es read-only. Archivos GRIB temporales se borran al
extraer datos y solamente CSV/JSON se conservan en artifacts.

Si un modelo no publica un parámetro compatible, su job falla con
mensaje legible; el informe no se considera validado. El archivo de
resultados no reemplaza la vigilancia aeronáutica oficial.
