package ar.mil.faa.vigilancia;
public record ThresholdRule(Phenomenon phenomenon, String region, AlertLevel level,
                            String variable, int windowHours, String operator, double threshold, String group) {
    public boolean matches(double value) {
        if (!Double.isFinite(value)) return false;
        return switch (operator) { case ">" -> value > threshold; default -> value >= threshold; };
    }
}
