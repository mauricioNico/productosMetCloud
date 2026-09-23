package ar.mil.faa.vigilancia;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.function.ToDoubleFunction;
public final class AccumulationCalculator {
    private AccumulationCalculator() {}
    public static double sumIntervalsEndingInside(List<ForecastPoint> points, Instant start,
                                                   int windowHours, ToDoubleFunction<ForecastPoint> valueFn) {
        Instant end = start.plus(windowHours, ChronoUnit.HOURS);
        double total = 0.0; boolean found = false;
        for (ForecastPoint p : points) {
            if (p.validTime().isAfter(start) && !p.validTime().isAfter(end)) {
                double v = valueFn.applyAsDouble(p);
                if (Double.isFinite(v)) { total += v; found = true; }
            }
        }
        return found ? total : Double.NaN;
    }
}
