package ar.mil.faa.vigilancia;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
public final class ConfigLoader {
    private ConfigLoader() {}
    public static Map<String, UnitConfig> loadUnits(Path path) throws IOException {
        Map<String, UnitConfig> out = new LinkedHashMap<>();
        List<String> lines = Files.readAllLines(path);
        for (int i = 1; i < lines.size(); i++) {
            if (lines.get(i).isBlank() || lines.get(i).startsWith("#")) continue;
            String[] p = lines.get(i).split(";", -1);
            UnitConfig u = new UnitConfig(p[0], Double.parseDouble(p[1]), Double.parseDouble(p[2]),
                    p[3], p[4], p[5], Boolean.parseBoolean(p[6]), Boolean.parseBoolean(p[7]));
            out.put(u.name(), u);
        }
        return out;
    }
    public static List<ThresholdRule> loadThresholds(Path path) throws IOException {
        List<ThresholdRule> out = new ArrayList<>();
        List<String> lines = Files.readAllLines(path);
        for (int i = 1; i < lines.size(); i++) {
            if (lines.get(i).isBlank() || lines.get(i).startsWith("#")) continue;
            String[] p = lines.get(i).split(";", -1);
            out.add(new ThresholdRule(Phenomenon.valueOf(p[0]), p[1], AlertLevel.valueOf(p[2]),
                    p[3], Integer.parseInt(p[4]), p[5], Double.parseDouble(p[6]), p[7]));
        }
        return out;
    }
}
