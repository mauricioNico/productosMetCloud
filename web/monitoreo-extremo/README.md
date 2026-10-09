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
