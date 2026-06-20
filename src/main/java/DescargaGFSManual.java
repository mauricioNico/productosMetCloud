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
import java.util.Scanner;
import java.util.stream.Stream;

public class DescargaGFSManual {

    private static final String BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl";

    // Usar SIEMPRE el Python del entorno "cartas"
    private static final String PYTHON_CMD = "python";

    // Scripts Python
    private static final String PYTHON_SCRIPT_MSLP = "python/mapa_mslp.py";
    private static final String PYTHON_SCRIPT_METEOGRAMA = "python/meteograma_gfs.py";

    public static void main(String[] args) {

        Scanner sc = new Scanner(System.in);

        System.out.println("=== GENERADOR MANUAL DE CARTAS GFS 0.25° ===");

        int anio = pedirEntero(sc, "Ingrese AÑO (YYYY): ", 2000, 2100);
        int mes = pedirEntero(sc, "Ingrese MES (1-12): ", 1, 12);
        int dia = pedirEntero(sc, "Ingrese DÍA (1-31): ", 1, 31);

        if (!fechaValida(anio, mes, dia)) {
            System.out.println("❌ Fecha inválida.");
            return;
        }

        String fecha = String.format("%04d%02d%02d", anio, mes, dia);

        int ciclo = pedirEntero(sc, "Ingrese ciclo (00/06/12/18): ", 0, 18);
        if (!(ciclo == 0 || ciclo == 6 || ciclo == 12 || ciclo == 18)) {
            System.out.println("❌ Ciclo inválido.");
            return;
        }

        int horaInicial = pedirEntero(sc, "Ingrese hora inicial del pronóstico (0-384): ", 0, 384);
        int cantidad = pedirEntero(sc, "Ingrese cantidad de cartas/tiempos a descargar: ", 1, 100);
        int salto = pedirEntero(sc, "Ingrese salto entre tiempos en horas (ej. 12): ", 1, 384);

        System.out.println("\n=== REGIÓN PARA LAS CARTAS / DESCARGA ===");
        double top = pedirDouble(sc, "Latitud norte (top): ");
        double bottom = pedirDouble(sc, "Latitud sur (bottom): ");
        double leftOeste = pedirDouble(sc, "Longitud oeste (left, ej. -95): ");
        double rightOeste = pedirDouble(sc, "Longitud este (right, ej. -25): ");

        double left = leftOeste + 360.0;
        double right = rightOeste + 360.0;

        boolean generarCartas = pedirSiNo(sc, "\n¿Desea generar las cartas sinópticas? (s/n): ");
        boolean generarMeteograma = pedirSiNo(sc, "¿Desea generar el meteograma? (s/n): ");

        String nombrePunto = "Punto";
        double latPunto = 0.0;
        double lonPunto = 0.0;

        if (generarMeteograma) {
            System.out.println("\n=== PUNTO PARA EL METEOGRAMA ===");
            System.out.print("Nombre del punto (ej. Buenos_Aires): ");
            nombrePunto = sc.nextLine().trim();
            if (nombrePunto.isBlank()) {
                nombrePunto = "Punto";
            }

            latPunto = pedirDouble(sc, "Latitud del punto (ej. -34.60): ");
            lonPunto = pedirDouble(sc, "Longitud del punto (ej. -58.40): ");
        }

        boolean borrarGribsAlFinal = pedirSiNo(sc, "\n¿Desea borrar los GRIB al finalizar? (s/n): ");

        System.out.println("\n=== CONFIGURACIÓN ===");
        System.out.println("Fecha: " + fecha);
        System.out.println("Ciclo: " + String.format("%02d", ciclo) + "Z");
        System.out.println("Hora inicial: f" + String.format("%03d", horaInicial));
        System.out.println("Cantidad: " + cantidad);
        System.out.println("Salto: " + salto + " h");
        System.out.println("Top: " + top);
        System.out.println("Bottom: " + bottom);
        System.out.println("Left: " + left + " (convertida a 0-360)");
        System.out.println("Right: " + right + " (convertida a 0-360)");
        System.out.println("Generar cartas: " + (generarCartas ? "SI" : "NO"));
        System.out.println("Generar meteograma: " + (generarMeteograma ? "SI" : "NO"));
        if (generarMeteograma) {
            System.out.println("Punto meteograma: " + nombrePunto);
            System.out.println("Lat punto: " + latPunto);
            System.out.println("Lon punto: " + lonPunto);
        }
        System.out.println("Borrar GRIB al final: " + (borrarGribsAlFinal ? "SI" : "NO"));
        System.out.println("=====================");

        int ok = 0;
        int fail = 0;

        for (int i = 0; i < cantidad; i++) {
            int horaPron = horaInicial + i * salto;

            if (horaPron > 384) {
                System.out.println("⚠ Se omite f" + String.format("%03d", horaPron) + " por exceder 384 horas.");
                continue;
            }

            try {
                System.out.println("\n========================================");
                System.out.println("Procesando pronóstico f" + String.format("%03d", horaPron));
                System.out.println("========================================");

                procesarPronostico(fecha, ciclo, horaPron, top, bottom, left, right, generarCartas);
                ok++;

            } catch (Exception e) {
                fail++;
                System.out.println("❌ Error en f" + String.format("%03d", horaPron) + ": " + e.getMessage());
                e.printStackTrace();
            }
        }

        if (generarMeteograma) {
            System.out.println("\n========================================");
            System.out.println("Generación de meteograma");
            System.out.println("========================================");

            boolean meteogramaOk = generarMeteogramaConPython(
                    "gribs/" + fecha,
                    "salidas/" + fecha,
                    latPunto,
                    lonPunto,
                    nombrePunto
            );

            if (meteogramaOk) {
                System.out.println("✔ Meteograma generado correctamente.");
            } else {
                System.out.println("❌ No se pudo generar el meteograma.");
            }
        } else {
            System.out.println("\nℹ Se omitió la generación del meteograma por elección del usuario.");
        }

        if (borrarGribsAlFinal) {
            System.out.println("\n========================================");
            System.out.println("Limpieza final de GRIB");
            System.out.println("========================================");
            borrarGribsEIdxDeFecha(fecha);
            borrarCarpetaSiEstaVacia(fecha);
        } else {
            System.out.println("\nℹ Los GRIB se conservaron en disco.");
        }

        System.out.println("\n=== RESUMEN ===");
        System.out.println("Procesados OK: " + ok);
        System.out.println("Con error:     " + fail);
        System.out.println("Proceso terminado.");
    }

