package ar.mil.faa.vigilancia;
import java.time.Instant;
public record ForecastPoint(String model, Instant runTime, String unit, double lat, double lon,
        Instant validTime, int leadH, double windKmh, double gustKmh,
        double precipIntervalMm, double snowIntervalMm, double snowDepthCm, boolean zondaHint) {
    public double value(String variable) {
        return switch (variable) {
            case "wind_kmh" -> windKmh;
            case "gust_kmh" -> gustKmh;
            case "precip_interval_mm" -> precipIntervalMm;
            case "snow_interval_mm" -> snowIntervalMm;
            case "snow_depth_cm" -> snowDepthCm;
            default -> Double.NaN;
        };
    }
}
