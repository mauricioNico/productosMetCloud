package taf;

import java.io.BufferedReader;
import java.io.IOException;
import javax.imageio.ImageIO;
import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Generador de pronósticos automáticos orientativos a partir de datos GFS.
 *
 * Compatible con Java 17 y sin dependencias externas.
 *
 * Lee el CSV generado por meteograma_gfs.py, calcula el pronóstico corto
 * de cada localidad y crea UN ÚNICO PNG con todos los pronósticos.
 * No genera archivos TXT individuales.
 *
 * USO:
 *   java taf.GenerarTAF datos_taf.csv carpeta_salida
 *
 * Opcionalmente se puede indicar la ruta del escudo:
 *   java taf.GenerarTAF datos_taf.csv carpeta_salida imagenes/escudo_dmm.png
 *
 * Columnas esperadas:
 * nombre,fecha_hora,wind_dir,wind_kt,gust_kt,vis_m,temp_c,td_c,rh,
 * precip_mm,conv_precip_mm,cape,cin,reflectivity_dbz,low_cloud_pct,
 * ceiling_ft_agl
 *
 * IMPORTANTE:
 * El producto es automático/orientativo y requiere revisión profesional.
 */
public class GenerarTAF {

    // ============================================================
    // CONFIGURACION GENERAL
    // ============================================================

    private static final int HORAS_VALIDEZ = 24;

    // Producto PNG único
    private static final int PNG_ANCHO = 1800;
    private static final int PNG_MARGEN = 60;
    private static final int PNG_COLUMNAS = 2;
    private static final int PNG_SEPARACION_COLUMNAS = 30;
    private static final int PNG_SEPARACION_FILAS = 24;

    private static final String RUTA_ESCUDO_PREDETERMINADA = "imagenes/escudo_dmm.png";

    private static final String AVISO_ORIENTATIVO =
            "Estos pronósticos constituyen una salida automática a partir de los meteogramas " +
            "pronosticados y deben solo considerarse de carácter orientativo. Consulte los " +
            "pronósticos por cada unidad de la FAA en " +
            "https://imagenesmeteorologicas.faa.mil.ar/app/model/verinfo.php";

    // Viento
    private static final double RAFAGA_DIFERENCIA_MIN_KT = 10.0;
    private static final double CAMBIO_DIRECCION_SIGNIFICATIVO = 60.0;
    private static final double VIENTO_MIN_CAMBIO_DIRECCION_KT = 10.0;
    private static final double CAMBIO_VELOCIDAD_SIGNIFICATIVO_KT = 10.0;

    // Niebla / neblina
    private static final double FG_RH_MIN = 95.0;
    private static final double FG_SPREAD_MAX = 1.5;
    private static final double FG_VIENTO_MAX_KT = 6.0;
    private static final double FG_PRECIP_MAX_MM = 0.2;

    private static final double BR_RH_MIN = 90.0;
    private static final double BR_SPREAD_MAX = 2.5;

    // Tormenta
    private static final double TS_CAPE_MIN = 1000.0;
    private static final double TS_CIN_MAX = 50.0;
    private static final double TS_REFL_MIN_DBZ = 35.0;
    private static final double TS_CONV_PRECIP_MIN_MM = 0.5;

    // Chaparrones
    private static final double SHRA_CONV_PRECIP_MIN_MM = 0.2;
    private static final double SHRA_CAPE_MIN = 500.0;
    private static final double SHRA_REFL_MIN_DBZ = 25.0;

    // Umbrales operacionales utilizados para detectar cambios.
    private static final double[] UMBRALES_VISIBILIDAD = {
            10000, 5000, 3000, 1500, 800, 600, 350, 150
    };

    private static final double[] UMBRALES_TECHO = {
            1500, 1000, 500, 200, 100
    };

    // ============================================================
    // MAIN
    // ============================================================

    public static void main(String[] args) {

        // Necesario para GitHub Actions / servidores Linux sin entorno gráfico.
        System.setProperty("java.awt.headless", "true");
        Locale.setDefault(Locale.US);

        if (args.length < 1) {
            mostrarAyuda();
            return;
        }

        Path archivoEntrada = Paths.get(args[0]);

        Path carpetaSalida = args.length >= 2
                ? Paths.get(args[1])
                : Paths.get("taf_salida");

        String fecha = null;
        String cicloStr = null;
        Path rutaEscudo = Paths.get(RUTA_ESCUDO_PREDETERMINADA);

        /*
         * Formas admitidas:
         *
         * 1) java taf.GenerarTAF datos.csv carpeta
         *    -> fecha/ciclo se infieren cuando es posible.
         *
         * 2) java taf.GenerarTAF datos.csv carpeta imagenes/escudo_dmm.png
         *    -> compatibilidad con la versión anterior.
         *
         * 3) java taf.GenerarTAF datos.csv carpeta 20260910 12
         *    -> fecha y ciclo explícitos.
         *
         * 4) java taf.GenerarTAF datos.csv carpeta 20260910 12 imagenes/escudo_dmm.png
         */
        if (args.length >= 4) {
            fecha = args[2];
            cicloStr = args[3];

            if (args.length >= 5) {
                rutaEscudo = Paths.get(args[4]);
            }
        } else if (args.length >= 3) {
            rutaEscudo = Paths.get(args[2]);
        }

        try {
            ejecutar(
                    archivoEntrada,
                    carpetaSalida,
                    fecha,
                    cicloStr,
                    rutaEscudo
            );

        } catch (Exception e) {
            System.err.println("ERROR GENERAL: " + e.getMessage());
            e.printStackTrace();
        }
    }

    /**
     * Compatibilidad con llamadas anteriores.
     * Si no se suministran fecha/ciclo, se intentan inferir del CSV.
     */
    public static void generar(String archivoCsv, String carpetaSalida) {
        try {
            ejecutar(
                    Paths.get(archivoCsv),
                    Paths.get(carpetaSalida),
                    null,
                    null,
                    Paths.get(RUTA_ESCUDO_PREDETERMINADA)
            );
        } catch (Exception e) {
            throw new RuntimeException("Error generando pronósticos automáticos", e);
        }
    }

    /**
     * Método utilizado por DescargaGFSMenu.
     *
     * La fecha corresponde a la fecha de la corrida GFS y cicloStr al ciclo
     * detectado (00, 06, 12 o 18). La hora de emisión/validez del producto
     * se fija en:
     *
     *   ciclos 00/06 -> 12Z, válido 12/12
     *   ciclos 12/18 -> 18Z, válido 18/18
     */
    public static void generar(
            String archivoCsv,
            String carpetaSalida,
            String fecha,
            String cicloStr) {

        try {
            ejecutar(
                    Paths.get(archivoCsv),
                    Paths.get(carpetaSalida),
                    fecha,
                    cicloStr,
                    Paths.get(RUTA_ESCUDO_PREDETERMINADA)
            );
        } catch (Exception e) {
            throw new RuntimeException("Error generando pronósticos automáticos", e);
        }
    }

    /**
     * Variante con ruta de escudo explícita.
     */
    public static void generar(
            String archivoCsv,
            String carpetaSalida,
            String fecha,
            String cicloStr,
            String rutaEscudo) {

        try {
            ejecutar(
                    Paths.get(archivoCsv),
                    Paths.get(carpetaSalida),
                    fecha,
                    cicloStr,
                    Paths.get(rutaEscudo)
            );
        } catch (Exception e) {
            throw new RuntimeException("Error generando pronósticos automáticos", e);
        }
    }

