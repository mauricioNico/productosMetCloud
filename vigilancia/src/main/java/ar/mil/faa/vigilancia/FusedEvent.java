package ar.mil.faa.vigilancia;
import java.time.Instant;
public record FusedEvent(String unit, Phenomenon phenomenon, Instant start, Instant end,
                         ModelEvent gfs, ModelEvent ecmwf, AlertLevel suggestedLevel,
                         Confidence confidence, String observation) {}
