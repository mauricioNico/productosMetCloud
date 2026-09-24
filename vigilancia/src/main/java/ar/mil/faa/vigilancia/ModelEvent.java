package ar.mil.faa.vigilancia;
import java.time.Instant;
public record ModelEvent(String model, Instant runTime, String unit, Phenomenon phenomenon,
                         Instant start, Instant end, AlertLevel level, double maxValue, String valueDescription) {}
