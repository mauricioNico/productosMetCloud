import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.LocalDate;
import java.util.Set;

/**
 * Generador automático de soundings GFS.
 *
 * Detecta automáticamente la fecha/ciclo disponible del GFS,
 * descarga los GRIB correspondientes a f012 y f018, y genera un sounding
 * para cada localidad configurada usando python/sounding_gfs.py.
 */
public class GenerarSoundingsAutomaticoGFS {

    private static final String BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl";

    private static final String PYTHON_CMD = "python";
    private static final String PYTHON_SCRIPT_SOUNDING = "python/sounding_gfs.py";

    private static final Set<Integer> HORAS_SOUNDINGS = Set.of(12, 18);

    private static final double TOP = -20.0;
    private static final double BOTTOM = -80.0;
    private static final double LEFT = -95.0 + 360.0;
    private static final double RIGHT = -25.0 + 360.0;

    private static final PuntoSounding[] PUNTOS_SOUNDING = {
            new PuntoSounding("Tandil", -37.3217, -59.1332),
            new PuntoSounding("Mar_del_Plata", -38.0055, -57.5426),
            new PuntoSounding("El_Palomar", -34.6099, -58.5986),
            new PuntoSounding("Parana", -31.7319, -60.5238),
            new PuntoSounding("Escuela_de_Aviacion_Militar", -31.3236, -64.2080),
            new PuntoSounding("Gordillo", -29.4260, -66.8500),
            new PuntoSounding("Tartagal", -22.5164, -63.8013),
            new PuntoSounding("Rio_Cuarto", -33.1307, -64.3499),
            new PuntoSounding("Reconquista", -29.1440, -59.6500),
            new PuntoSounding("Resistencia", -27.4514, -58.9867),
            new PuntoSounding("Mendoza", -32.8895, -68.8458),
            new PuntoSounding("Villa_Reynolds", -33.7299, -65.3874),
            new PuntoSounding("Comodoro_Rivadavia", -45.8641, -67.4966),
            new PuntoSounding("Rio_Gallegos", -51.6230, -69.2168),
            new PuntoSounding("Marambio", -64.14, -56.4)
    };

