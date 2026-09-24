package ar.mil.faa.vigilancia;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;
public final class Main {
    public static void main(String[] args) throws Exception {
        System.setProperty("java.awt.headless", "true");
        Map<String,String> a = parse(args);
        Path gfs = path(a.get("gfs")); Path ecmwf = path(a.get("ecmwf"));
        Path unitsPath = Path.of(a.getOrDefault("units", "vigilancia/config/unidades.csv"));
        Path thresholdsPath = Path.of(a.getOrDefault("thresholds", "vigilancia/config/umbrales.csv"));
        Path output = Path.of(a.getOrDefault("output", "salidas_vigilancia"));
        int horizon = Integer.parseInt(a.getOrDefault("horizon", "72"));
        List<ForecastPoint> gfsPoints = CsvForecastReader.read(gfs);
        List<ForecastPoint> ecmwfPoints = CsvForecastReader.read(ecmwf);
        if (gfsPoints.isEmpty() && ecmwfPoints.isEmpty()) throw new IllegalStateException("No hay datos GFS ni ECMWF para evaluar.");
        Map<String, UnitConfig> units = ConfigLoader.loadUnits(unitsPath);
        List<ThresholdRule> rules = ConfigLoader.loadThresholds(thresholdsPath);
        ThresholdEvaluator ev = new ThresholdEvaluator(rules, horizon);
        List<ModelEvent> ge = ev.evaluate("GFS", gfsPoints, units);
        List<ModelEvent> ee = ev.evaluate("ECMWF", ecmwfPoints, units);
        List<FusedEvent> fused = new FusionEngine().fuse(ge, ee);
        Instant gRun = gfsPoints.isEmpty()?null:gfsPoints.get(0).runTime();
        Instant eRun = ecmwfPoints.isEmpty()?null:ecmwfPoints.get(0).runTime();
        System.out.println("==============================================");
        System.out.println("VIGILANCIA AUTOMATICA FAA - 72 H");
        System.out.println("==============================================");
        System.out.println("GFS: " + (gRun==null?"NO DISPONIBLE":gRun));
        System.out.println("ECMWF: " + (eRun==null?"NO DISPONIBLE":eRun));
        for (FusedEvent e : fused) System.out.printf("%s | %s | %s -> %s | nivel=%s | confianza=%s%n", e.unit(), e.phenomenon(), e.start(), e.end(), e.suggestedLevel(), e.confidence());
        System.out.println("Eventos para revisión: " + fused.size());
        if (fused.isEmpty()) { System.out.println("No se detectaron eventos que alcancen los umbrales configurados."); return; }
        OutputWriter.write(output, fused, gRun, eRun, horizon);
        System.out.println("Producto generado en: " + output.toAbsolutePath());
    }
    private static Path path(String s) { return s==null||s.isBlank()?null:Path.of(s); }
    private static Map<String,String> parse(String[] args) {
        Map<String,String> m=new HashMap<>();
        for(int i=0;i<args.length;i++) if(args[i].startsWith("--")) {
            String k=args[i].substring(2); String v=(i+1<args.length&&!args[i+1].startsWith("--"))?args[++i]:"true"; m.put(k,v);
        }
        return m;
    }
}
