package taf;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
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
 * Generador de TAF corto orientativo a partir de datos horarios de GFS.
 *
 * Compatible con Java 17 y sin dependencias externas.
 *
 * USO:
 *   javac GenerarTAF.java
 *   java GenerarTAF datos_taf.csv
 *
 * o:
 *   java GenerarTAF datos_taf.csv C:\modelos\salidas\20260909\taf12
 *
 * El CSV puede estar separado por coma o punto y coma.
 *
 * Columnas esperadas:
 *
 * nombre,fecha_hora,wind_dir,wind_kt,gust_kt,vis_m,temp_c,td_c,rh,
 * precip_mm,conv_precip_mm,cape,cin,reflectivity_dbz,low_cloud_pct,
 * ceiling_ft_agl
 *
 * Ejemplo de fecha_hora:
 *   2026-09-09T12:00
 *   2026-09-09 12:00
 *
 * IMPORTANTE:
 * Este programa genera un TAF AUTOMATICO/ORIENTATIVO. No reemplaza
 * la revisión y responsabilidad de un pronosticador aeronáutico.
 */
public class GenerarTAF {

    // ============================================================
    // CONFIGURACION GENERAL
    // ============================================================

    private static final int HORAS_VALIDEZ = 12;

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

        Locale.setDefault(Locale.US);

        if (args.length < 1) {
            mostrarAyuda();
            return;
        }

        Path archivoEntrada = Paths.get(args[0]);

        Path carpetaSalida;
        if (args.length >= 2) {
            carpetaSalida = Paths.get(args[1]);
        } else {
            carpetaSalida = Paths.get("taf_salida");
        }

        try {
            if (!Files.exists(archivoEntrada)) {
                System.err.println("ERROR: No existe el archivo: " + archivoEntrada.toAbsolutePath());
                return;
            }

            Files.createDirectories(carpetaSalida);

            List<RegistroHorario> registros = leerCSV(archivoEntrada);

            if (registros.isEmpty()) {
                System.err.println("ERROR: El CSV no contiene registros utilizables.");
                return;
            }

            Map<String, List<RegistroHorario>> porLocalidad = agruparPorLocalidad(registros);

            System.out.println("====================================================");
            System.out.println(" GENERADOR AUTOMATICO DE TAF CORTO");
            System.out.println("====================================================");
            System.out.println("Archivo: " + archivoEntrada.toAbsolutePath());
            System.out.println("Localidades encontradas: " + porLocalidad.size());
            System.out.println();

            for (Map.Entry<String, List<RegistroHorario>> entry : porLocalidad.entrySet()) {

                String nombre = entry.getKey();
                List<RegistroHorario> datos = entry.getValue();

                try {
                    String taf = generarTAF(nombre, datos);

                    Path archivoSalida = carpetaSalida.resolve("TAF_" + nombreSeguroArchivo(nombre) + ".txt");

                    Files.writeString(
                            archivoSalida,
                            taf,
                            StandardCharsets.UTF_8
                    );

                    System.out.println("OK  " + nombre + " -> " + archivoSalida.toAbsolutePath());

                } catch (Exception e) {
                    System.err.println("ERROR generando TAF para " + nombre + ": " + e.getMessage());
                }
            }

            System.out.println();
            System.out.println("Proceso finalizado.");

        } catch (Exception e) {
            System.err.println("ERROR GENERAL: " + e.getMessage());
            e.printStackTrace();
        }
    }

    /**
     * Permite ejecutar el generador desde DescargaGFSMenu sin abrir otro proceso Java.
     */
    public static void generar(String archivoCsv, String carpetaSalida) {
        main(new String[]{archivoCsv, carpetaSalida});
    }

    private static void mostrarAyuda() {
        System.out.println("""
                Uso:
                  java GenerarTAF datos_taf.csv
                  java GenerarTAF datos_taf.csv carpeta_salida

                Ejemplo:
                  java GenerarTAF C:\\modelos\\datos_taf_12.csv C:\\modelos\\salidas\\20260909\\taf12
                """);
    }

    // ============================================================
    // GENERACION DEL TAF
    // ============================================================

    private static String generarTAF(String nombre, List<RegistroHorario> datos) {

        datos.sort(Comparator.comparing(r -> r.fechaHora));

        LocalDateTime inicio = datos.get(0).fechaHora;
        LocalDateTime fin = inicio.plusHours(HORAS_VALIDEZ);

        List<RegistroHorario> periodo = new ArrayList<>();

        for (RegistroHorario r : datos) {
            if (!r.fechaHora.isBefore(inicio) && r.fechaHora.isBefore(fin)) {
                periodo.add(r);
            }
        }

        if (periodo.size() < 2) {
            throw new IllegalArgumentException(
                    "Se necesitan al menos 2 horas de datos dentro del periodo de validez."
            );
        }

        LocalDateTime emision = inicio.minusHours(1);

        String encabezado =
                nombre.replace('_', ' ') + "\n"
                        + "Emision: " + formatearEmisionTexto(emision) + "\n"
                        + "Validez: " + formatearValidezTexto(inicio, fin);

        RegistroHorario inicial = periodo.get(0);

        List<GrupoCambio> grupos = detectarCambios(periodo);

        StringBuilder sb = new StringBuilder();

        sb.append(encabezado).append("\n\n");
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

        sb.append("\n");

        return sb.toString();
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
