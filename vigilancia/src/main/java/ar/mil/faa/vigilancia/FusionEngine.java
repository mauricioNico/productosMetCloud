package ar.mil.faa.vigilancia;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
public final class FusionEngine {
    public List<FusedEvent> fuse(List<ModelEvent> gfs, List<ModelEvent> ecmwf) {
        List<FusedEvent> out = new ArrayList<>();
        Set<ModelEvent> usedE = new HashSet<>();
        for (ModelEvent g : gfs) {
            ModelEvent best = ecmwf.stream().filter(e -> !usedE.contains(e))
                    .filter(e -> sameKey(g,e) && compatibleTime(g,e))
                    .min(Comparator.comparingLong(e -> Math.abs(Duration.between(g.start(), e.start()).toHours()))).orElse(null);
            if (best == null) out.add(single(g, true));
            else {
                usedE.add(best);
                Instant start = g.start().isBefore(best.start()) ? g.start() : best.start();
                Instant end = g.end().isAfter(best.end()) ? g.end() : best.end();
                boolean overlap = !g.end().isBefore(best.start()) && !best.end().isBefore(g.start());
                Confidence confidence = overlap && g.level() == best.level() ? Confidence.ALTA : Confidence.MEDIA;
                AlertLevel common = AlertLevel.min(g.level(), best.level());
                String obs = g.level() == best.level() ? "Coincidencia multimodelo." : "Los modelos difieren en intensidad.";
                out.add(new FusedEvent(g.unit(), g.phenomenon(), start, end, g, best, common, confidence, obs));
            }
        }
        for (ModelEvent e : ecmwf) if (!usedE.contains(e)) out.add(single(e, false));
        out.sort(Comparator.comparing(FusedEvent::start).thenComparing(FusedEvent::unit));
        return out;
    }
    private boolean sameKey(ModelEvent a, ModelEvent b) { return a.unit().equals(b.unit()) && a.phenomenon() == b.phenomenon(); }
    private boolean compatibleTime(ModelEvent a, ModelEvent b) {
        boolean overlap = !a.end().isBefore(b.start()) && !b.end().isBefore(a.start());
        long dh = Math.abs(Duration.between(a.start(), b.start()).toHours());
        return overlap || dh <= 6;
    }
    private FusedEvent single(ModelEvent e, boolean gfs) {
        return new FusedEvent(e.unit(), e.phenomenon(), e.start(), e.end(), gfs ? e : null, gfs ? null : e,
                e.level(), Confidence.BAJA, "Evaluación multimodelo incompleta: solo " + e.model() + " alcanza criterio.");
    }
}