    private static void ejecutar(
            Path archivoEntrada,
            Path carpetaSalida,
            String fecha,
            String cicloStr,
            Path rutaEscudo) throws IOException {

        System.setProperty("java.awt.headless", "true");
        Locale.setDefault(Locale.US);

        if (!Files.exists(archivoEntrada)) {
            throw new IOException(
                    "No existe el archivo: " + archivoEntrada.toAbsolutePath()
            );
        }

        Files.createDirectories(carpetaSalida);
        limpiarSalidasAnteriores(carpetaSalida);

        List<RegistroHorario> registros = leerCSV(archivoEntrada);

        if (registros.isEmpty()) {
            throw new IOException("El CSV no contiene registros utilizables.");
        }

        Map<String, List<RegistroHorario>> porLocalidad = agruparPorLocalidad(registros);

        LocalDateTime inicioValidez = calcularInicioValidez(
                fecha,
                cicloStr,
                archivoEntrada,
                registros
        );

        LocalDateTime finValidez = inicioValidez.plusHours(HORAS_VALIDEZ);

        /*
         * En este producto la emisión general coincide con el comienzo
         * de la validez solicitada:
         *
         * mañana -> 12Z / tarde -> 18Z.
         */
        LocalDateTime emisionGeneral = inicioValidez;

        Map<String, PronosticoLocalidad> pronosticos = new LinkedHashMap<>();

        System.out.println("====================================================");
        System.out.println(" GENERADOR DE PRONOSTICOS AUTOMATICOS - PNG UNICO");
        System.out.println("====================================================");
        System.out.println("Archivo: " + archivoEntrada.toAbsolutePath());
        System.out.println("Localidades encontradas: " + porLocalidad.size());
        System.out.println("Emision general: " + formatearEmisionTexto(emisionGeneral));
        System.out.println("Validez: " + formatearValidezTexto(inicioValidez, finValidez));
        System.out.println();

        for (Map.Entry<String, List<RegistroHorario>> entry : porLocalidad.entrySet()) {

            String nombre = entry.getKey();
            List<RegistroHorario> datos = entry.getValue();

            try {
                PronosticoLocalidad pronostico = generarPronostico(
                        nombre,
                        datos,
                        inicioValidez,
                        finValidez
                );

                pronosticos.put(nombre, pronostico);

                System.out.printf(
                        Locale.US,
                        "OK  %s | Tmax %.1f C | Tmin %.1f C%n",
                        nombre,
                        pronostico.tmax,
                        pronostico.tmin
                );

            } catch (Exception e) {
                System.err.println(
                        "ERROR generando pronostico para " + nombre + ": " + e.getMessage()
                );
            }
        }

        if (pronosticos.isEmpty()) {
            throw new IOException("No se pudo generar ningún pronóstico.");
        }

        String nombrePng = String.format(
                "pronosticos_automaticos_%04d%02d%02d_%02dZ.png",
                inicioValidez.getYear(),
                inicioValidez.getMonthValue(),
                inicioValidez.getDayOfMonth(),
                inicioValidez.getHour()
        );

        Path salidaPng = carpetaSalida.resolve(nombrePng);

        generarProductoPNG(
                pronosticos,
                salidaPng,
                rutaEscudo,
                emisionGeneral,
                inicioValidez,
                finValidez
        );

        System.out.println();
        System.out.println("PNG generado: " + salidaPng.toAbsolutePath());
        System.out.println("Proceso finalizado.");
    }

    private static LocalDateTime calcularInicioValidez(
            String fecha,
            String cicloStr,
            Path archivoEntrada,
            List<RegistroHorario> registros) {

        String fechaEfectiva = fecha;
        String cicloEfectivo = cicloStr;

        if (fechaEfectiva == null || fechaEfectiva.isBlank()) {

            LocalDateTime primero = registros.stream()
                    .map(r -> r.fechaHora)
                    .min(LocalDateTime::compareTo)
                    .orElseThrow();

            fechaEfectiva = primero.format(DateTimeFormatter.BASIC_ISO_DATE);
        }

        if (cicloEfectivo == null || cicloEfectivo.isBlank()) {
            cicloEfectivo = inferirCicloDesdeNombre(archivoEntrada);

            if (cicloEfectivo == null) {
                /*
                 * Respaldo: si no podemos inferir el ciclo del nombre del CSV,
                 * usamos 12Z como producto matutino.
                 */
                cicloEfectivo = "00";
            }
        }

        LocalDate dia = LocalDate.parse(
                fechaEfectiva,
                DateTimeFormatter.BASIC_ISO_DATE
        );

        int ciclo;
        try {
            ciclo = Integer.parseInt(cicloEfectivo);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException(
                    "Ciclo GFS inválido: " + cicloEfectivo
            );
        }

        int horaEmision = ciclo < 12 ? 12 : 18;

        return dia.atTime(horaEmision, 0);
    }

    private static String inferirCicloDesdeNombre(Path archivoEntrada) {

        String nombre = archivoEntrada.getFileName().toString();

        java.util.regex.Matcher m =
                java.util.regex.Pattern.compile(
                        ".*_([0-9]{2})\\.csv$",
                        java.util.regex.Pattern.CASE_INSENSITIVE
                ).matcher(nombre);

        if (m.matches()) {
            return m.group(1);
        }

        return null;
    }

    private static void mostrarAyuda() {
        System.out.println("""
                Uso recomendado desde DescargaGFSMenu:
                  GenerarTAF.generar(archivoCsv, carpetaSalida, fecha, cicloStr)

                Desde consola:
                  java taf.GenerarTAF datos_taf.csv carpeta_salida 20260910 00
                  java taf.GenerarTAF datos_taf.csv carpeta_salida 20260910 12

                Opcionalmente:
                  java taf.GenerarTAF datos_taf.csv carpeta_salida 20260910 12 imagenes/escudo_dmm.png

                Reglas de validez:
                  ciclos 00/06 -> emisión 12Z, validez 12/12
                  ciclos 12/18 -> emisión 18Z, validez 18/18

                El resultado es un único PNG con todos los pronósticos.
                """);
    }

    private static void limpiarSalidasAnteriores(Path carpetaSalida) {
        try (java.util.stream.Stream<Path> stream = Files.list(carpetaSalida)) {
            for (Path p : stream.toList()) {
                String nombre = p.getFileName().toString();
                boolean txtAnterior = nombre.startsWith("TAF_") && nombre.endsWith(".txt");
                boolean pngAnterior = nombre.startsWith("pronosticos_automaticos_") && nombre.endsWith(".png");

                if (txtAnterior || pngAnterior) {
                    try {
                        Files.deleteIfExists(p);
                    } catch (IOException e) {
                        System.out.println("ADVERTENCIA: no se pudo borrar salida anterior: " + p);
                    }
                }
            }
        } catch (IOException e) {
            System.out.println("ADVERTENCIA: no se pudo revisar la carpeta de salida: " + e.getMessage());
        }
    }

    // ============================================================
    // GENERACION DEL PRONOSTICO POR LOCALIDAD
    // ============================================================

