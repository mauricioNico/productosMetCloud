# Pruebas visuales de cartografía

Datos reales de [Monitoreo Extremo](https://mauricionico.github.io/productosMetCloud/datos/monitoreo-extremo.zip), ciclo **2026-10-09 12 UTC**, publicados **2026-10-09 23:58:55 UTC**. Se conservan los metadatos en [publicacion.json](publicacion.json). ZIP SHA-256: `2f3a16329afb931b0f4bee4ae83e0eab5afc4c4ac05beb319a66f5eafeff4180`.

| Período | Antes, master cb61b57 | Después, Natural Earth + IGN |
|---|---|---|
| Día 1 | [captura](before/day-1.png) | [captura](day-1.png) |
| Día 2 | [captura](before/day-2.png) | [captura](day-2.png) |
| Día 3 | [captura](before/day-3.png) | [captura](day-3.png) |

[Tooltip de precipitación](tooltip.png). Cada captura incluye los mapas de vigilancia por lluvia/viento y precipitación GFS/ECMWF; los resultados muestran 26.616 registros, seis capas y la misma corrida. Las capturas anteriores y posteriores usan exactamente el mismo ZIP real.

Validación ejecutada:

- Control geográfico de seis localidades de los países requeridos y exclusión del Atlántico; dominio completo dentro del encuadre; error máximo de inversión inferior a `4e-14` grados.
- 24 jurisdicciones IGN con geometrías derivadas válidas; unión provincial idéntica al contorno argentino. El original de Tierra del Fuego requiere reparación de anillos anidados para dibujar; se preserva el original oficial. Las pequeñas superposiciones de origen no se corrigen arbitrariamente.
- Carga automática, tres días, cuatro mapas por día, navegación hacia adelante/atrás y tooltips meteorológicos y de vigilancia.
- Todas las coordenadas y propiedades de los polígonos de alerta coinciden con el ZIP original después de la carga y navegación. Sin errores JavaScript.
- Motor Java: **13 pruebas aprobadas**, ninguna omitida; JAR compilado con Java 17.
- Workflow productivo multimodelo, cálculos, umbrales y máscaras meteorológicas sin cambios.

Resultados automatizados: [visual](results.json), [topología](geography-results.json). Fuentes, hashes, limitaciones de escala y comandos reproducibles: [CARTOGRAFIA.md](../../web/monitoreo-extremo/CARTOGRAFIA.md).

La prueba valida el visor local cargando una copia de la publicación real a través del flujo automático. No prueba un despliegue nuevo en GitHub Pages. La rama queda para revisión mediante Pull Request, sin integración a `master`.