    private static int pedirEntero(Scanner sc, String msg, int min, int max) {
        while (true) {
            System.out.print(msg);
            try {
                int val = Integer.parseInt(sc.nextLine().trim());
                if (val >= min && val <= max) return val;
            } catch (Exception ignored) {
            }
            System.out.println("Valor inválido. Intente nuevamente.");
        }
    }

    private static double pedirDouble(Scanner sc, String msg) {
        while (true) {
            System.out.print(msg);
            try {
                return Double.parseDouble(sc.nextLine().trim());
            } catch (Exception ignored) {
                System.out.println("Valor inválido. Intente nuevamente.");
            }
        }
    }

    private static boolean pedirSiNo(Scanner sc, String msg) {
        while (true) {
            System.out.print(msg);
            String resp = sc.nextLine().trim().toLowerCase();
            if (resp.equals("s") || resp.equals("si") || resp.equals("sí")) {
                return true;
            }
            if (resp.equals("n") || resp.equals("no")) {
                return false;
            }
            System.out.println("Respuesta inválida. Ingrese 's' o 'n'.");
        }
    }

    private static boolean fechaValida(int a, int m, int d) {
        try {
            LocalDate.of(a, m, d);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private static void procesarPronostico(String fecha, int ciclo, int horaPron,
                                           double top, double bottom,
                                           double left, double right,
                                           boolean generarCartas) throws IOException {

        String carpetaGribs = "gribs/" + fecha;
        String carpetaSalidas = "salidas/" + fecha;

        new File(carpetaGribs).mkdirs();
        new File(carpetaSalidas).mkdirs();
        new File(carpetaSalidas + "/cortoplazo").mkdirs();
        new File(carpetaSalidas + "/largo_plazo").mkdirs();

        String archivoLocal = construirNombreArchivoLocal(fecha, ciclo, horaPron, top, bottom, left, right);
        String url = construirURL(fecha, ciclo, horaPron, top, bottom, left, right);

        System.out.println("\nArchivo destino: " + archivoLocal);
        System.out.println("URL: " + url);

        boolean descargado = descargarArchivo(url, archivoLocal);

        if (!descargado) {
            System.out.println("❌ No se pudo obtener el archivo.");
            return;
        }

        if (!generarCartas) {
            System.out.println("ℹ Se omite la generación de la carta por elección del usuario.");
            System.out.println("✔ GRIB conservado: " + archivoLocal);
            return;
        }

        // Determinar subcarpeta según rango horario
        String carpetaDestino = carpetaSalidas;
        if (horaPron >= 12 && horaPron <= 36) {
            carpetaDestino = carpetaSalidas + "/cortoplazo";
        } else if (horaPron >= 48 && horaPron <= 84) {
            carpetaDestino = carpetaSalidas + "/largo_plazo";
        }

        String pngSalida = carpetaDestino + "/" +
                new File(archivoLocal).getName().replace(".grib2", ".png");

        if (Files.exists(Path.of(pngSalida))) {
            System.out.println("✔ La carta ya existe para esa hora y región, no se vuelve a generar:");
            System.out.println("  " + pngSalida);
            System.out.println("✔ GRIB conservado: " + archivoLocal);
            return;
        }

        boolean generado = generarMapaMSLPConPython(archivoLocal, pngSalida, top, bottom, left, right);

        if (generado) {
            System.out.println("✔ GRIB conservado: " + archivoLocal);
        } else {
            System.out.println("⚠ Se conserva el GRIB para revisión: " + archivoLocal);
        }
    }

    private static String construirNombreArchivoLocal(String fecha, int ciclo, int horaPron,
                                                      double top, double bottom,
                                                      double left, double right) {

        String cicloStr = String.format("%02d", ciclo);
        String carpeta = "gribs/" + fecha + "/";
        String areaSuffix = construirAreaSuffix(top, bottom, left, right);

        return carpeta + "gfs_" + fecha + "_" + cicloStr +
                "_f" + String.format("%03d", horaPron) + areaSuffix + ".grib2";
    }

    private static String construirAreaSuffix(double top, double bottom,
                                              double left, double right) {
        return "_T" + sanitizeCoord(top) +
                "_B" + sanitizeCoord(bottom) +
                "_L" + sanitizeCoord(left) +
                "_R" + sanitizeCoord(right);
    }

    private static String sanitizeCoord(double val) {
        String s = String.valueOf(val);
        s = s.replace("+", "");
        s = s.replace("-", "m");
        s = s.replace(".", "");
        return s;
    }

    private static String construirURL(String fecha, int ciclo, int horaPron,
                                       double top, double bottom,
                                       double left, double right) {

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
            System.out.println("✔ Archivo ya existente, no se descarga: " + archivoLocal);
            return true;
        }

        System.out.println("→ Archivo no existe, descargando...");

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
            System.out.println("✔ Archivo descargado correctamente.");
        } finally {
            conn.disconnect();
        }

        return true;
    }