    public static void main(String[] args) {
        System.out.println("=== GENERADOR AUTOMÁTICO DE SOUNDINGS GFS 0.25° ===");

        LocalDate hoy = LocalDate.now();
        String fecha = formatearFecha(hoy);

        Integer ciclo = detectarCicloDisponible(fecha, TOP, BOTTOM, LEFT, RIGHT);

        if (ciclo == null) {
            System.out.println("⚠ No se encontró ciclo disponible para hoy (" + fecha + ").");
            System.out.println("Se probará con el día anterior...");

            LocalDate ayer = hoy.minusDays(1);
            fecha = formatearFecha(ayer);
            ciclo = detectarCicloDisponible(fecha, TOP, BOTTOM, LEFT, RIGHT);

            if (ciclo == null) {
                System.out.println("❌ Tampoco se encontró ciclo disponible para ayer (" + fecha + ").");
                System.out.println("Proceso cancelado.");
                return;
            }
        }

        String cicloStr = String.format("%02d", ciclo);
        String carpetaGribs = "gribs/" + fecha;
        String carpetaSoundings = "salidas/" + fecha + "/soundings" + cicloStr;

        new File(carpetaGribs).mkdirs();
        new File(carpetaSoundings).mkdirs();
        // Crear subcarpetas para f012 y f018
        new File(carpetaSoundings + "/f012").mkdirs();
        new File(carpetaSoundings + "/f018").mkdirs();

        System.out.println("\n=== CONFIGURACIÓN AUTOMÁTICA ===");
        System.out.println("Fecha detectada: " + fecha);
        System.out.println("Ciclo detectado: " + cicloStr + "Z");
        System.out.println("Horas soundings: " + HORAS_SOUNDINGS);
        System.out.println("Localidades: " + PUNTOS_SOUNDING.length);
        System.out.println("Carpeta GRIB: " + carpetaGribs);
        System.out.println("Carpeta salida: " + carpetaSoundings);
        System.out.println("================================");

        int descargasOk = 0;
        int descargasFail = 0;
        int soundingsOk = 0;
        int soundingsFail = 0;

        for (int horaPron : HORAS_SOUNDINGS) {
            String horaStr = String.format("%03d", horaPron);
            String carpetaSoundingsHora = carpetaSoundings + "/f" + horaStr;
            System.out.println("\n========================================");
            System.out.println("Procesando f" + horaStr);
            System.out.println("========================================");

            String archivoLocal = construirNombreArchivoLocal(fecha, ciclo, horaPron, TOP, BOTTOM, LEFT, RIGHT);
            String url = construirURL(fecha, ciclo, horaPron, TOP, BOTTOM, LEFT, RIGHT);

            try {
                boolean descargado = descargarArchivo(url, archivoLocal);

                if (descargado) {
                    descargasOk++;
                } else {
                    descargasFail++;
                    System.out.println("❌ No se pudo descargar f" + horaStr + ". Se omiten soundings de esta hora.");
                    continue;
                }

                for (PuntoSounding punto : PUNTOS_SOUNDING) {
                    System.out.println("\n----------------------------------------");
                    System.out.println("Sounding: " + punto.nombre + " | f" + horaStr);
                    System.out.println("----------------------------------------");

                    boolean ok = generarSoundingConPython(
                            archivoLocal,
                            carpetaSoundingsHora,
                            punto.lat,
                            punto.lon,
                            punto.nombre
                    );

                    if (ok) {
                        soundingsOk++;
                        System.out.println("✔ Sounding generado: " + punto.nombre + " f" + horaStr);
                    } else {
                        soundingsFail++;
                        System.out.println("❌ Falló sounding: " + punto.nombre + " f" + horaStr);
                    }
                }

            } catch (Exception e) {
                descargasFail++;
                System.out.println("❌ Error general en f" + horaStr + ": " + e.getMessage());
                e.printStackTrace();
            }
        }

        System.out.println("\n=== RESUMEN FINAL ===");
        System.out.println("Descargas OK:          " + descargasOk);
        System.out.println("Descargas con error:   " + descargasFail);
        System.out.println("Soundings OK:          " + soundingsOk);
        System.out.println("Soundings con error:   " + soundingsFail);
        System.out.println("Carpeta de salida:     " + carpetaSoundings);
        System.out.println("Proceso terminado.");
    }

    private static String formatearFecha(LocalDate fecha) {
        return String.format("%04d%02d%02d", fecha.getYear(), fecha.getMonthValue(), fecha.getDayOfMonth());
    }

    private static Integer detectarCicloDisponible(String fecha,
                                                   double top,
                                                   double bottom,
                                                   double left,
                                                   double right) {
        int[] ciclos = {18, 12, 6, 0};

        for (int ciclo : ciclos) {
            try {
                System.out.println("Probando ciclo " + String.format("%02d", ciclo) + "Z para fecha " + fecha + "...");
                String url = construirURL(fecha, ciclo, 12, top, bottom, left, right);

                if (urlDisponible(url)) {
                    System.out.println("✔ Ciclo disponible detectado: " + String.format("%02d", ciclo) + "Z");
                    return ciclo;
                } else {
                    System.out.println("  No disponible.");
                }
            } catch (Exception e) {
                System.out.println("  Error al probar ciclo " + String.format("%02d", ciclo) + "Z: " + e.getMessage());
            }
        }
        return null;
    }

