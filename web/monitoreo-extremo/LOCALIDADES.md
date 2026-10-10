# Localidades georreferenciadas — visor Monitoreo Extremo

La capa se basa en el catálogo **GeoRef Argentina**, listado oficial de **localidades** en coordenadas geográficas WGS84 (longitud/latitud). No usa Google Maps ni consulta a GeoRef desde el navegador: el sitio publica junto al HTML una copia compacta y versionada en `localidades-georef.json`.

- Fuente de descarga completa: https://apis.datos.gob.ar/georef/api/v2.0/localidades.json
- Documentación oficial: https://www.argentina.gob.ar/georef/descarga-de-la-base-completa
- Captura inicial: 2026-10-10 UTC, **4.028** registros válidos distribuidos en 24 jurisdicciones.
- Identificadores, nombres, provincias, coordenadas y categorías provienen de GeoRef. La tabla no contiene cifras de población. Algunos registros cercanos representan una misma entidad/localidad: solo se ocultan duplicados muy próximos de categoría «Entidad» en pantalla, conservando el original en el JSON.

## Funcionalidades

1. **Localidades:** habilita/deshabilita puntos, grupos y etiqueta de localidad seleccionada sin afectar la cartografía ni la meteorología.
2. **Etiquetas según zoom:** muestra nombres progresivamente con prevención de superposición. A escala regional predomina la agrupación por celdas de pantalla; al ampliar se ven localidades individuales y más nombres.
3. **Búsqueda:** busca por nombre y provincia, sin diferenciar tildes; ofrece hasta 9 sugerencias. Seleccionar una centra los **cuatro** mapas del día y conserva la selección al cambiar de día.
4. **Interacción:** clic en una agrupación acerca el mapa correspondiente; clic en un punto selecciona la localidad. Cada mapa conserva zoom independiente.
5. **Coordenadas:** usa la misma transformación `proj()` del visor Lambert; los marcadores se posicionan y se actualizan tras cada zoom/desplazamiento, no se mueven sobre la base de un bitmap fijo.

**Interpretación meteorológica:** los marcadores identifican localidades, no son estaciones ni pronósticos puntualizados. Los valores GFS/ECMWF son datos del modelo a resolución de grilla, no observaciones. El visor es experimental, no una fuente de alertas oficiales.

## Actualización del archivo

La descarga/reproducción está en `tools/actualizar_localidades_georef.py`. Verifica un mínimo de localidades, las 24 jurisdicciones, IDs, coordenadas geográficas y documenta SHA-256 del archivo de origen. La actualización se puede realizar con un entorno que tenga conexión a GeoRef y luego versionar el JSON. La captura inicial se validó en GitHub Actions con una herramienta temporal que fue retirada al finalizar las pruebas; el workflow multimodelo no fue modificado.

La publicación `.github/workflows/generar-zip-alertas-web.yml` valida y copia `localidades-georef.json` y `localidades-layer.js` a GitHub Pages, junto con la cartografía y las capas meteorológicas.

Comprobación estática:

```bash
node web/monitoreo-extremo/tests/localidades.test.cjs
node --check web/monitoreo-extremo/localidades-layer.js
```
