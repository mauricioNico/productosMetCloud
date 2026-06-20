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
import java.util.stream.Stream;

public class DescargaGFSMenu {

    private static final String BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl";

    private static final String PYTHON_CMD = "python";

    private static final String PYTHON_SCRIPT_MSLP = "python/mapa_mslp.py";
    private static final String PYTHON_SCRIPT_METEOGRAMA = "python/meteograma_gfs.py";

    // Descargar GRIB desde f000 hasta f084 cada 3 h
    private static final int HORA_INICIAL_DESCARGA = 0;
    private static final int HORA_FINAL_DESCARGA = 84;
    private static final int SALTO_DESCARGA = 3;

    // Cartas solamente para estos horarios
    private static final Set<Integer> HORAS_CARTAS = Set.of(
            12, 24, 36, 48, 60, 72, 84
    );

    // Región fija
    private static final double TOP = -20.0;
    private static final double BOTTOM = -80.0;
    private static final double LEFT = -95.0 + 360.0;
    private static final double RIGHT = -25.0 + 360.0;

    // Si querés conservar los GRIB, cambiar a false
    private static final boolean BORRAR_GRIBS_AL_FINAL = true;

    private static final PuntoMeteograma[] PUNTOS_METEOGRAMA = {
            new PuntoMeteograma("Tandil", -37.3217, -59.1332),
            new PuntoMeteograma("Mar_del_Plata", -38.0055, -57.5426),
            new PuntoMeteograma("El_Palomar", -34.6099, -58.5986),
            new PuntoMeteograma("Parana", -31.7319, -60.5238),
            new PuntoMeteograma("Escuela_de_Aviacion_Militar", -31.3236, -64.2080),
            new PuntoMeteograma("Gordillo", -29.4260, -66.8500),
            new PuntoMeteograma("Tartagal", -22.5164, -63.8013),
            new PuntoMeteograma("Rio_Cuarto", -33.1307, -64.3499),
            new PuntoMeteograma("Reconquista", -29.1440, -59.6500),
            new PuntoMeteograma("Resistencia", -27.4514, -58.9867),
            new PuntoMeteograma("Mendoza", -32.8895, -68.8458),
            new PuntoMeteograma("Villa_Reynolds", -33.7299, -65.3874),
            new PuntoMeteograma("Comodoro_Rivadavia", -45.8641, -67.4966),
            new PuntoMeteograma("Rio_Gallegos", -51.6230, -69.2168),
            new PuntoMeteograma("Marambio", -64.14, -56.40)
    };