    private static PronosticoLocalidad generarPronostico(
            String nombre,
            List<RegistroHorario> datos,
            LocalDateTime inicio,
            LocalDateTime fin) {

        datos.sort(Comparator.comparing(r -> r.fechaHora));

        List<RegistroHorario> periodo = new ArrayList<>();

        for (RegistroHorario r : datos) {
            if (!r.fechaHora.isBefore(inicio) && r.fechaHora.isBefore(fin)) {
                periodo.add(r);
            }
        }

        if (periodo.size() < 2) {
            throw new IllegalArgumentException(
                    "Se necesitan al menos 2 tiempos de datos dentro del período "
                            + formatearValidezTexto(inicio, fin)
            );
        }

        RegistroHorario inicial = periodo.get(0);
        List<GrupoCambio> grupos = detectarCambios(periodo);

        StringBuilder sb = new StringBuilder();
        sb.append(formatearEstado(inicial));

        for (GrupoCambio grupo : grupos) {
            sb.append("\n");

            switch (grupo.tipo) {
                case FM -> {
                    sb.append("FM")
                      .append(formatearFM(grupo.desde))
                      .append(" ")
                      .append(formatearEstado(grupo.estado));
                }

                case BECMG -> {
                    sb.append("BECMG ")
                      .append(formatearPeriodo(grupo.desde, grupo.hasta))
                      .append(" ")
                      .append(formatearEstado(grupo.estado));
                }

                case TEMPO -> {
                    sb.append("TEMPO ")
                      .append(formatearPeriodo(grupo.desde, grupo.hasta))
                      .append(" ")
                      .append(formatearEstado(grupo.estado));
                }
            }
        }

        RegistroHorario registroMax = null;
        RegistroHorario registroMin = null;

        for (RegistroHorario r : periodo) {

            if (!Double.isFinite(r.temperaturaC)) {
                continue;
            }

            if (registroMax == null || r.temperaturaC > registroMax.temperaturaC) {
                registroMax = r;
            }

            if (registroMin == null || r.temperaturaC < registroMin.temperaturaC) {
                registroMin = r;
            }
        }

        double tmax = registroMax == null ? Double.NaN : registroMax.temperaturaC;
        double tmin = registroMin == null ? Double.NaN : registroMin.temperaturaC;

        LocalDateTime horaTmax = registroMax == null ? null : registroMax.fechaHora;
        LocalDateTime horaTmin = registroMin == null ? null : registroMin.fechaHora;

        return new PronosticoLocalidad(
                nombre,
                sb.toString(),
                tmax,
                tmin,
                horaTmax,
                horaTmin
        );
    }

    // ============================================================
    // DETECCION DE FM / BECMG / TEMPO
    // ============================================================

    private static List<GrupoCambio> detectarCambios(List<RegistroHorario> estados) {

        List<GrupoCambio> grupos = new ArrayList<>();

        RegistroHorario predominante = estados.get(0);

        int i = 1;

        while (i < estados.size()) {

            RegistroHorario actual = estados.get(i);

            if (!cambioSignificativo(predominante, actual)) {
                i++;
                continue;
            }

            // ----------------------------------------------------
            // 1) TEMPO:
            // deterioro breve que luego retorna aproximadamente
            // a la condicion predominante.
            // ----------------------------------------------------
            int indiceRetorno = buscarRetornoTemporal(estados, i, predominante);

            if (indiceRetorno > i && esDeterioro(predominante, actual)) {

                LocalDateTime desde = actual.fechaHora;
                LocalDateTime hasta = estados.get(indiceRetorno).fechaHora;

                grupos.add(
                        new GrupoCambio(
                                TipoGrupo.TEMPO,
                                desde,
                                hasta,
                                peorEstado(estados, i, indiceRetorno - 1)
                        )
                );

                i = indiceRetorno;
                continue;
            }

            // ----------------------------------------------------
            // 2) FM:
            // cambio relativamente abrupto y persistente.
            // ----------------------------------------------------
            if (esPersistente(estados, i)) {

                grupos.add(
                        new GrupoCambio(
                                TipoGrupo.FM,
                                actual.fechaHora,
                                null,
                                actual
                        )
                );

                predominante = actual;
                i++;
                continue;
            }

            // ----------------------------------------------------
            // 3) BECMG:
            // buscamos una nueva condicion estable en las
            // siguientes 2 a 4 horas.
            // ----------------------------------------------------
            int destinoBECMG = buscarDestinoBECMG(estados, i, predominante);

            if (destinoBECMG > i) {

                RegistroHorario destino = estados.get(destinoBECMG);

                grupos.add(
                        new GrupoCambio(
                                TipoGrupo.BECMG,
                                actual.fechaHora,
                                destino.fechaHora,
                                destino
                        )
                );

                predominante = destino;
                i = destinoBECMG + 1;
                continue;
            }

            // Si no podemos clasificarlo con seguridad, no abrimos
            // un grupo de cambio por una oscilacion aislada.
            i++;
        }

        return grupos;
    }

    private static int buscarRetornoTemporal(
            List<RegistroHorario> estados,
            int inicioCambio,
            RegistroHorario predominante) {

        // Con datos horarios deterministas usamos una heuristica:
        // buscamos retorno en las siguientes 1-3 horas.
        int limite = Math.min(estados.size() - 1, inicioCambio + 3);

        for (int j = inicioCambio + 1; j <= limite; j++) {
            if (condicionesSimilares(predominante, estados.get(j))) {
                return j;
            }
        }

        return -1;
    }

    private static boolean esPersistente(List<RegistroHorario> estados, int indice) {

        if (indice >= estados.size() - 1) {
            return true;
        }

        RegistroHorario actual = estados.get(indice);
        RegistroHorario siguiente = estados.get(indice + 1);

        if (!condicionesSimilares(actual, siguiente)) {
            return false;
        }

        // Si existe una tercera hora, mejora la confianza.
        if (indice + 2 < estados.size()) {
            RegistroHorario tercera = estados.get(indice + 2);

            if (condicionesSimilares(actual, tercera)) {
                return true;
            }
        }

        return true;
    }

    private static int buscarDestinoBECMG(
            List<RegistroHorario> estados,
            int inicio,
            RegistroHorario predominante) {

        int limite = Math.min(estados.size() - 1, inicio + 4);

        for (int j = inicio + 2; j <= limite; j++) {

            RegistroHorario candidato = estados.get(j);

            if (!cambioSignificativo(predominante, candidato)) {
                continue;
            }

            if (esPersistente(estados, j)) {
                return j;
            }
        }

        return -1;
    }

    // ============================================================
    // CAMBIOS SIGNIFICATIVOS
    // ============================================================

    private static boolean cambioSignificativo(
            RegistroHorario anterior,
            RegistroHorario actual) {

        return cambioVientoSignificativo(anterior, actual)
                || cruzaUmbralVisibilidad(anterior.visibilidadMetros, actual.visibilidadMetros)
                || cambioTechoSignificativo(anterior, actual)
                || cambioFenomenoSignificativo(anterior, actual);
    }

    private static boolean cambioVientoSignificativo(
            RegistroHorario a,
            RegistroHorario b) {

        double diferenciaDireccion =
                diferenciaAngular(a.direccionViento, b.direccionViento);

        double maxViento = Math.max(a.vientoKt, b.vientoKt);

        boolean cambioDireccion =
                diferenciaDireccion >= CAMBIO_DIRECCION_SIGNIFICATIVO
                        && maxViento >= VIENTO_MIN_CAMBIO_DIRECCION_KT;

        boolean cambioVelocidad =
                Math.abs(a.vientoKt - b.vientoKt)
                        >= CAMBIO_VELOCIDAD_SIGNIFICATIVO_KT;

        boolean cambioRafaga =
                Math.abs(valorSeguro(a.rafagaKt) - valorSeguro(b.rafagaKt)) >= 10
                        && Math.max(a.vientoKt, b.vientoKt) >= 15;

        return cambioDireccion || cambioVelocidad || cambioRafaga;
    }

