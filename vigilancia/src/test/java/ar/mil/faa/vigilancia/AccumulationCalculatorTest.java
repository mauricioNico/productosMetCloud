package ar.mil.faa.vigilancia;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
class AccumulationCalculatorTest {
    private ForecastPoint p(int h, double pp) {
        Instant run=Instant.parse("2026-09-23T00:00:00Z");
        return new ForecastPoint("GFS",run,"X",0,0,run.plusSeconds(h*3600L),h,0,0,pp,Double.NaN,Double.NaN,false);
    }
    @Test void window12From72Uses75To84() {
        List<ForecastPoint> ps=List.of(p(72,100),p(75,1),p(78,2),p(81,3),p(84,4),p(87,50));
        double s=AccumulationCalculator.sumIntervalsEndingInside(ps,Instant.parse("2026-09-26T00:00:00Z"),12,ForecastPoint::precipIntervalMm);
        assertEquals(10,s,1e-9);
    }
    @Test void window24From72UsesThrough96() {
        List<ForecastPoint> ps=new ArrayList<>();
        ps.add(p(72,100)); for(int h=75;h<=96;h+=3) ps.add(p(h,1));
        double s=AccumulationCalculator.sumIntervalsEndingInside(ps,Instant.parse("2026-09-26T00:00:00Z"),24,ForecastPoint::precipIntervalMm);
        assertEquals(8,s,1e-9);
    }
}
