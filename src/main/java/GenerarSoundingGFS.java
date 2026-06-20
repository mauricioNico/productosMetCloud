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

public class GenerarSoundingGFS {

    private static final String BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl";
    private static final String PYTHON_CMD = "python";
    private static final String PYTHON_SCRIPT_SOUNDING = "python/sounding_gfs.py";

    // Región fija igual a la usada en DescargaGFSMenu
    private static final double TOP = -20.0;
    private static final double BOTTOM = -80.0;
    private static final double LEFT = -95.0 + 360.0;
    private static final double RIGHT = -25.0 + 360.0;

    public static void main(String[] args) {

        if (args.length < 6) {
            System.out.println("Uso:");
            System.out.println("mvn exec:java -Dexec.mainClass=GenerarSoundingGFS -Dexec.args=\"fecha ciclo hora lat lon nombre\"");
            System.out.println();
            System.out.println("Ejemplo:");
            System.out.println("mvn exec:java -Dexec.mainClass=GenerarSoundingGFS -Dexec.args=\"20260529 06 024 -34.92 -57.95 La_Plata\"");
            return;
        }

        String fecha = args[0];
        int ciclo = Integer.parseInt(args[1]);
        int horaPron = Integer.parseInt(args[2]);
        double lat = Double.parseDouble(args[3]);
        double lon = Double.parseDouble(args[4]);
        String nombre = args[5];

        String cicloStr = String.format("%02d", ciclo);
        String horaStr = String.format("%03d", horaPron);

        String carpetaGribs = "gribs/" + fecha;
        String carpetaSalida = "salidas/" + fecha + "/soundings" + cicloStr;

        new File(carpetaGribs).mkdirs();
        new File(carpetaSalida).mkdirs();

        String archivoGrib = construirNombreArchivoLocal(
                fecha,
                ciclo,
                horaPron,
                TOP,
                BOTTOM,
                LEFT,
                RIGHT
        );

        String url = construirURL(
                fecha,
                ciclo,
                horaPron,
                TOP,
                BOTTOM,
                LEFT,
                RIGHT
        );

        System.out.println("========================================");
        System.out.println("GENERADOR PUNTUAL DE SOUNDING GFS");
        System.out.println("========================================");
        System.out.println("Fecha:           " + fecha);
        System.out.println("Ciclo:           " + cicloStr + "Z");
        System.out.println("Hora pronostico: f" + horaStr);
        System.out.println("Localidad:       " + nombre);
        System.out.println("Latitud:         " + lat);
        System.out.println("Longitud:        " + lon);
        System.out.println("GRIB local:      " + archivoGrib);
        System.out.println("Salida:          " + carpetaSalida);
        System.out.println("========================================");

        try {
            boolean descargado = descargarArchivo(url, archivoGrib);

            if (!descargado) {
                System.out.println("❌ No se pudo descargar el GRIB.");
                return;
            }

            boolean ok = generarSoundingConPython(
                    archivoGrib,
                    carpetaSalida,
                    lat,
                    lon,
                    nombre
            );

            if (ok) {
                System.out.println("✔ Sounding generado correctamente.");
            } else {
                System.out.println("❌ Error al generar el sounding.");
            }

        } catch (Exception e) {
            System.out.println("❌ Error general: " + e.getMessage());
            e.printStackTrace();
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

        return carpeta + "gfs_" + fecha + "_" + cicloStr
                + "_f" + String.format("%03d", horaPron)
                + areaSuffix + ".grib2";
    }

    private static String construirAreaSuffix(double top,
                                              double bottom,
                                              double left,
                                              double right) {
        return "_T" + sanitizeCoord(top)
                + "_B" + sanitizeCoord(bottom)
                + "_L" + sanitizeCoord(left)
                + "_R" + sanitizeCoord(right);
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
            System.out.println("▶ Ejecutando Python para generar sounding...");

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

            if (exit == 0) {
                return true;
            } else {
                System.out.println("❌ Python terminó con error. Exit code: " + exit);
                return false;
            }

        } catch (Exception e) {
            System.out.println("❌ No se pudo ejecutar Python: " + e.getMessage());
            return false;
        }
    }
}