    private static boolean cruzaUmbralVisibilidad(double a, double b) {

        if (Double.isNaN(a) || Double.isNaN(b)) {
            return false;
        }

        for (double umbral : UMBRALES_VISIBILIDAD) {
            if ((a >= umbral && b < umbral)
                    || (a < umbral && b >= umbral)) {
                return true;
            }
        }

        return false;
    }

    private static boolean cambioTechoSignificativo(
            RegistroHorario a,
            RegistroHorario b) {

        if (Double.isNaN(a.techoFtAgl) || Double.isNaN(b.techoFtAgl)) {
            return false;
        }

        boolean aTecho = esTecho(a);
        boolean bTecho = esTecho(b);

        // Cambio entre SCT/FEW y BKN/OVC en niveles bajos.
        if (aTecho != bTecho
                && Math.min(a.techoFtAgl, b.techoFtAgl) <= 1500) {
            return true;
        }

        if (aTecho && bTecho) {
            for (double umbral : UMBRALES_TECHO) {
                if ((a.techoFtAgl >= umbral && b.techoFtAgl < umbral)
                        || (a.techoFtAgl < umbral && b.techoFtAgl >= umbral)) {
                    return true;
                }
            }
        }

        return false;
    }

    private static boolean cambioFenomenoSignificativo(
            RegistroHorario a,
            RegistroHorario b) {

        String wxA = detectarFenomeno(a);
        String wxB = detectarFenomeno(b);

        return !wxA.equals(wxB)
                && severidadFenomeno(wxA) != severidadFenomeno(wxB);
    }

    // ============================================================
    // SIMILITUD Y DETERIORO
    // ============================================================

    private static boolean condicionesSimilares(
            RegistroHorario a,
            RegistroHorario b) {

        if (cruzaUmbralVisibilidad(a.visibilidadMetros, b.visibilidadMetros)) {
            return false;
        }

        if (cambioTechoSignificativo(a, b)) {
            return false;
        }

        if (cambioFenomenoSignificativo(a, b)) {
            return false;
        }

        if (cambioVientoSignificativo(a, b)) {
            return false;
        }

        return true;
    }

    private static boolean esDeterioro(
            RegistroHorario base,
            RegistroHorario candidato) {

        int scoreBase = scoreCondicion(base);
        int scoreCandidato = scoreCondicion(candidato);

        return scoreCandidato > scoreBase;
    }

    private static int scoreCondicion(RegistroHorario e) {

        int score = 0;

        // Visibilidad
        double vis = e.visibilidadMetros;

        if (!Double.isNaN(vis)) {
            if (vis < 600) score += 7;
            else if (vis < 800) score += 6;
            else if (vis < 1500) score += 5;
            else if (vis < 3000) score += 4;
            else if (vis < 5000) score += 3;
            else if (vis < 10000) score += 1;
        }

        // Techo
        if (esTecho(e) && !Double.isNaN(e.techoFtAgl)) {
            if (e.techoFtAgl < 200) score += 7;
            else if (e.techoFtAgl < 500) score += 6;
            else if (e.techoFtAgl < 1000) score += 5;
            else if (e.techoFtAgl < 1500) score += 3;
            else if (e.techoFtAgl < 3000) score += 1;
        }

        // Tiempo significativo
        score += severidadFenomeno(detectarFenomeno(e));

        return score;
    }

    private static RegistroHorario peorEstado(
            List<RegistroHorario> estados,
            int desde,
            int hastaInclusive) {

        RegistroHorario peor = estados.get(desde);
        int peorScore = scoreCondicion(peor);

        for (int i = desde + 1; i <= hastaInclusive; i++) {
            RegistroHorario candidato = estados.get(i);
            int score = scoreCondicion(candidato);

            if (score > peorScore) {
                peor = candidato;
                peorScore = score;
            }
        }

        return peor;
    }

    // ============================================================
    // TRADUCCION METEOROLOGICA A TAF
    // ============================================================

    private static String formatearEstado(RegistroHorario e) {

        List<String> partes = new ArrayList<>();

        partes.add(formatearViento(e));
        partes.add(formatearVisibilidad(e.visibilidadMetros));

        String fenomeno = detectarFenomeno(e);

        if (!fenomeno.isBlank()) {
            partes.add(fenomeno);
        }

        String nubes = formatearNubes(e, fenomeno);

        if (!nubes.isBlank()) {
            partes.add(nubes);
        }

        return String.join(" ", partes);
    }

    private static String formatearViento(RegistroHorario e) {

        int velocidad = (int) Math.round(Math.max(0, e.vientoKt));

        if (velocidad == 0) {
            return "00000KT";
        }

        String direccion;

        if (velocidad <= 3 || Double.isNaN(e.direccionViento)) {
            direccion = "VRB";
        } else {
            int dir = redondearDireccion10(e.direccionViento);
            direccion = String.format("%03d", dir);
        }

        StringBuilder sb = new StringBuilder();

        sb.append(direccion)
          .append(String.format("%02d", Math.min(velocidad, 99)));

        if (!Double.isNaN(e.rafagaKt)) {

            int rafaga = (int) Math.round(e.rafagaKt);

            if (rafaga >= velocidad + RAFAGA_DIFERENCIA_MIN_KT) {
                sb.append("G")
                  .append(String.format("%02d", Math.min(rafaga, 99)));
            }
        }

        sb.append("KT");

        return sb.toString();
    }

    private static String formatearVisibilidad(double visibilidadMetros) {

        if (Double.isNaN(visibilidadMetros)) {
            return "9999";
        }

        double vis = Math.max(0, visibilidadMetros);

        if (vis >= 10000) {
            return "9999";
        }

        int redondeada;

        if (vis < 800) {
            redondeada = (int) Math.floor(vis / 50.0) * 50;
        } else if (vis < 5000) {
            redondeada = (int) Math.floor(vis / 100.0) * 100;
        } else {
            redondeada = (int) Math.floor(vis / 1000.0) * 1000;
        }

        redondeada = Math.max(50, redondeada);

        return String.format("%04d", redondeada);
    }

