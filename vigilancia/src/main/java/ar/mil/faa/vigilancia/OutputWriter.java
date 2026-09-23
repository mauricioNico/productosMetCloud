package ar.mil.faa.vigilancia;
import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.List;
public final class OutputWriter {
    private static final DateTimeFormatter F = DateTimeFormatter.ofPattern("dd MMM HH'Z'").withZone(ZoneOffset.UTC);
    private OutputWriter() {}
    public static void write(Path dir, List<FusedEvent> events, Instant gfsRun, Instant ecmwfRun, int horizon) throws IOException {
        Files.createDirectories(dir);
        writeCsv(dir.resolve("eventos_vigilancia.csv"), events);
        writeJson(dir.resolve("eventos_vigilancia.json"), events, gfsRun, ecmwfRun, horizon);
        writePng(dir.resolve("resumen_vigilancia.png"), events, gfsRun, ecmwfRun);
    }
    private static void writeCsv(Path p, List<FusedEvent> es) throws IOException {
        StringBuilder s = new StringBuilder("unidad;fenomeno;inicio_utc;fin_utc;nivel_gfs;valor_gfs;nivel_ecmwf;valor_ecmwf;nivel_sugerido;confianza;corrida_gfs;corrida_ecmwf;observacion\n");
        for (FusedEvent e : es) s.append(e.unit()).append(';').append(e.phenomenon()).append(';')
                .append(e.start()).append(';').append(e.end()).append(';')
                .append(level(e.gfs())).append(';').append(value(e.gfs())).append(';')
                .append(level(e.ecmwf())).append(';').append(value(e.ecmwf())).append(';')
                .append(e.suggestedLevel()).append(';').append(e.confidence()).append(';')
                .append(run(e.gfs())).append(';').append(run(e.ecmwf())).append(';')
                .append(e.observation().replace(';', ',')).append('\n');
        Files.writeString(p, s.toString(), StandardCharsets.UTF_8);
    }
    private static void writeJson(Path p, List<FusedEvent> es, Instant gfsRun, Instant ecmwfRun, int horizon) throws IOException {
        StringBuilder s = new StringBuilder();
        s.append("{\n  \"generadoEn\": \"").append(Instant.now()).append("\",\n")
                .append("  \"horizonteHoras\": ").append(horizon).append(",\n")
                .append("  \"gfs\": {\"run\": ").append(json(gfsRun)).append("},\n")
                .append("  \"ecmwf\": {\"run\": ").append(json(ecmwfRun)).append("},\n  \"eventos\": [\n");
        for (int i=0;i<es.size();i++) {
            FusedEvent e=es.get(i);
            s.append("    {\"unidad\":").append(json(e.unit())).append(",\"fenomeno\":").append(json(e.phenomenon().name()))
                    .append(",\"inicioUtc\":").append(json(e.start())).append(",\"finUtc\":").append(json(e.end()))
                    .append(",\"nivelGfs\":").append(json(level(e.gfs()))).append(",\"valorGfs\":").append(json(value(e.gfs())))
                    .append(",\"nivelEcmwf\":").append(json(level(e.ecmwf()))).append(",\"valorEcmwf\":").append(json(value(e.ecmwf())))
                    .append(",\"nivelSugerido\":").append(json(e.suggestedLevel().name())).append(",\"confianza\":").append(json(e.confidence().name()))
                    .append(",\"observacion\":").append(json(e.observation())).append('}');
            if (i+1<es.size()) s.append(',');
            s.append('\n');
        }
        s.append("  ]\n}\n");
        Files.writeString(p, s.toString(), StandardCharsets.UTF_8);
    }
    private static void writePng(Path p, List<FusedEvent> es, Instant gfsRun, Instant ecmwfRun) throws IOException {
        int w=1500, row=70, h=Math.max(420, 260+es.size()*row);
        BufferedImage img=new BufferedImage(w,h,BufferedImage.TYPE_INT_RGB);
        Graphics2D g=img.createGraphics(); g.setColor(Color.WHITE); g.fillRect(0,0,w,h); g.setColor(Color.BLACK);
        g.setFont(new Font("SansSerif",Font.BOLD,30)); g.drawString("VIGILANCIA METEOROLÓGICA AUTOMÁTICA – 72 H",55,55);
        g.setFont(new Font("SansSerif",Font.PLAIN,20)); g.drawString("GFS 0.25° + ECMWF IFS 0.25°",55,88);
        g.drawString("GFS: "+show(gfsRun)+" | ECMWF: "+show(ecmwfRun),55,120);
        int y=175; g.setFont(new Font("SansSerif",Font.BOLD,17));
        g.drawString("UNIDAD / FENÓMENO",55,y); g.drawString("PERÍODO",400,y); g.drawString("GFS",720,y); g.drawString("ECMWF",920,y); g.drawString("NIVEL",1120,y); g.drawString("CONFIANZA",1280,y);
        y+=32; g.setFont(new Font("SansSerif",Font.PLAIN,16));
        for (FusedEvent e:es) {
            g.drawString(e.unit()+" / "+e.phenomenon(),55,y); g.drawString(F.format(e.start())+" - "+F.format(e.end()),400,y);
            g.drawString(level(e.gfs())+" "+value(e.gfs()),720,y); g.drawString(level(e.ecmwf())+" "+value(e.ecmwf()),920,y);
            g.drawString(e.suggestedLevel().name(),1120,y); g.drawString(e.confidence().name(),1280,y); y+=row;
        }
        g.setFont(new Font("SansSerif",Font.ITALIC,16));
        g.drawString("Producto automático de apoyo a la decisión. La emisión de un alerta queda sujeta al análisis meteorológico operativo.",55,h-45);
        g.dispose(); ImageIO.write(img,"png",p.toFile());
    }
    private static String level(ModelEvent e){return e==null?"N/D":e.level().name();}
    private static String value(ModelEvent e){return e==null?"N/D":e.valueDescription();}
    private static String run(ModelEvent e){return e==null?"":e.runTime().toString();}
    private static String show(Instant i){return i==null?"N/D":i.toString();}
    private static String json(Object o){if(o==null)return"null";return "\""+o.toString().replace("\\","\\\\").replace("\"","\\\"")+"\"";}
}
