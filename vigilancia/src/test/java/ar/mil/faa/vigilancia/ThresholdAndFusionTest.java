package ar.mil.faa.vigilancia;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
class ThresholdAndFusionTest {
    private static final Instant RUN=Instant.parse("2026-09-23T00:00:00Z");
    private ForecastPoint p(String model,int h,double wind,double gust,boolean zonda){return new ForecastPoint(model,RUN,"X",0,0,RUN.plusSeconds(h*3600L),h,wind,gust,0,0,Double.NaN,zonda);}
    private UnitConfig u(String region, boolean zonda){return new UnitConfig("X",0,0,"UNDEFINED",region,"UNDEFINED",zonda,true);}
    @Test void exactThresholdCounts(){ assertTrue(new ThresholdRule(Phenomenon.VIENTO,"W",AlertLevel.AMARILLO,"gust_kmh",0,">=",65,"A").matches(65)); }
    @Test void gustCanTriggerWind(){
        var r=List.of(new ThresholdRule(Phenomenon.VIENTO,"W",AlertLevel.AMARILLO,"wind_kmh",0,">=",55,"A"),new ThresholdRule(Phenomenon.VIENTO,"W",AlertLevel.AMARILLO,"gust_kmh",0,">=",65,"B"));
        var ev=new ThresholdEvaluator(r,72).evaluate("GFS",List.of(p("GFS",3,20,70,false)),Map.of("X",u("W",false)));
        assertFalse(ev.isEmpty());
    }
    @Test void sustainedCanTriggerWind(){
        var r=List.of(new ThresholdRule(Phenomenon.VIENTO,"W",AlertLevel.AMARILLO,"wind_kmh",0,">=",55,"A"),new ThresholdRule(Phenomenon.VIENTO,"W",AlertLevel.AMARILLO,"gust_kmh",0,">=",65,"B"));
        var ev=new ThresholdEvaluator(r,72).evaluate("GFS",List.of(p("GFS",3,60,20,false)),Map.of("X",u("W",false)));
        assertFalse(ev.isEmpty());
    }
    @Test void sameYellowIsHighConfidence(){
        ModelEvent g=new ModelEvent("GFS",RUN,"X",Phenomenon.VIENTO,RUN.plusSeconds(3*3600),RUN.plusSeconds(6*3600),AlertLevel.AMARILLO,70,"gust=70");
        ModelEvent e=new ModelEvent("ECMWF",RUN,"X",Phenomenon.VIENTO,RUN.plusSeconds(3*3600),RUN.plusSeconds(6*3600),AlertLevel.AMARILLO,72,"gust=72");
        FusedEvent f=new FusionEngine().fuse(List.of(g),List.of(e)).get(0);
        assertEquals(Confidence.ALTA,f.confidence()); assertEquals(AlertLevel.AMARILLO,f.suggestedLevel());
    }
    @Test void orangeAndYellowCommonIsYellow(){
        ModelEvent g=new ModelEvent("GFS",RUN,"X",Phenomenon.VIENTO,RUN,RUN.plusSeconds(3*3600),AlertLevel.NARANJA,100,"gust=100");
        ModelEvent e=new ModelEvent("ECMWF",RUN,"X",Phenomenon.VIENTO,RUN,RUN.plusSeconds(3*3600),AlertLevel.AMARILLO,70,"gust=70");
        FusedEvent f=new FusionEngine().fuse(List.of(g),List.of(e)).get(0);
        assertEquals(AlertLevel.AMARILLO,f.suggestedLevel()); assertEquals(Confidence.MEDIA,f.confidence());
    }
    @Test void singleModelIsLow(){
        ModelEvent g=new ModelEvent("GFS",RUN,"X",Phenomenon.VIENTO,RUN,RUN.plusSeconds(3*3600),AlertLevel.AMARILLO,70,"gust=70");
        assertEquals(Confidence.BAJA,new FusionEngine().fuse(List.of(g),List.of()).get(0).confidence());
    }
    @Test void distantEventsDoNotFuse(){
        ModelEvent g=new ModelEvent("GFS",RUN,"X",Phenomenon.VIENTO,RUN,RUN.plusSeconds(3*3600),AlertLevel.AMARILLO,70,"g");
        ModelEvent e=new ModelEvent("ECMWF",RUN,"X",Phenomenon.VIENTO,RUN.plusSeconds(12*3600),RUN.plusSeconds(15*3600),AlertLevel.AMARILLO,70,"e");
        assertEquals(2,new FusionEngine().fuse(List.of(g),List.of(e)).size());
    }
    @Test void undefinedRegionProducesNoEvent(){
        var r=List.of(new ThresholdRule(Phenomenon.VIENTO,"W",AlertLevel.AMARILLO,"gust_kmh",0,">=",65,"A"));
        UnitConfig uu=new UnitConfig("X",0,0,"UNDEFINED","UNDEFINED","UNDEFINED",false,true);
        assertTrue(new ThresholdEvaluator(r,72).evaluate("GFS",List.of(p("GFS",3,0,100,false)),Map.of("X",uu)).isEmpty());
    }
    @Test void marambioDoesNotInheritContinentalRegion(){
        UnitConfig m=new UnitConfig("Marambio",-64.14,-56.4,"UNDEFINED","UNDEFINED","UNDEFINED",false,true);
        assertEquals("UNDEFINED",m.windRegion()); assertEquals("UNDEFINED",m.rainRegion());
    }
    @Test void zondaFalseDoesNotClassify(){
        var r=List.of(new ThresholdRule(Phenomenon.ZONDA,"ZONDA",AlertLevel.AMARILLO,"gust_kmh",0,">=",0,"A"));
        UnitConfig uu=new UnitConfig("X",0,0,"UNDEFINED","UNDEFINED","UNDEFINED",true,true);
        assertTrue(new ThresholdEvaluator(r,72).evaluate("GFS",List.of(p("GFS",3,0,100,false)),Map.of("X",uu)).isEmpty());
    }
    @Test void zondaTrueCanClassify(){
        var r=List.of(new ThresholdRule(Phenomenon.ZONDA,"ZONDA",AlertLevel.AMARILLO,"gust_kmh",0,">=",0,"A"));
        UnitConfig uu=new UnitConfig("X",0,0,"UNDEFINED","UNDEFINED","UNDEFINED",true,true);
        assertFalse(new ThresholdEvaluator(r,72).evaluate("GFS",List.of(p("GFS",3,0,50,true)),Map.of("X",uu)).isEmpty());
    }
}