    private static String detectarFenomeno(RegistroHorario e) {

        // --------------------------------------------------------
        // Tormenta: criterio deliberadamente conservador.
        // CAPE solo NO genera TSRA.
        // --------------------------------------------------------
        if (valorSeguro(e.cape) >= TS_CAPE_MIN
                && valorSeguro(e.cin) <= TS_CIN_MAX
                && valorSeguro(e.reflectividadDbz) >= TS_REFL_MIN_DBZ
                && valorSeguro(e.precipitacionConvectivaMm) >= TS_CONV_PRECIP_MIN_MM) {

            return "TSRA";
        }

        // --------------------------------------------------------
        // Chaparrones.
        // --------------------------------------------------------
        if (valorSeguro(e.precipitacionConvectivaMm) >= SHRA_CONV_PRECIP_MIN_MM
                || (valorSeguro(e.cape) >= SHRA_CAPE_MIN
                    && valorSeguro(e.reflectividadDbz) >= SHRA_REFL_MIN_DBZ
                    && valorSeguro(e.precipitacionMm) >= 0.2)) {

            return "SHRA";
        }

        // --------------------------------------------------------
        // Lluvia estratiforme.
        // --------------------------------------------------------
        if (valorSeguro(e.precipitacionMm) > 4.0) {
            return "+RA";
        }

        if (valorSeguro(e.precipitacionMm) >= 1.0) {
            return "RA";
        }

        if (valorSeguro(e.precipitacionMm) >= 0.1) {
            return "-RA";
        }

        // --------------------------------------------------------
        // Niebla / neblina.
        // Se usa VIS + RH + spread + viento.
        // --------------------------------------------------------
        double rh = e.humedadRelativa;

        if (Double.isNaN(rh)
                && !Double.isNaN(e.temperaturaC)
                && !Double.isNaN(e.puntoRocioC)) {
            rh = calcularRH(e.temperaturaC, e.puntoRocioC);
        }

        double spread = Double.NaN;

        if (!Double.isNaN(e.temperaturaC)
                && !Double.isNaN(e.puntoRocioC)) {
            spread = e.temperaturaC - e.puntoRocioC;
        }

        if (!Double.isNaN(e.visibilidadMetros)
                && e.visibilidadMetros < 1000
                && !Double.isNaN(rh)
                && rh >= FG_RH_MIN
                && !Double.isNaN(spread)
                && spread <= FG_SPREAD_MAX
                && e.vientoKt <= FG_VIENTO_MAX_KT
                && valorSeguro(e.precipitacionMm) < FG_PRECIP_MAX_MM) {

            return "FG";
        }

        if (!Double.isNaN(e.visibilidadMetros)
                && e.visibilidadMetros >= 1000
                && e.visibilidadMetros <= 5000
                && !Double.isNaN(rh)
                && rh >= BR_RH_MIN
                && !Double.isNaN(spread)
                && spread <= BR_SPREAD_MAX) {

            return "BR";
        }

        return "";
    }

    private static String formatearNubes(
            RegistroHorario e,
            String fenomeno) {

        if (Double.isNaN(e.nubosidadBajaPct)) {
            return "";
        }

        double cobertura = Math.max(0, Math.min(100, e.nubosidadBajaPct));

        if (cobertura < 10) {
            return "NSC";
        }

        // Para poder informar FEW/SCT/BKN/OVC necesitamos altura.
        if (Double.isNaN(e.techoFtAgl)) {
            return "";
        }

        String cantidad;

        if (cobertura <= 25) {
            cantidad = "FEW";
        } else if (cobertura <= 50) {
            cantidad = "SCT";
        } else if (cobertura <= 87) {
            cantidad = "BKN";
        } else {
            cantidad = "OVC";
        }

        int centenasPies =
                (int) Math.round(Math.max(0, e.techoFtAgl) / 100.0);

        centenasPies = Math.min(centenasPies, 999);

        String nube =
                cantidad + String.format("%03d", centenasPies);

        if ("TSRA".equals(fenomeno)) {
            nube += "CB";
        }

        return nube;
    }

    private static boolean esTecho(RegistroHorario e) {

        if (Double.isNaN(e.nubosidadBajaPct)) {
            return false;
        }

        return e.nubosidadBajaPct > 50;
    }

    // ============================================================
    // FORMATO DE FECHAS TAF
    // ============================================================

    private static String formatearEmision(LocalDateTime fecha) {

        return String.format(
                "%02d%02d%02dZ",
                fecha.getDayOfMonth(),
                fecha.getHour(),
                fecha.getMinute()
        );
    }

    private static String formatearPeriodo(
            LocalDateTime desde,
            LocalDateTime hasta) {

        return String.format(
                "%02d%02d/%02d%02d",
                desde.getDayOfMonth(),
                desde.getHour(),
                hasta.getDayOfMonth(),
                hasta.getHour()
        );
    }

    private static String formatearFM(LocalDateTime fecha) {

        return String.format(
                "%02d%02d%02d",
                fecha.getDayOfMonth(),
                fecha.getHour(),
                fecha.getMinute()
        );
    }

    private static String formatearEmisionTexto(LocalDateTime fecha) {
        return String.format("%02d/%02dZ", fecha.getDayOfMonth(), fecha.getHour());
    }

    private static String formatearValidezTexto(LocalDateTime desde, LocalDateTime hasta) {
        return String.format(
                "%02d/%02dZ - %02d/%02dZ",
                desde.getDayOfMonth(), desde.getHour(),
                hasta.getDayOfMonth(), hasta.getHour()
        );
    }

    private static String nombreSeguroArchivo(String nombre) {
        return nombre.trim()
                .replace(' ', '_')
                .replaceAll("[^A-Za-z0-9_-]", "_");
    }

    // ============================================================
    // PRODUCTO PNG UNICO
    // ============================================================