    public static void main(String[] args) {

        System.out.println("=== GENERADOR AUTOMÁTICO GFS 0.25°: CARTAS + METEOGRAMAS ===");

        LocalDate hoy = LocalDate.now();
        String fecha = String.format("%04d%02d%02d",
                hoy.getYear(), hoy.getMonthValue(), hoy.getDayOfMonth());

        Integer ciclo = detectarCicloDisponible(fecha, TOP, BOTTOM, LEFT, RIGHT);

        if (ciclo == null) {
            System.out.println("⚠ No se encontró ciclo disponible para hoy (" + fecha + ").");
            System.out.println("Se probará con el día anterior...");

            LocalDate ayer = hoy.minusDays(1);
            fecha = String.format("%04d%02d%02d",
                    ayer.getYear(), ayer.getMonthValue(), ayer.getDayOfMonth());

            ciclo = detectarCicloDisponible(fecha, TOP, BOTTOM, LEFT, RIGHT);

            if (ciclo == null) {
                System.out.println("❌ Tampoco se encontró ciclo disponible para ayer (" + fecha + ").");
                System.out.println("Proceso cancelado.");
                return;
            }
        }

        String cicloStr = String.format("%02d", ciclo);

        /*
         * Las salidas se separan por fecha, tipo de producto y corrida del modelo.
         *
         * Ejemplo para fecha 20260529 y ciclo 12Z:
         *
         * salidas/20260529/cartas12
         * salidas/20260529/meteogramas12
         *
         * De esta forma, si luego se ejecuta otra corrida, por ejemplo 18Z,
         * no se mezclan las imágenes generadas.
         */
        String carpetaCartas = "salidas/" + fecha + "/cartas" + cicloStr;
        String carpetaMeteogramas = "salidas/" + fecha + "/meteogramas" + cicloStr;

        new File(carpetaCartas).mkdirs();
        new File(carpetaMeteogramas).mkdirs();
        new File(carpetaCartas + "/cortoplazo").mkdirs();
        new File(carpetaCartas + "/largo_plazo").mkdirs();

        System.out.println("\n=== CONFIGURACIÓN AUTOMÁTICA ===");
        System.out.println("Fecha detectada: " + fecha);
        System.out.println("Ciclo detectado: " + cicloStr + "Z");
        System.out.println("Descarga GRIB: f000 a f084 cada 3 h");
        System.out.println("Cartas: " + HORAS_CARTAS);
        System.out.println("Carpeta cartas: " + carpetaCartas);
        System.out.println("Carpeta meteogramas: " + carpetaMeteogramas);
        System.out.println("Región:");
        System.out.println("  Top    = " + TOP);
        System.out.println("  Bottom = " + BOTTOM);
        System.out.println("  Left   = " + LEFT);
        System.out.println("  Right  = " + RIGHT);
        System.out.println("Borrar GRIB al final: " + (BORRAR_GRIBS_AL_FINAL ? "SI" : "NO"));
        System.out.println("================================");

        int descargasOk = 0;
        int descargasFail = 0;
        int cartasOk = 0;
        int cartasFail = 0;

        for (int horaPron = HORA_INICIAL_DESCARGA;
             horaPron <= HORA_FINAL_DESCARGA;
             horaPron += SALTO_DESCARGA) {

            try {
                System.out.println("\n========================================");
                System.out.println("Procesando pronóstico f" + String.format("%03d", horaPron));
                System.out.println("========================================");

                boolean debeGenerarCarta = HORAS_CARTAS.contains(horaPron);
                
                String carpetaCartasDestino = carpetaCartas;
                if (debeGenerarCarta) {
                    if (horaPron >= 12 && horaPron <= 36) {
                        carpetaCartasDestino = carpetaCartas + "/cortoplazo";
                    } else if (horaPron >= 48 && horaPron <= 84) {
                        carpetaCartasDestino = carpetaCartas + "/largo_plazo";
                    }
                }

                ResultadoPronostico resultado = procesarPronostico(
                        fecha,
                        ciclo,
                        horaPron,
                        TOP,
                        BOTTOM,
                        LEFT,
                        RIGHT,
                        debeGenerarCarta,
                        carpetaCartasDestino
                );

                if (resultado.descargado) {
                    descargasOk++;
                } else {
                    descargasFail++;
                }

                if (debeGenerarCarta) {
                    if (resultado.cartaGenerada) {
                        cartasOk++;
                    } else {
                        cartasFail++;
                    }
                }

            } catch (Exception e) {
                descargasFail++;
                System.out.println("❌ Error en f" + String.format("%03d", horaPron) + ": " + e.getMessage());
                e.printStackTrace();
            }
        }

        int meteogramasOk = 0;
        int meteogramasFail = 0;

        System.out.println("\n========================================");
        System.out.println("GENERACIÓN AUTOMÁTICA DE METEOGRAMAS");
        System.out.println("========================================");
        System.out.println("Carpeta destino meteogramas: " + carpetaMeteogramas);

        for (PuntoMeteograma punto : PUNTOS_METEOGRAMA) {
            System.out.println("\n----------------------------------------");
            System.out.println("Meteograma: " + punto.nombre);
            System.out.println("----------------------------------------");

            boolean ok = generarMeteogramaConPython(
                    "gribs/" + fecha,
                    carpetaMeteogramas,
                    punto.lat,
                    punto.lon,
                    punto.nombre
            );

            if (ok) {
                meteogramasOk++;
                System.out.println("✔ Meteograma generado: " + punto.nombre);
            } else {
                meteogramasFail++;
                System.out.println("❌ Falló meteograma: " + punto.nombre);
            }
        }

        if (BORRAR_GRIBS_AL_FINAL) {
            System.out.println("\n========================================");
            System.out.println("LIMPIEZA FINAL DE GRIB");
            System.out.println("========================================");
            borrarGribsEIdxDeFecha(fecha);
            borrarCarpetaSiEstaVacia(fecha);
        } else {
            System.out.println("\nℹ Los GRIB se conservaron en disco.");
        }

        System.out.println("\n=== RESUMEN FINAL ===");
        System.out.println("Descargas OK:        " + descargasOk);
        System.out.println("Descargas con error: " + descargasFail);
        System.out.println("Cartas OK:           " + cartasOk);
        System.out.println("Cartas con error:    " + cartasFail);
        System.out.println("Meteogramas OK:      " + meteogramasOk);
        System.out.println("Meteogramas error:   " + meteogramasFail);
        System.out.println("Carpeta cartas:      " + carpetaCartas);
        System.out.println("  → Cortoplazo (12/24/36h): " + carpetaCartas + "/cortoplazo");
        System.out.println("  → Largo plazo (48-84h):   " + carpetaCartas + "/largo_plazo");
        System.out.println("Carpeta meteogramas: " + carpetaMeteogramas);
        System.out.println("Proceso terminado.");
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

    private static ResultadoPronostico procesarPronostico(String fecha,
                                                          int ciclo,
                                                          int horaPron,
                                                          double top,
                                                          double bottom,
                                                          double left,
                                                          double right,
                                                          boolean generarCarta,
                                                          String carpetaCartas) throws IOException {

        String carpetaGribs = "gribs/" + fecha;

        new File(carpetaGribs).mkdirs();
        new File(carpetaCartas).mkdirs();

        String archivoLocal = construirNombreArchivoLocal(fecha, ciclo, horaPron, top, bottom, left, right);
        String url = construirURL(fecha, ciclo, horaPron, top, bottom, left, right);

        System.out.println("\nArchivo destino: " + archivoLocal);
        System.out.println("URL: " + url);

        boolean descargado = descargarArchivo(url, archivoLocal);

        if (!descargado) {
            System.out.println("❌ No se pudo obtener el archivo.");
            return new ResultadoPronostico(false, false);
        }

        if (!generarCarta) {
            System.out.println("ℹ GRIB descargado/conservado. No corresponde generar carta para f"
                    + String.format("%03d", horaPron));
            return new ResultadoPronostico(true, false);
        }

        String pngSalida = carpetaCartas + "/" +
                new File(archivoLocal).getName().replace(".grib2", ".png");

        if (Files.exists(Path.of(pngSalida))) {
            System.out.println("✔ La carta ya existe para esa hora, región y corrida, no se vuelve a generar:");
            System.out.println("  " + pngSalida);
            return new ResultadoPronostico(true, true);
        }

        boolean generado = generarMapaMSLPConPython(
                archivoLocal,
                pngSalida,
                top,
                bottom,
                left,
                right
        );

        if (generado) {
            System.out.println("✔ Carta generada y GRIB conservado para meteogramas: " + archivoLocal);
            System.out.println("  Salida carta: " + pngSalida);
        } else {
            System.out.println("⚠ Se conserva el GRIB para revisión: " + archivoLocal);
        }

        return new ResultadoPronostico(true, generado);
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

        return carpeta + "gfs_" + fecha + "_" + cicloStr +
                "_f" + String.format("%03d", horaPron) + areaSuffix + ".grib2";
    }

    private static String construirAreaSuffix(double top,
                                              double bottom,
                                              double left,
                                              double right) {
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
                                                    double top,
                                                    double bottom,
                                                    double left,
                                                    double right) {

        try {
            System.out.println("▶ Generando carta con Python...");
            System.out.println("  Usando Python: " + PYTHON_CMD);
            System.out.println("  Salida: " + salidaPNG);

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
                                                      String carpetaMeteogramas,
                                                      double latPunto,
                                                      double lonPunto,
                                                      String nombrePunto) {

        try {
            new File(carpetaMeteogramas).mkdirs();

            System.out.println("▶ Generando meteograma con Python...");
            System.out.println("  Punto: " + nombrePunto + " | Lat: " + latPunto + " | Lon: " + lonPunto);
            System.out.println("  Carpeta GRIB: " + carpetaGribs);
            System.out.println("  Carpeta salida meteograma: " + carpetaMeteogramas);

            ProcessBuilder pb = new ProcessBuilder(
                    PYTHON_CMD,
                    PYTHON_SCRIPT_METEOGRAMA,
                    carpetaGribs,
                    carpetaMeteogramas,
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

    private static class PuntoMeteograma {
        String nombre;
        double lat;
        double lon;

        PuntoMeteograma(String nombre, double lat, double lon) {
            this.nombre = nombre;
            this.lat = lat;
            this.lon = lon;
        }
    }

    private static class ResultadoPronostico {
        boolean descargado;
        boolean cartaGenerada;

        ResultadoPronostico(boolean descargado, boolean cartaGenerada) {
            this.descargado = descargado;
            this.cartaGenerada = cartaGenerada;
        }
    }
}
