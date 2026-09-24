# Motor Java de vigilancia FAA

Java 17. Lee CSV normalizados de GFS/ECMWF, aplica `config/umbrales.csv`, agrupa eventos contiguos, fusiona por unidad/fenómeno/hora válida y genera salidas de revisión.

```bash
mvn clean test package
java -jar target/vigilancia-faa-1.0.0.jar --gfs gfs.csv --ecmwf ecmwf.csv --output salida
```

No publica ni envía alertas. Ver `../docs/vigilancia-multimodelo.md`.