    private static void generarProductoPNG(
            Map<String, PronosticoLocalidad> pronosticos,
            Path salidaPng,
            Path rutaEscudo,
            LocalDateTime emisionGeneral,
            LocalDateTime inicioValidez,
            LocalDateTime finValidez) throws IOException {

        Font fuenteTitulo = new Font("SansSerif", Font.BOLD, 44);
        Font fuenteSubtitulo = new Font("SansSerif", Font.BOLD, 28);
        Font fuenteMeta = new Font("SansSerif", Font.PLAIN, 22);
        Font fuenteAviso = new Font("SansSerif", Font.BOLD, 21);
        Font fuenteLugar = new Font("SansSerif", Font.BOLD, 25);
        Font fuenteTemperatura = new Font("SansSerif", Font.BOLD, 18);
        Font fuenteTAF = new Font("Monospaced", Font.PLAIN, 20);
        Font fuentePie = new Font("SansSerif", Font.PLAIN, 16);

        BufferedImage auxiliar = new BufferedImage(10, 10, BufferedImage.TYPE_INT_ARGB);
        Graphics2D ga = auxiliar.createGraphics();
        configurarRenderizado(ga);

        int anchoUtil = PNG_ANCHO - 2 * PNG_MARGEN;
        int anchoColumna = (anchoUtil - PNG_SEPARACION_COLUMNAS) / PNG_COLUMNAS;
        int anchoTextoTarjeta = anchoColumna - 44;

        FontMetrics fmTaf = ga.getFontMetrics(fuenteTAF);
        FontMetrics fmLugar = ga.getFontMetrics(fuenteLugar);
        FontMetrics fmTemperatura = ga.getFontMetrics(fuenteTemperatura);
        FontMetrics fmAviso = ga.getFontMetrics(fuenteAviso);

        List<TarjetaPronostico> tarjetas = new ArrayList<>();

        for (Map.Entry<String, PronosticoLocalidad> entry : pronosticos.entrySet()) {

            PronosticoLocalidad p = entry.getValue();

            List<String> lineas = envolverTAF(
                    p.texto,
                    fmTaf,
                    anchoTextoTarjeta
            );

            String resumenTemperaturas = formatearTemperaturas(p);

            int altoTarjeta = 28
                    + fmLugar.getHeight()
                    + 12
                    + fmTemperatura.getHeight()
                    + 17
                    + lineas.size() * (fmTaf.getHeight() + 3)
                    + 26;

            tarjetas.add(
                    new TarjetaPronostico(
                            entry.getKey(),
                            resumenTemperaturas,
                            lineas,
                            altoTarjeta
                    )
            );
        }

        List<String> lineasAviso = envolverTexto(AVISO_ORIENTATIVO, fmAviso, anchoUtil - 60);
        int altoAviso = 34 + lineasAviso.size() * (fmAviso.getHeight() + 3) + 30;

        int altoCabecera = 245;
        int altoContenido = calcularAltoContenido(tarjetas);
        int altoPie = 70;

        int altoTotal = PNG_MARGEN
                + altoCabecera
                + altoAviso
                + 28
                + altoContenido
                + altoPie
                + PNG_MARGEN;

        ga.dispose();

        BufferedImage imagen = new BufferedImage(PNG_ANCHO, altoTotal, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = imagen.createGraphics();
        configurarRenderizado(g);

        Color azul = new Color(17, 91, 132);
        Color celeste = new Color(226, 243, 250);
        Color fondoTarjeta = new Color(247, 249, 251);
        Color borde = new Color(184, 194, 202);
        Color textoSecundario = new Color(70, 70, 70);

        g.setColor(Color.WHITE);
        g.fillRect(0, 0, PNG_ANCHO, altoTotal);

        // -------------------------
        // CABECERA
        // -------------------------
        BufferedImage logo = cargarYRecortarLogo(rutaEscudo);

        int logoX = PNG_MARGEN;
        int logoY = PNG_MARGEN - 10;
        int logoMaxW = 205;
        int logoMaxH = 190;

        if (logo != null) {
            dibujarImagenAjustada(g, logo, logoX, logoY, logoMaxW, logoMaxH);
        } else {
            g.setColor(celeste);
            g.fillRoundRect(logoX, logoY, logoMaxW, logoMaxH, 20, 20);
            g.setColor(azul);
            g.setFont(new Font("SansSerif", Font.BOLD, 22));
            g.drawString("FAA - DGSAM", logoX + 25, logoY + 95);
        }

        int xTitulo = PNG_MARGEN + 245;
        int yTitulo = PNG_MARGEN + 45;

        g.setColor(azul);
        g.setFont(fuenteTitulo);
        g.drawString("PRONÓSTICOS AUTOMÁTICOS ORIENTATIVOS", xTitulo, yTitulo);

        g.setColor(Color.BLACK);
        g.setFont(fuenteSubtitulo);
        g.drawString("Departamento Meteorología Militar - FAA / DGSAM", xTitulo, yTitulo + 47);

        DateTimeFormatter fmtEmision = DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm 'UTC'");
        DateTimeFormatter fmtValidez = DateTimeFormatter.ofPattern("dd/MM/yyyy HH'Z'");

        g.setFont(fuenteMeta);
        g.setColor(textoSecundario);
        g.drawString(
                "Emisión general: " + emisionGeneral.format(fmtEmision),
                xTitulo,
                yTitulo + 93
        );
        g.drawString(
                "Validez general: " + inicioValidez.format(fmtValidez)
                        + " a " + finValidez.format(fmtValidez)
                        + " (24 h)",
                xTitulo,
                yTitulo + 127
        );

        int yAviso = PNG_MARGEN + altoCabecera;

        // -------------------------
        // AVISO DESTACADO
        // -------------------------
        g.setColor(celeste);
        g.fillRoundRect(PNG_MARGEN, yAviso, anchoUtil, altoAviso, 24, 24);
        g.setColor(azul);
        g.drawRoundRect(PNG_MARGEN, yAviso, anchoUtil, altoAviso, 24, 24);

        g.setFont(fuenteAviso);
        g.setColor(new Color(25, 55, 70));

        int yTextoAviso = yAviso + 38;
        for (String linea : lineasAviso) {
            g.drawString(linea, PNG_MARGEN + 30, yTextoAviso);
            yTextoAviso += fmAviso.getHeight() + 3;
        }

        // -------------------------
        // TARJETAS DE PRONOSTICOS
        // -------------------------
        int yContenido = yAviso + altoAviso + 28;

        for (int fila = 0; fila * PNG_COLUMNAS < tarjetas.size(); fila++) {

            int base = fila * PNG_COLUMNAS;
            int altoFila = 0;

            for (int c = 0; c < PNG_COLUMNAS; c++) {
                int idx = base + c;
                if (idx < tarjetas.size()) {
                    altoFila = Math.max(altoFila, tarjetas.get(idx).alto);
                }
            }

            for (int c = 0; c < PNG_COLUMNAS; c++) {
                int idx = base + c;
                if (idx >= tarjetas.size()) {
                    continue;
                }

                TarjetaPronostico tarjeta = tarjetas.get(idx);

                int x = PNG_MARGEN + c * (anchoColumna + PNG_SEPARACION_COLUMNAS);
                int y = yContenido;

                g.setColor(fondoTarjeta);
                g.fillRoundRect(x, y, anchoColumna, altoFila, 20, 20);
                g.setColor(borde);
                g.drawRoundRect(x, y, anchoColumna, altoFila, 20, 20);

                g.setFont(fuenteLugar);
                g.setColor(azul);
                g.drawString(
                        tarjeta.nombre.replace('_', ' '),
                        x + 22,
                        y + 34
                );

                g.setColor(new Color(205, 214, 220));
                g.drawLine(x + 22, y + 49, x + anchoColumna - 22, y + 49);

                g.setFont(fuenteTemperatura);
                g.setColor(new Color(65, 65, 65));
                g.drawString(
                        tarjeta.resumenTemperaturas,
                        x + 22,
                        y + 78
                );

                g.setFont(fuenteTAF);
                g.setColor(Color.BLACK);

                int yTaf = y + 112;
                for (String linea : tarjeta.lineas) {
                    g.drawString(linea, x + 22, yTaf);
                    yTaf += fmTaf.getHeight() + 3;
                }
            }

            yContenido += altoFila + PNG_SEPARACION_FILAS;
        }

        // -------------------------
        // PIE
        // -------------------------
        int yPie = altoTotal - PNG_MARGEN - 25;
        g.setColor(new Color(150, 150, 150));
        g.drawLine(PNG_MARGEN, yPie - 30, PNG_ANCHO - PNG_MARGEN, yPie - 30);

        g.setFont(fuentePie);
        g.setColor(textoSecundario);
        g.drawString(
                "Producto automático generado a partir de la salida GFS 0.25°.",
                PNG_MARGEN,
                yPie
        );

        g.dispose();

        Files.createDirectories(salidaPng.getParent());
        ImageIO.write(imagen, "png", salidaPng.toFile());
    }

    private static String formatearTemperaturas(PronosticoLocalidad p) {

        String max = Double.isFinite(p.tmax)
                ? String.format(Locale.US, "%.0f °C", p.tmax)
                : "--";

        String min = Double.isFinite(p.tmin)
                ? String.format(Locale.US, "%.0f °C", p.tmin)
                : "--";

        String horaMax = p.horaTmax == null
                ? ""
                : String.format(" (%02dZ)", p.horaTmax.getHour());

        String horaMin = p.horaTmin == null
                ? ""
                : String.format(" (%02dZ)", p.horaTmin.getHour());

        return "Tmax " + max + horaMax
                + "   |   Tmin " + min + horaMin;
    }

    private static void configurarRenderizado(Graphics2D g) {
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_RENDERING, RenderingHints.VALUE_RENDER_QUALITY);
        g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BICUBIC);
    }

    private static BufferedImage cargarYRecortarLogo(Path rutaEscudo) {
        try {
            if (rutaEscudo == null || !Files.exists(rutaEscudo)) {
                System.out.println("ADVERTENCIA: no se encontró el escudo: "
                        + (rutaEscudo == null ? "null" : rutaEscudo.toAbsolutePath()));
                return null;
            }

            BufferedImage original = ImageIO.read(rutaEscudo.toFile());
            if (original == null) {
                return null;
            }

            return recortarTransparencia(original);

        } catch (Exception e) {
            System.out.println("ADVERTENCIA: no se pudo cargar el escudo: " + e.getMessage());
            return null;
        }
    }

    private static BufferedImage recortarTransparencia(BufferedImage imagen) {

        if (!imagen.getColorModel().hasAlpha()) {
            return imagen;
        }

        int minX = imagen.getWidth();
        int minY = imagen.getHeight();
        int maxX = -1;
        int maxY = -1;

        for (int y = 0; y < imagen.getHeight(); y++) {
            for (int x = 0; x < imagen.getWidth(); x++) {
                int alpha = (imagen.getRGB(x, y) >>> 24) & 0xFF;
                if (alpha > 10) {
                    minX = Math.min(minX, x);
                    minY = Math.min(minY, y);
                    maxX = Math.max(maxX, x);
                    maxY = Math.max(maxY, y);
                }
            }
        }

        if (maxX < minX || maxY < minY) {
            return imagen;
        }

        return imagen.getSubimage(
                minX,
                minY,
                maxX - minX + 1,
                maxY - minY + 1
        );
    }

    private static void dibujarImagenAjustada(
            Graphics2D g,
            BufferedImage imagen,
            int x,
            int y,
            int maxW,
            int maxH) {

        double escala = Math.min(
                maxW / (double) imagen.getWidth(),
                maxH / (double) imagen.getHeight()
        );

        int w = (int) Math.round(imagen.getWidth() * escala);
        int h = (int) Math.round(imagen.getHeight() * escala);

        int xx = x + (maxW - w) / 2;
        int yy = y + (maxH - h) / 2;

        g.drawImage(imagen, xx, yy, w, h, null);
    }

    private static List<String> envolverTAF(String taf, FontMetrics fm, int anchoMax) {

        List<String> salida = new ArrayList<>();

        for (String linea : taf.replace("\r", "").split("\n")) {
            String limpia = linea.trim();
            if (limpia.isEmpty()) {
                continue;
            }
            salida.addAll(envolverTexto(limpia, fm, anchoMax));
        }

        return salida;
    }

    private static List<String> envolverTexto(String texto, FontMetrics fm, int anchoMax) {

        List<String> lineas = new ArrayList<>();
        String[] palabras = texto.trim().split("\\s+");
        StringBuilder actual = new StringBuilder();

        for (String palabra : palabras) {

            String candidato = actual.length() == 0
                    ? palabra
                    : actual + " " + palabra;

            if (fm.stringWidth(candidato) <= anchoMax) {
                actual.setLength(0);
                actual.append(candidato);
            } else {
                if (actual.length() > 0) {
                    lineas.add(actual.toString());
                }
                actual.setLength(0);
                actual.append(palabra);
            }
        }

        if (actual.length() > 0) {
            lineas.add(actual.toString());
        }

        return lineas;
    }

    private static int calcularAltoContenido(List<TarjetaPronostico> tarjetas) {

        int total = 0;

        for (int fila = 0; fila * PNG_COLUMNAS < tarjetas.size(); fila++) {

            int base = fila * PNG_COLUMNAS;
            int altoFila = 0;

            for (int c = 0; c < PNG_COLUMNAS; c++) {
                int idx = base + c;
                if (idx < tarjetas.size()) {
                    altoFila = Math.max(altoFila, tarjetas.get(idx).alto);
                }
            }

            total += altoFila;

            if ((fila + 1) * PNG_COLUMNAS < tarjetas.size()) {
                total += PNG_SEPARACION_FILAS;
            }
        }

        return total;
    }

    // ============================================================
    // LECTURA DEL CSV
    // ============================================================

    private static List<RegistroHorario> leerCSV(Path archivo) throws IOException {

        List<RegistroHorario> registros = new ArrayList<>();

        try (BufferedReader br = Files.newBufferedReader(archivo, StandardCharsets.UTF_8)) {

            String encabezado = br.readLine();

            if (encabezado == null) {
                return registros;
            }

            encabezado = quitarBOM(encabezado);

            char separador = detectarSeparador(encabezado);

            List<String> headers = separarCSV(encabezado, separador);

            Map<String, Integer> columnas = new HashMap<>();

            for (int i = 0; i < headers.size(); i++) {
                columnas.put(normalizarNombreColumna(headers.get(i)), i);
            }

            validarColumnasMinimas(columnas);

            String linea;
            int numeroLinea = 1;

            while ((linea = br.readLine()) != null) {

                numeroLinea++;

                if (linea.isBlank()) {
                    continue;
                }

                try {
                    List<String> valores = separarCSV(linea, separador);

                    RegistroHorario r = new RegistroHorario();

                    r.nombre = texto(columnas, valores, "nombre");

                    r.fechaHora = parseFechaHora(texto(columnas, valores, "fecha_hora"));

                    r.direccionViento = numero(columnas, valores, "wind_dir");
                    r.vientoKt = numero(columnas, valores, "wind_kt");
                    r.rafagaKt = numeroOpcional(columnas, valores, "gust_kt");

                    r.visibilidadMetros = numero(columnas, valores, "vis_m");

                    r.temperaturaC = numeroOpcional(columnas, valores, "temp_c");
                    r.puntoRocioC = numeroOpcional(columnas, valores, "td_c");
                    r.humedadRelativa = numeroOpcional(columnas, valores, "rh");

                    r.precipitacionMm = numeroOpcional(columnas, valores, "precip_mm");
                    r.precipitacionConvectivaMm =
                            numeroOpcional(columnas, valores, "conv_precip_mm");

                    r.cape = numeroOpcional(columnas, valores, "cape");
                    r.cin = numeroOpcional(columnas, valores, "cin");
                    r.reflectividadDbz =
                            numeroOpcional(columnas, valores, "reflectivity_dbz");

                    r.nubosidadBajaPct =
                            numeroOpcional(columnas, valores, "low_cloud_pct");

                    r.techoFtAgl =
                            numeroOpcional(columnas, valores, "ceiling_ft_agl");

                    registros.add(r);

                } catch (Exception e) {
                    System.err.println(
                            "ADVERTENCIA: se omite linea "
                                    + numeroLinea + ": " + e.getMessage()
                    );
                }
            }
        }

        return registros;
    }

    private static Map<String, List<RegistroHorario>> agruparPorLocalidad(
            List<RegistroHorario> registros) {

        Map<String, List<RegistroHorario>> mapa = new LinkedHashMap<>();

        registros.sort(
                Comparator.comparing((RegistroHorario r) -> r.nombre)
                        .thenComparing(r -> r.fechaHora)
        );

        for (RegistroHorario r : registros) {
            mapa.computeIfAbsent(r.nombre, k -> new ArrayList<>()).add(r);
        }

        return mapa;
    }

    private static void validarColumnasMinimas(Map<String, Integer> columnas) {

        String[] requeridas = {
                "nombre",
                "fecha_hora",
                "wind_dir",
                "wind_kt",
                "vis_m"
        };

        for (String columna : requeridas) {
            if (!columnas.containsKey(columna)) {
                throw new IllegalArgumentException(
                        "Falta la columna obligatoria: " + columna
                );
            }
        }
    }

    // ============================================================
    // UTILIDADES CSV
    // ============================================================

    private static char detectarSeparador(String linea) {

        int comas = contarCaracter(linea, ',');
        int puntoComa = contarCaracter(linea, ';');

        return puntoComa > comas ? ';' : ',';
    }

    private static int contarCaracter(String s, char c) {

        int contador = 0;

        for (char x : s.toCharArray()) {
            if (x == c) {
                contador++;
            }
        }

        return contador;
    }

    private static List<String> separarCSV(String linea, char separador) {

        List<String> resultado = new ArrayList<>();

        StringBuilder actual = new StringBuilder();
        boolean entreComillas = false;

        for (int i = 0; i < linea.length(); i++) {

            char c = linea.charAt(i);

            if (c == '"') {

                if (entreComillas
                        && i + 1 < linea.length()
                        && linea.charAt(i + 1) == '"') {

                    actual.append('"');
                    i++;

                } else {
                    entreComillas = !entreComillas;
                }

            } else if (c == separador && !entreComillas) {

                resultado.add(actual.toString().trim());
                actual.setLength(0);

            } else {
                actual.append(c);
            }
        }

        resultado.add(actual.toString().trim());

        return resultado;
    }

    private static String normalizarNombreColumna(String s) {

        return quitarBOM(s)
                .trim()
                .toLowerCase(Locale.ROOT)
                .replace(" ", "_");
    }

    private static String quitarBOM(String s) {

        if (s != null && !s.isEmpty() && s.charAt(0) == '\uFEFF') {
            return s.substring(1);
        }

        return s;
    }

    private static String texto(
            Map<String, Integer> columnas,
            List<String> valores,
            String nombre) {

        Integer i = columnas.get(nombre);

        if (i == null || i >= valores.size()) {
            throw new IllegalArgumentException("Falta valor para " + nombre);
        }

        String valor = valores.get(i).trim();

        if (valor.isBlank()) {
            throw new IllegalArgumentException("Valor vacio para " + nombre);
        }

        return valor;
    }

    private static String textoOpcional(
            Map<String, Integer> columnas,
            List<String> valores,
            String nombre) {

        Integer i = columnas.get(nombre);

        if (i == null || i >= valores.size()) {
            return "";
        }

        return valores.get(i).trim();
    }

    private static double numero(
            Map<String, Integer> columnas,
            List<String> valores,
            String nombre) {

        String s = texto(columnas, valores, nombre);
        return parseDoubleFlexible(s);
    }

    private static double numeroOpcional(
            Map<String, Integer> columnas,
            List<String> valores,
            String nombre) {

        Integer i = columnas.get(nombre);

        if (i == null || i >= valores.size()) {
            return Double.NaN;
        }

        String s = valores.get(i).trim();

        if (s.isBlank()
                || s.equalsIgnoreCase("nan")
                || s.equalsIgnoreCase("null")
                || s.equalsIgnoreCase("none")) {

            return Double.NaN;
        }

        return parseDoubleFlexible(s);
    }

    private static double parseDoubleFlexible(String s) {

        String limpio = s.trim().replace(',', '.');
        return Double.parseDouble(limpio);
    }

    private static LocalDateTime parseFechaHora(String texto) {

        String s = texto.trim();

        DateTimeFormatter[] formatos = {
                DateTimeFormatter.ISO_LOCAL_DATE_TIME,
                DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm"),
                DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"),
                DateTimeFormatter.ofPattern("yyyyMMddHH"),
                DateTimeFormatter.ofPattern("yyyyMMddHHmm")
        };

        for (DateTimeFormatter formato : formatos) {
            try {
                return LocalDateTime.parse(s, formato);
            } catch (DateTimeParseException ignored) {
            }
        }

        throw new IllegalArgumentException(
                "Formato de fecha_hora no reconocido: " + texto
        );
    }

    // ============================================================
    // UTILIDADES METEOROLOGICAS
    // ============================================================

    private static int redondearDireccion10(double grados) {

        double normalizada = grados % 360.0;

        if (normalizada < 0) {
            normalizada += 360.0;
        }

        int redondeada = (int) Math.round(normalizada / 10.0) * 10;

        if (redondeada == 0) {
            redondeada = 360;
        }

        if (redondeada > 360) {
            redondeada = 360;
        }

        return redondeada;
    }

    private static double diferenciaAngular(double a, double b) {

        if (Double.isNaN(a) || Double.isNaN(b)) {
            return 0;
        }

        double diferencia = Math.abs(a - b) % 360.0;

        return diferencia > 180.0
                ? 360.0 - diferencia
                : diferencia;
    }

    private static double calcularRH(double temperatura, double puntoRocio) {

        double a = 17.625;
        double b = 243.04;

        double esTd =
                Math.exp((a * puntoRocio) / (b + puntoRocio));

        double esT =
                Math.exp((a * temperatura) / (b + temperatura));

        return 100.0 * (esTd / esT);
    }

    private static int severidadFenomeno(String fenomeno) {

        return switch (fenomeno) {
            case "" -> 0;
            case "BR", "-RA" -> 1;
            case "RA", "SHRA" -> 2;
            case "FG", "+RA" -> 3;
            case "TSRA" -> 5;
            default -> 1;
        };
    }

    private static double valorSeguro(double valor) {

        return Double.isNaN(valor) ? 0.0 : valor;
    }

    // ============================================================
    // CLASES INTERNAS
    // ============================================================

    private enum TipoGrupo {
        FM,
        BECMG,
        TEMPO
    }

    private static class PronosticoLocalidad {
        String nombre;
        String texto;
        double tmax;
        double tmin;
        LocalDateTime horaTmax;
        LocalDateTime horaTmin;

        PronosticoLocalidad(
                String nombre,
                String texto,
                double tmax,
                double tmin,
                LocalDateTime horaTmax,
                LocalDateTime horaTmin) {

            this.nombre = nombre;
            this.texto = texto;
            this.tmax = tmax;
            this.tmin = tmin;
            this.horaTmax = horaTmax;
            this.horaTmin = horaTmin;
        }
    }

    private static class TarjetaPronostico {
        String nombre;
        String resumenTemperaturas;
        List<String> lineas;
        int alto;

        TarjetaPronostico(
                String nombre,
                String resumenTemperaturas,
                List<String> lineas,
                int alto) {

            this.nombre = nombre;
            this.resumenTemperaturas = resumenTemperaturas;
            this.lineas = lineas;
            this.alto = alto;
        }
    }

    private static class GrupoCambio {

        TipoGrupo tipo;
        LocalDateTime desde;
        LocalDateTime hasta;
        RegistroHorario estado;

        GrupoCambio(
                TipoGrupo tipo,
                LocalDateTime desde,
                LocalDateTime hasta,
                RegistroHorario estado) {

            this.tipo = tipo;
            this.desde = desde;
            this.hasta = hasta;
            this.estado = estado;
        }
    }

    private static class RegistroHorario {

        String nombre;

        LocalDateTime fechaHora;

        double direccionViento;
        double vientoKt;
        double rafagaKt;

        double visibilidadMetros;

        double temperaturaC;
        double puntoRocioC;
        double humedadRelativa;

        double precipitacionMm;
        double precipitacionConvectivaMm;

        double cape;
        double cin;
        double reflectividadDbz;

        double nubosidadBajaPct;
        double techoFtAgl;
    }
}
