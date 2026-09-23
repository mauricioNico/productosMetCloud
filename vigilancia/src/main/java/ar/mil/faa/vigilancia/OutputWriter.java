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
    private static final DateTimeFormatter F =
            DateTimeFormatter.ofPattern("dd MMM HH'Z'").withZone(ZoneOffset.UTC);

    private OutputWriter() {}

    public static void write(Path dir, List<FusedEvent> events, Instant gfsRun,
                             Instant ecmwfRun, int horizon) throws IOException {
        Files.createDirectories(dir);
        writeCsv(dir.resolve("eventos_vigilancia.csv"), events);
        writeJson(dir.resolve("eventos_vigilancia.json"), events, gfsRun, ecmwfRun, horizon);
        writePng(dir.resolve("resumen_vigilancia.png"), events, gfsRun, ecmwfRun);
    }

    private static void writeCsv(Path p, List<FusedEvent> es) throws IOException {
        StringBuilder s = new StringBuilder(
                "unidad;fenomeno;inicio_utc;fin_utc;nivel_gfs;valor_gfs;" +
                "nivel_ecmwf;valor_ecmwf;nivel_sugerido;confianza;" +
                "corrida_gfs;corrida_ecmwf;observacion\n");
        for (FusedEvent e : es) {
            s.append(e.unit()).append(';').append(e.phenomenon()).append(';')
                    .append(e.start()).append(';').append(e.end()).append(';')
                    .append(level(e.gfs())).append(';').append(value(e.gfs())).append(';')
                    .append(level(e.ecmwf())).append(';').append(value(e.ecmwf())).append(';')
                    .append(e.suggestedLevel()).append(';').append(e.confidence()).append(';')
                    .append(run(e.gfs())).append(';').append(run(e.ecmwf())).append(';')
                    .append(e.observation().replace(';', ',')).append('\n');
        }
        Files.writeString(p, s.toString(), StandardCharsets.UTF_8);
    }

    private static void writeJson(Path p, List<FusedEvent> es, Instant gfsRun,
                                  Instant ecmwfRun, int horizon) throws IOException {
        StringBuilder s = new StringBuilder();
        s.append("{\n  \"generadoEn\": \"").append(Instant.now()).append("\",\n")
                .append("  \"horizonteHoras\": ").append(horizon).append(",\n")
                .append("  \"gfs\": {\"run\": ").append(json(gfsRun)).append("},\n")
                .append("  \"ecmwf\": {\"run\": ").append(json(ecmwfRun)).append("},\n")
                .append("  \"eventos\": [\n");

        for (int i = 0; i < es.size(); i++) {
            FusedEvent e = es.get(i);
            s.append("    {\"unidad\":").append(json(e.unit()))
                    .append(",\"fenomeno\":").append(json(e.phenomenon().name()))
                    .append(",\"inicioUtc\":").append(json(e.start()))
                    .append(",\"finUtc\":").append(json(e.end()))
                    .append(",\"nivelGfs\":").append(json(level(e.gfs())))
                    .append(",\"valorGfs\":").append(json(value(e.gfs())))
                    .append(",\"nivelEcmwf\":").append(json(level(e.ecmwf())))
                    .append(",\"valorEcmwf\":").append(json(value(e.ecmwf())))
                    .append(",\"nivelSugerido\":").append(json(e.suggestedLevel().name()))
                    .append(",\"confianza\":").append(json(e.confidence().name()))
                    .append(",\"observacion\":").append(json(e.observation())).append('}');
            if (i + 1 < es.size()) s.append(',');
            s.append('\n');
        }
        s.append("  ]\n}\n");
        Files.writeString(p, s.toString(), StandardCharsets.UTF_8);
    }

    private static void writePng(Path p, List<FusedEvent> es,
                                 Instant gfsRun, Instant ecmwfRun) throws IOException {
        int width = 1800;
        int header = 180;
        int cardHeight = 125;
        int footer = 90;
        int height = Math.max(520, header + es.size() * cardHeight + footer);

        BufferedImage img = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = img.createGraphics();
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setColor(Color.WHITE);
        g.fillRect(0, 0, width, height);

        g.setColor(Color.BLACK);
        g.setFont(new Font("SansSerif", Font.BOLD, 32));
        g.drawString("VIGILANCIA METEOROLÓGICA AUTOMÁTICA – 72 H", 60, 58);

        g.setFont(new Font("SansSerif", Font.PLAIN, 20));
        g.drawString("GFS 0.25° + ECMWF IFS 0.25°", 60, 94);
        drawFitted(g, "Corridas: GFS " + show(gfsRun) + " | ECMWF " + show(ecmwfRun),
                60, 128, width - 120);

        int y = header;
        for (int i = 0; i < es.size(); i++) {
            FusedEvent e = es.get(i);

            g.setColor(i % 2 == 0 ? new Color(246, 248, 250) : new Color(235, 240, 245));
            g.fillRoundRect(50, y - 25, width - 100, cardHeight - 12, 18, 18);
            g.setColor(new Color(150, 160, 170));
            g.drawRoundRect(50, y - 25, width - 100, cardHeight - 12, 18, 18);

            g.setColor(Color.BLACK);
            g.setFont(new Font("SansSerif", Font.BOLD, 19));
            drawFitted(g, e.unit() + " / " + e.phenomenon(), 75, y + 3, 380);

            g.setFont(new Font("SansSerif", Font.PLAIN, 17));
            drawFitted(g, "Período: " + F.format(e.start()) + " – " + F.format(e.end()),
                    470, y + 3, 500);
            drawFitted(g, "Nivel sugerido: " + e.suggestedLevel().name(),
                    1000, y + 3, 360);
            drawFitted(g, "Confianza: " + e.confidence().name(),
                    1390, y + 3, 320);

            g.setFont(new Font("SansSerif", Font.PLAIN, 16));
            drawFitted(g, "GFS: " + level(e.gfs()) + " · " + value(e.gfs()),
                    75, y + 38, 780);
            drawFitted(g, "ECMWF: " + level(e.ecmwf()) + " · " + value(e.ecmwf()),
                    900, y + 38, 810);

            g.setFont(new Font("SansSerif", Font.ITALIC, 16));
            drawFitted(g, e.observation(), 75, y + 75, width - 150);

            y += cardHeight;
        }

        g.setColor(Color.BLACK);
        g.setFont(new Font("SansSerif", Font.ITALIC, 16));
        drawFitted(g,
                "Producto automático de apoyo a la decisión. La emisión de un alerta queda sujeta al análisis meteorológico operativo.",
                60, height - 42, width - 120);

        g.dispose();
        ImageIO.write(img, "png", p.toFile());
    }

    private static void drawFitted(Graphics2D g, String text, int x, int y, int maxWidth) {
        if (text == null) text = "";
        FontMetrics fm = g.getFontMetrics();
        if (fm.stringWidth(text) <= maxWidth) {
            g.drawString(text, x, y);
            return;
        }
        String ellipsis = "…";
        int end = text.length();
        while (end > 0 && fm.stringWidth(text.substring(0, end) + ellipsis) > maxWidth) {
            end--;
        }
        g.drawString(text.substring(0, Math.max(0, end)) + ellipsis, x, y);
    }

    private static String level(ModelEvent e) { return e == null ? "N/D" : e.level().name(); }
    private static String value(ModelEvent e) { return e == null ? "N/D" : e.valueDescription(); }
    private static String run(ModelEvent e) { return e == null ? "" : e.runTime().toString(); }
    private static String show(Instant i) { return i == null ? "N/D" : i.toString(); }

    private static String json(Object o) {
        if (o == null) return "null";
        return "\"" + o.toString().replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }
}
