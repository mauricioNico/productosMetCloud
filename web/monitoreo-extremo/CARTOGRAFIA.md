# Cartografía base de Monitoreo Extremo

El visor usa una sola transformación y encuadre para vigilancia y precipitación GFS/ECMWF. Todos los vértices de alertas, provincias, países y puntos de grilla se dibujan con Lambert conforme cónica esférica: meridiano central 64°O, origen 38°S, paralelos estándar 25°S/50°S. El dominio 86°O–44°O / 56°S–19°S se ajusta con una única escala y margen, sin estirar ejes por separado. Los tooltips usan la transformación inversa. Es una proyección de presentación, no una transformación oficial POSGAR.

## Fuentes reproducibles

- Países vecinos y costas: Natural Earth **1:10m**, dominio público, `ne_10m_admin_0_countries.geojson`, [revisión ca96624a56bd078437bca8184e78163e5039ad19](https://github.com/nvkelso/natural-earth-vector/blob/ca96624a56bd078437bca8184e78163e5039ad19/geojson/ne_10m_admin_0_countries.geojson). Incluye Chile, Bolivia, Paraguay, Brasil, Uruguay y Perú. SHA-256 del original: `239eec57ac17f100a11e2536cffc56752c318b50ae765b0918ff7aab4ce8f255`.
- Argentina y sus 24 jurisdicciones: [Georef, provincias.geojson](https://apis.datos.gob.ar/georef/api/provincias.geojson), con `fuente: IGN`, descargado el **10 de octubre de 2026 UTC**. La fuente sin modificaciones se conserva en `web/cartografia/provincias_ign.geojson`, SHA-256 `b086852064c26813d9f607c82c91b4e74e18ea83fd21993ddedd473cf8495af5`. [Documentación oficial sobre las fuentes](https://datosgobar.github.io/georef-ar-api/georef-api-data/).
- El contorno argentino es la unión de esas jurisdicciones, de modo que las provincias y el borde nacional coinciden exactamente. Se recorta únicamente al dominio visible; no se simplifican vértices ni se desplazan coordenadas.
- El original de Tierra del Fuego contiene anillos anidados inválidos. `shapely.make_valid` se aplica solo a la representación derivada antes del recorte; el archivo oficial original no se modifica. Las pequeñas superposiciones provinciales de la fuente (0,01706046 grados cuadrados, aproximadamente 0,0061 % del área) se conservan. Natural Earth e IGN tienen escalas y trazados diferentes; no se inventan fronteras para ajustar las diferencias entre fuentes.

La cartografía derivada está en `base-cartography.js`, junto al visor; el workflow **experimental** la copia al sitio estático. No depende de consultas a `master` ni de servidores de mosaicos. Los países vecinos usan tonos suaves; las provincias, líneas finas; Argentina, un contorno destacado. Los puntos de precipitación siguen sin malla superpuesta.

## Separación de la meteorología

Los GeoJSON de alertas conservan todas sus coordenadas y propiedades. Solo se proyectan al dibujarse; no se recortan ni recalculan. Los tooltips seleccionan los polígonos originales incluso cuando su geometría no coincide exactamente con la nueva costa de referencia.

Los cuatro `referencia_provincias_*.geojson` utilizados por el clasificador **permanecen intactos**: modificar esa máscara alteraría el procesamiento meteorológico. Tampoco cambian umbrales, regiones, cálculos, navegación, identidad FAA ni formato de publicación. `generar-productos-multimodelo.yml` no se modifica.

## Regeneración

Con Python, Shapely y acceso HTTPS, desde la raíz:

```sh
curl -fsSL https://raw.githubusercontent.com/nvkelso/natural-earth-vector/ca96624a56bd078437bca8184e78163e5039ad19/geojson/ne_10m_admin_0_countries.geojson -o /tmp/natural-earth.geojson
python web/monitoreo-extremo/tools/build_cartography.py --natural-earth /tmp/natural-earth.geojson
```

El generador verifica los hashes de ambas fuentes antes de generar. No descarga una versión nueva de IGN silenciosamente ni reemplaza la máscara meteorológica.

## Validación

```sh
node web/monitoreo-extremo/tests/geography.test.cjs
python web/monitoreo-extremo/tests/topology.py
python web/monitoreo-extremo/tests/visual.py \
  --zip /ruta/monitoreo-extremo.zip \
  --metadata /ruta/publicacion.json \
  --out salidas/cartografia-pruebas
```

La prueba geográfica comprueba el dominio completo, la transformación inversa, seis localidades reales de control, un punto del Atlántico y las fuentes. La prueba topológica comprueba la validez de las 24 geometrías derivadas y la coincidencia exacta de la unión provincial con el contorno nacional.

La prueba visual levanta un servidor temporal y usa Chromium/Playwright. Carga el ZIP a través de las mismas solicitudes automáticas del visor, verifica seis capas, cuatro mapas por día, navegación y tooltips de precipitación y de polígonos de vigilancia. Compara todas las coordenadas y propiedades originales antes y después de navegar. `--baseline-html` permite comparar un HTML original; `--synthetic` identifica explícitamente pruebas sintéticas.

Las [capturas y resultados de revisión](../../docs/cartografia-monitoreo-extremo/README.md) usan el ZIP real publicado del **9 de octubre de 2026, 12 UTC**, con **26.616 registros y seis capas**. No se desplegó el sitio ni se integró la rama a `master`.
