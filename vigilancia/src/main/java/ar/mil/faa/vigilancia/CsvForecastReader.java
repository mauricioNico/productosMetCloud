package ar.mil.faa.vigilancia;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.*;
public final class CsvForecastReader {
    private CsvForecastReader() {}
    public static List<ForecastPoint> read(Path path) throws IOException {
        List<ForecastPoint> out = new ArrayList<>();
        if (path == null || !Files.exists(path)) return out;
        List<String> lines = Files.readAllLines(path);
        if (lines.isEmpty()) return out;
        String[] h = lines.get(0).split(";", -1);
        Map<String,Integer> idx = new HashMap<>();
        for (int i=0;i<h.length;i++) idx.put(h[i], i);
        for (int i=1;i<lines.size();i++) {
            String line = lines.get(i);
            if (line.isBlank()) continue;
            String[] p = line.split(";", -1);
            out.add(new ForecastPoint(
                    get(p, idx, "model"), Instant.parse(get(p, idx, "run_time")), get(p, idx, "unidad"),
                    d(p, idx, "lat"), d(p, idx, "lon"), Instant.parse(get(p, idx, "valid_time")),
                    (int)d(p, idx, "lead_h"), d(p, idx, "wind_kmh"), d(p, idx, "gust_kmh"),
                    d(p, idx, "precip_interval_mm"), d(p, idx, "snow_interval_mm"),
                    d(p, idx, "snow_depth_cm"), Boolean.parseBoolean(get(p, idx, "zonda_hint"))));
        }
        return out;
    }
    private static String get(String[] p, Map<String,Integer> idx, String k) {
        Integer i = idx.get(k); return (i == null || i >= p.length) ? "" : p[i];
    }
    private static double d(String[] p, Map<String,Integer> idx, String k) {
        String s = get(p, idx, k); if (s == null || s.isBlank()) return Double.NaN;
        try { return Double.parseDouble(s); } catch (Exception e) { return Double.NaN; }
    }
}
