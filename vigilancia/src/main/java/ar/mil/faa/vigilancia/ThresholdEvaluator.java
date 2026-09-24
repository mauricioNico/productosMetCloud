package ar.mil.faa.vigilancia;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
public final class ThresholdEvaluator {
    private final List<ThresholdRule> rules;
    private final int horizonHours;
    public ThresholdEvaluator(List<ThresholdRule> rules, int horizonHours) {
        this.rules = List.copyOf(rules); this.horizonHours = horizonHours;
    }
    public List<ModelEvent> evaluate(String model, List<ForecastPoint> allPoints, Map<String, UnitConfig> units) {
        List<ModelEvent> result = new ArrayList<>();
        Map<String, List<ForecastPoint>> byUnit = new LinkedHashMap<>();
        for (ForecastPoint p : allPoints) {
            if (!p.model().equalsIgnoreCase(model)) continue;
            byUnit.computeIfAbsent(p.unit(), k -> new ArrayList<>()).add(p);
        }
        for (var e : byUnit.entrySet()) {
            UnitConfig unit = units.get(e.getKey());
            if (unit == null || !unit.active()) continue;
            List<ForecastPoint> points = e.getValue();
            points.sort(Comparator.comparing(ForecastPoint::validTime));
            if (points.isEmpty()) continue;
            Instant run = points.get(0).runTime();
            for (Phenomenon phenomenon : Phenomenon.values()) {
                String region = unit.regionFor(phenomenon);
                if (region == null || region.equals("UNDEFINED") || region.equals("REVISAR")) {
                    System.out.println("⚠ " + unit.name() + " / " + phenomenon + ": región " + region + ", sin clasificación automática.");
                    continue;
                }
                if (phenomenon == Phenomenon.ZONDA && !unit.zondaApplicable()) continue;
                List<Detection> detections = detect(points, run, phenomenon, region);
                result.addAll(group(model, run, unit.name(), phenomenon, detections));
            }
        }
        return result;
    }
    private List<Detection> detect(List<ForecastPoint> points, Instant run, Phenomenon phenomenon, String region) {
        List<ThresholdRule> rr = rules.stream().filter(r -> r.phenomenon() == phenomenon && r.region().equals(region)).toList();
        if (rr.isEmpty()) return List.of();
        SortedSet<Instant> starts = new TreeSet<>();
        starts.add(run);
        for (ForecastPoint p : points) {
            if (!p.validTime().isBefore(run) && Duration.between(run, p.validTime()).toHours() <= horizonHours) starts.add(p.validTime());
        }
        List<Detection> out = new ArrayList<>();
        for (Instant start : starts) {
            AlertLevel best = AlertLevel.NONE; double bestValue = Double.NaN; int bestWindow = 0; String bestVar = "";
            for (AlertLevel level : List.of(AlertLevel.AMARILLO, AlertLevel.NARANJA, AlertLevel.ROJO)) {
                for (ThresholdRule r : rr) {
                    if (r.level() != level) continue;
                    double value = measured(points, start, r, phenomenon);
                    if (r.matches(value) && level.rank() >= best.rank()) {
                        best = level; bestValue = value; bestWindow = r.windowHours(); bestVar = r.variable();
                    }
                }
            }
            if (best != AlertLevel.NONE) {
                Instant end = start.plusSeconds(Math.max(3, bestWindow) * 3600L);
                out.add(new Detection(start, end, best, bestValue, bestVar));
            }
        }
        return out;
    }
    private double measured(List<ForecastPoint> points, Instant start, ThresholdRule r, Phenomenon phenomenon) {
        if (phenomenon == Phenomenon.ZONDA) {
            ForecastPoint p = at(points, start);
            if (p == null || !p.zondaHint()) return Double.NaN;
            return p.value(r.variable());
        }
        if (r.windowHours() <= 0) {
            ForecastPoint p = at(points, start);
            return p == null ? Double.NaN : p.value(r.variable());
        }
        if (r.variable().equals("snow_depth_cm")) {
            Instant end = start.plusSeconds(r.windowHours() * 3600L);
            double max = Double.NaN;
            for (ForecastPoint p : points) {
                if (p.validTime().isAfter(start) && !p.validTime().isAfter(end) && Double.isFinite(p.snowDepthCm()))
                    max = Double.isFinite(max) ? Math.max(max, p.snowDepthCm()) : p.snowDepthCm();
            }
            return max;
        }
        return AccumulationCalculator.sumIntervalsEndingInside(points, start, r.windowHours(), p -> p.value(r.variable()));
    }
    private ForecastPoint at(List<ForecastPoint> points, Instant t) {
        for (ForecastPoint p : points) if (p.validTime().equals(t)) return p;
        return null;
    }
    private List<ModelEvent> group(String model, Instant run, String unit, Phenomenon phenomenon, List<Detection> detections) {
        if (detections.isEmpty()) return List.of();
        detections.sort(Comparator.comparing(Detection::start));
        List<ModelEvent> out = new ArrayList<>();
        Detection cur = detections.get(0);
        Instant s = cur.start(), e = cur.end(); AlertLevel level = cur.level(); double max = cur.value(); String variable = cur.variable();
        for (int i=1;i<detections.size();i++) {
            Detection n = detections.get(i);
            if (!n.start().isAfter(e.plusSeconds(3*3600L))) {
                if (n.end().isAfter(e)) e = n.end();
                if (n.level().rank() > level.rank()) level = n.level();
                if (!Double.isFinite(max) || n.value() > max) { max = n.value(); variable = n.variable(); }
            } else {
                out.add(new ModelEvent(model, run, unit, phenomenon, s, e, level, max, variable + "=" + fmt(max)));
                s=n.start(); e=n.end(); level=n.level(); max=n.value(); variable=n.variable();
            }
        }
        out.add(new ModelEvent(model, run, unit, phenomenon, s, e, level, max, variable + "=" + fmt(max)));
        return out;
    }
    private String fmt(double v) { return Double.isFinite(v) ? String.format(Locale.US, "%.1f", v) : "N/D"; }
    private record Detection(Instant start, Instant end, AlertLevel level, double value, String variable) {}
}