    private static boolean generarMapaMSLPConPython(String nombreGrib,
                                                    String salidaPNG,
                                                    double top, double bottom,
                                                    double left, double right) {

        try {
            System.out.println("▶ Generando carta con Python...");
            System.out.println("  Usando Python: " + PYTHON_CMD);

            ProcessBuilder pb = new ProcessBuilder(
                    PYTHON_CMD,
                    PYTHON_SCRIPT_MSLP,
                    nombreGrib,
                    salidaPNG,
                    String.valueOf(top),
                    String.valueOf(bottom),
                    String.valueOf(left),
                    String.valueOf(right)
            );

            pb.directory(new File("."));
            pb.inheritIO();

            Process p = pb.start();
            int exit = p.waitFor();

            if (exit == 0) {
                System.out.println("✔ Carta generada: " + salidaPNG);
                return true;
            } else {
                System.out.println("❌ Error al generar carta (exit=" + exit + ")");
                return false;
            }

        } catch (Exception e) {
            System.out.println("❌ No se pudo ejecutar Python: " + e.getMessage());
            return false;
        }
    }

    private static boolean generarMeteogramaConPython(String carpetaGribs,
                                                      String carpetaSalidas,
                                                      double latPunto,
                                                      double lonPunto,
                                                      String nombrePunto) {
        try {
            System.out.println("▶ Generando meteograma con Python...");
            System.out.println("  Usando Python: " + PYTHON_CMD);

            ProcessBuilder pb = new ProcessBuilder(
                    PYTHON_CMD,
                    PYTHON_SCRIPT_METEOGRAMA,
                    carpetaGribs,
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
                System.out.println("❌ Error al generar meteograma (exit=" + exit + ")");
                return false;
            }

        } catch (Exception e) {
            System.out.println("❌ No se pudo ejecutar Python para meteograma: " + e.getMessage());
            return false;
        }
    }

    private static void borrarGribsEIdxDeFecha(String fecha) {
        Path carpeta = Path.of("gribs/" + fecha);

        if (!Files.exists(carpeta) || !Files.isDirectory(carpeta)) {
            System.out.println("ℹ No existe carpeta de GRIB para limpiar: " + carpeta);
            return;
        }

        int borradosGrib = 0;
        int borradosIdx = 0;
        int errores = 0;

        try (Stream<Path> stream = Files.list(carpeta)) {
            for (Path p : stream.toList()) {
                String nombre = p.getFileName().toString().toLowerCase();

                if (nombre.endsWith(".grib2") || nombre.endsWith(".idx")) {
                    try {
                        Files.deleteIfExists(p);
                        if (nombre.endsWith(".grib2")) {
                            borradosGrib++;
                            System.out.println("🧹 GRIB eliminado: " + p);
                        } else {
                            borradosIdx++;
                            System.out.println("🧹 IDX eliminado: " + p);
                        }
                    } catch (IOException e) {
                        errores++;
                        System.out.println("⚠ No se pudo borrar: " + p);
                    }
                }
            }
        } catch (IOException e) {
            System.out.println("⚠ Error al listar la carpeta: " + carpeta);
            return;
        }

        System.out.println("Resumen limpieza -> GRIB: " + borradosGrib
                + " | IDX: " + borradosIdx
                + " | errores: " + errores);
    }

    private static void borrarCarpetaSiEstaVacia(String fecha) {
        Path carpeta = Path.of("gribs/" + fecha);
        try {
            if (Files.exists(carpeta) && Files.isDirectory(carpeta)) {
                try (Stream<Path> stream = Files.list(carpeta)) {
                    if (!stream.findAny().isPresent()) {
                        Files.delete(carpeta);
                        System.out.println("🧹 Carpeta vacía eliminada: " + carpeta);
                    }
                }
            }
        } catch (IOException e) {
            System.out.println("⚠ No se pudo borrar la carpeta vacía: " + carpeta);
        }
    }
}