    private static boolean urlDisponible(String urlStr) {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(urlStr);
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("HEAD");
            conn.setConnectTimeout(15000);
            conn.setReadTimeout(15000);
            int status = conn.getResponseCode();
            return status == HttpURLConnection.HTTP_OK;
        } catch (Exception e) {
            return false;
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    private static String construirNombreArchivoLocal(String fecha,
                                                      int ciclo,
                                                      int horaPron,
                                                      double top,
                                                      double bottom,
                                                      double left,
                                                      double right) {
        String cicloStr = String.format("%02d", ciclo);
        String carpeta = "gribs/" + fecha + "/";
        String areaSuffix = construirAreaSuffix(top, bottom, left, right);
        return carpeta + "gfs_" + fecha + "_" + cicloStr + "_f" + String.format("%03d", horaPron) + areaSuffix + ".grib2";
    }

    private static String construirAreaSuffix(double top, double bottom, double left, double right) {
        return "_T" + sanitizeCoord(top) + "_B" + sanitizeCoord(bottom) + "_L" + sanitizeCoord(left) + "_R" + sanitizeCoord(right);
    }

    private static String sanitizeCoord(double val) {
        String s = String.valueOf(val);
        s = s.replace("+", "");
        s = s.replace("-", "m");
        s = s.replace(".", "");
        return s;
    }

    private static String construirURL(String fecha,
                                       int ciclo,
                                       int horaPron,
                                       double top,
                                       double bottom,
                                       double left,
                                       double right) {
        String cicloStr = String.format("%02d", ciclo);
        String file = "gfs.t" + cicloStr + "z.pgrb2.0p25.f" + String.format("%03d", horaPron);
        String dir = "/gfs." + fecha + "/" + cicloStr + "/atmos";
        String dirEnc = URLEncoder.encode(dir, StandardCharsets.UTF_8);

        return BASE_URL
                + "?file=" + file
                + "&all_var=on&all_lev=on"
                + "&toplat=" + top
                + "&bottomlat=" + bottom
                + "&leftlon=" + left
                + "&rightlon=" + right
                + "&dir=" + dirEnc;
    }

    private static boolean descargarArchivo(String urlStr, String nombreArchivo) throws IOException {
        Path archivoLocal = Path.of(nombreArchivo);

        if (Files.exists(archivoLocal)) {
            System.out.println("✔ GRIB ya existente, no se vuelve a descargar:");
            System.out.println("  " + archivoLocal);
            return true;
        }

        Files.createDirectories(archivoLocal.getParent());

        System.out.println("→ Descargando GRIB desde NOMADS...");
        System.out.println("URL: " + urlStr);

        URL url = new URL(urlStr);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setConnectTimeout(30000);
        conn.setReadTimeout(120000);

        int status = conn.getResponseCode();
        if (status != HttpURLConnection.HTTP_OK) {
            System.out.println("❌ HTTP " + status + " - " + conn.getResponseMessage());
            conn.disconnect();
            return false;
        }

        try (InputStream in = conn.getInputStream()) {
            Files.copy(in, archivoLocal, StandardCopyOption.REPLACE_EXISTING);
            System.out.println("✔ GRIB descargado correctamente:");
            System.out.println("  " + archivoLocal);
        } finally {
            conn.disconnect();
        }
        return true;
    }

    private static boolean generarSoundingConPython(String archivoGrib,
                                                    String carpetaSalidas,
                                                    double latPunto,
                                                    double lonPunto,
                                                    String nombrePunto) {
        try {
            ProcessBuilder pb = new ProcessBuilder(
                    PYTHON_CMD,
                    PYTHON_SCRIPT_SOUNDING,
                    archivoGrib,
                    carpetaSalidas,
                    String.valueOf(latPunto),
                    String.valueOf(lonPunto),
                    nombrePunto
            );

            pb.directory(new File("."));
            pb.inheritIO();

            Process p = pb.start();
            int exit = p.waitFor();
            return exit == 0;
        } catch (Exception e) {
            System.out.println("❌ No se pudo ejecutar Python para sounding: " + e.getMessage());
            return false;
        }
    }

    private static class PuntoSounding {
        String nombre;
        double lat;
        double lon;

        PuntoSounding(String nombre, double lat, double lon) {
            this.nombre = nombre;
            this.lat = lat;
            this.lon = lon;
        }
    }
}
