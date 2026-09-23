# Vigilancia meteorológica multimodelo GFS + ECMWF

## Objetivo

Este módulo agrega una **vigilancia meteorológica automática a 72 h** como producto de apoyo a la decisión. No envía correos, no usa Selenium, no publica productos y no emite alertas oficiales. Si detecta superaciones de umbral, genera PNG/CSV/JSON para revisión del pronosticador.

## Arquitectura

- El workflow productivo `generar-productos-gfs.yml` queda intacto.
- El nuevo `generar-productos-multimodelo.yml` es exclusivamente manual (`workflow_dispatch`) durante la etapa de prueba.
- GFS conserva f084 por defecto; la corrida multimodelo activa f096 mediante variables de entorno.
- ECMWF IFS Open Data 0.25° se descarga hasta f096; las cartas se generan solo en f012/24/36/48/60/72/84.
- Python lee GRIB y normaliza series; Java 17 evalúa umbrales y fusiona modelos.

## Horizonte 72 h y f096

Un evento debe **iniciar dentro de +72 h**. Sin embargo, una ventana de acumulación de 24 h que comienza en f072 necesita datos hasta f096. Por ello se descargan cuatro pasos extra para el detector, sin crear cartas adicionales.

### Regla de intervalos

Si la precipitación `f075` corresponde al intervalo que termina en f075, la ventana f072–f084 suma **f075 + f078 + f081 + f084**. La ventana f072–f096 suma **f075 ... f096**. El motor Java lo implementa mediante `AccumulationCalculator.sumIntervalsEndingInside`.

## Configuración externa

`vigilancia/config/umbrales.csv` contiene los umbrales regionales y permite múltiples condiciones OR como filas independientes. `vigilancia/config/unidades.csv` contiene la asignación unidad→región.

La asignación regional fue preparada a partir de los mapas gráficos del documento SMN aportado al proyecto y debe ser revisada operacionalmente antes de considerarse definitiva. Donde no existe una asignación inequívoca se utiliza `REVISAR` o `UNDEFINED`. **Marambio permanece UNDEFINED** y no hereda criterios continentales.

## Zonda

No se diagnostica Zonda por velocidad. Los extractores colocan `zonda_hint=false`. Los umbrales Zonda solo se evalúan cuando una futura fuente/diagnóstico marque `zonda_hint=true`.

## Confianza multimodelo

- **ALTA**: ambos modelos superan umbral, los períodos se superponen y tienen el mismo nivel.
- **MEDIA**: ambos modelos detectan el evento pero difieren en intensidad o desplazamiento temporal.
- **BAJA**: solo uno de los modelos alcanza criterio. El caso se conserva para revisión.

El nivel común cuando ambos modelos difieren es el menor nivel compartido (por ejemplo GFS naranja + ECMWF amarillo → sugerido amarillo) y la discrepancia queda explícita.

## Ejecución local del motor

```bash
mvn -f vigilancia/pom.xml clean test package
java -jar vigilancia/target/vigilancia-faa-1.0.0.jar \
  --gfs datos_vigilancia_gfs.csv \
  --ecmwf datos_vigilancia_ecmwf.csv \
  --units vigilancia/config/unidades.csv \
  --thresholds vigilancia/config/umbrales.csv \
  --horizon 72 \
  --output vigilancia_resultado
```

Si no existen eventos, el proceso termina con código 0 y no crea la carpeta de salida.

## Productos

Cuando hay eventos:
- `resumen_vigilancia.png`
- `eventos_vigilancia.csv`
- `eventos_vigilancia.json`

El PNG incluye la leyenda: **“Producto automático de apoyo a la decisión. La emisión de un alerta queda sujeta al análisis meteorológico operativo.”**

## Limitaciones conocidas

1. La regionalización unidad→umbral debe revisarse contra la cartografía oficial antes de pasar a producción.
2. Marambio no tiene umbral continental asignado.
3. Zonda requiere un diagnóstico externo futuro.
4. La disponibilidad/codificación de campos ECMWF (`10fg`, `sf`) se valida durante la primera corrida real del workflow manual.
5. El workflow multimodelo no tiene cron hasta superar las pruebas operativas.
