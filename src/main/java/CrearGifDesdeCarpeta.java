import javax.imageio.*;
import javax.imageio.metadata.*;
import javax.imageio.stream.ImageOutputStream;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class CrearGifDesdeCarpeta {

    private static final long LIMITE_BYTES = 5L * 1024L * 1024L; // 5 MB

    // Escalas que se prueban solo si el GIF supera los 5 MB.
    private static final double[] ESCALAS = {
            1.00, 0.98, 0.96, 0.94, 0.92, 0.90, 0.88, 0.85, 0.82, 0.80, 0.75, 0.70
    };

    public static void main(String[] args) throws Exception {

        if (args.length < 1) {
            System.out.println("Uso: java -jar generador-gif.jar carpetaImagenes [carpetaSalida] [delayMs]");
            return;
        }

        File carpeta = new File(args[0]);

        File carpetaSalida = args.length >= 2
                ? new File(args[1])
                : new File("loops");

        int delayMs = args.length >= 3
                ? Integer.parseInt(args[2])
                : 1000;

        carpetaSalida.mkdirs();

        File[] archivos = carpeta.listFiles();

        if (archivos == null) {
            System.out.println("No se pudo leer la carpeta: " + carpeta.getAbsolutePath());
            return;
        }

        List<File> imagenes = Arrays.stream(archivos)
                .filter(File::isFile)
                .filter(f -> {
                    String n = f.getName().toLowerCase();
                    return n.endsWith(".png") || n.endsWith(".jpg") || n.endsWith(".jpeg");
                })
                .sorted()
                .toList();

        if (imagenes.isEmpty()) {
            System.out.println("No se encontraron imágenes.");
            return;
        }

        System.out.println("Imágenes encontradas: " + imagenes.size());

        String fechaHora = java.time.LocalDateTime.now()
                .format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));

        File salidaFinal = new File(
                carpetaSalida,
                "animacion_satelite_" + fechaHora + ".gif"
        );

        File mejorArchivo = null;
        ResultadoGeneracion mejorResultado = null;

        for (double escala : ESCALAS) {

            File salidaTemporal = new File(
                    carpetaSalida,
                    "temp_animacion_" + fechaHora + "_" + (int) (escala * 100) + ".gif"
            );

            ResultadoGeneracion resultado = generarGif(imagenes, salidaTemporal, delayMs, escala);

            if (resultado.framesValidos == 0) {
                salidaTemporal.delete();
                continue;
            }

            long peso = salidaTemporal.length();

            System.out.println("-----------------------------------");
            System.out.println("Prueba escala: " + (int) (escala * 100) + "%");
            System.out.println("Tamaño: " + formatoMB(peso));
            System.out.println("Frames agregados: " + resultado.framesValidos);
            System.out.println("Frames repetidos omitidos: " + resultado.framesRepetidos);
            System.out.println("Imágenes inválidas omitidas: " + resultado.framesInvalidos);
            System.out.println("-----------------------------------");

            if (mejorArchivo == null || peso < mejorArchivo.length()) {
                if (mejorArchivo != null && mejorArchivo.exists()) {
                    mejorArchivo.delete();
                }
                mejorArchivo = salidaTemporal;
                mejorResultado = resultado;
            } else {
                salidaTemporal.delete();
            }

            if (peso <= LIMITE_BYTES) {
                break;
            }
        }

        if (mejorArchivo == null || !mejorArchivo.exists()) {
            System.out.println("❌ No se pudo generar el GIF.");
            return;
        }

        if (salidaFinal.exists()) {
            salidaFinal.delete();
        }

        boolean renombrado = mejorArchivo.renameTo(salidaFinal);

        if (!renombrado) {
            System.out.println("❌ No se pudo renombrar el archivo final.");
            System.out.println("Archivo temporal generado: " + mejorArchivo.getAbsolutePath());
            return;
        }

        System.out.println("===================================");
        System.out.println("GIF generado correctamente:");
        System.out.println(salidaFinal.getAbsolutePath());
        System.out.println("Tamaño final: " + formatoMB(salidaFinal.length()));

        if (mejorResultado != null) {
            System.out.println("Frames finales: " + mejorResultado.framesValidos);
            System.out.println("Frames repetidos omitidos: " + mejorResultado.framesRepetidos);
            System.out.println("Imágenes inválidas omitidas: " + mejorResultado.framesInvalidos);
        }

        if (salidaFinal.length() <= LIMITE_BYTES) {
            System.out.println("Estado: OK, menor o igual a 5 MB");
        } else {
            System.out.println("Estado: supera 5 MB, pero se usó la máxima reducción configurada");
        }

        System.out.println("===================================");
    }

    private static ResultadoGeneracion generarGif(
            List<File> imagenes,
            File salida,
            int delayMs,
            double escala
    ) throws Exception {

        ImageWriter writer = ImageIO.getImageWritersBySuffix("gif").next();

        int framesValidos = 0;
        int framesRepetidos = 0;
        int framesInvalidos = 0;

        BufferedImage ultimaImagenAgregada = null;

        try (ImageOutputStream output = ImageIO.createImageOutputStream(salida)) {

            writer.setOutput(output);
            writer.prepareWriteSequence(null);

            for (File archivo : imagenes) {

                BufferedImage imagen;

                try {
                    imagen = ImageIO.read(archivo);

                    if (imagen == null) {
                        System.out.println("⚠ Imagen inválida, se omite: " + archivo.getName());
                        framesInvalidos++;
                        continue;
                    }

                } catch (Exception e) {
                    System.out.println("⚠ Error leyendo imagen, se omite: " + archivo.getName());
                    System.out.println("  " + e.getMessage());
                    framesInvalidos++;
                    continue;
                }

                BufferedImage optimizada = optimizarImagen(imagen, escala);

                if (ultimaImagenAgregada != null && sonImagenesIguales(ultimaImagenAgregada, optimizada)) {
                    System.out.println("↪ Frame repetido, se omite: " + archivo.getName());
                    framesRepetidos++;
                    continue;
                }

                ImageWriteParam params = writer.getDefaultWriteParam();

                IIOMetadata metadata = writer.getDefaultImageMetadata(
                        new ImageTypeSpecifier(optimizada),
                        params
                );

                configurarMetadata(metadata, delayMs);

                IIOImage frame = new IIOImage(optimizada, null, metadata);
                writer.writeToSequence(frame, params);

                ultimaImagenAgregada = optimizada;
                framesValidos++;

                System.out.println("✔ Frame agregado: " + archivo.getName());
            }

            writer.endWriteSequence();
        } finally {
            writer.dispose();
        }

        return new ResultadoGeneracion(framesValidos, framesRepetidos, framesInvalidos);
    }

    private static BufferedImage optimizarImagen(BufferedImage original, double escala) {

        int ancho = Math.max(1, (int) Math.round(original.getWidth() * escala));
        int alto = Math.max(1, (int) Math.round(original.getHeight() * escala));

        BufferedImage escalada = new BufferedImage(
                ancho,
                alto,
                BufferedImage.TYPE_INT_RGB
        );

        Graphics2D g = escalada.createGraphics();
        g.setRenderingHint(
                RenderingHints.KEY_INTERPOLATION,
                RenderingHints.VALUE_INTERPOLATION_BILINEAR
        );
        g.setRenderingHint(
                RenderingHints.KEY_RENDERING,
                RenderingHints.VALUE_RENDER_QUALITY
        );
        g.drawImage(original, 0, 0, ancho, alto, null);
        g.dispose();

        // TYPE_BYTE_INDEXED fuerza una paleta apta para GIF y reduce el peso.
        BufferedImage indexada = new BufferedImage(
                ancho,
                alto,
                BufferedImage.TYPE_BYTE_INDEXED
        );

        Graphics2D g2 = indexada.createGraphics();
        g2.drawImage(escalada, 0, 0, null);
        g2.dispose();

        return indexada;
    }

    private static boolean sonImagenesIguales(BufferedImage img1, BufferedImage img2) {

        if (img1.getWidth() != img2.getWidth() || img1.getHeight() != img2.getHeight()) {
            return false;
        }

        // Comparación por muestreo: suficiente para detectar frames satelitales repetidos.
        // Paso 4 = compara 1 de cada 4 píxeles en cada eje.
        int paso = 4;

        for (int y = 0; y < img1.getHeight(); y += paso) {
            for (int x = 0; x < img1.getWidth(); x += paso) {
                if (img1.getRGB(x, y) != img2.getRGB(x, y)) {
                    return false;
                }
            }
        }

        return true;
    }

    private static void configurarMetadata(IIOMetadata metadata, int delayMs) throws Exception {

        String format = metadata.getNativeMetadataFormatName();

        IIOMetadataNode root = (IIOMetadataNode) metadata.getAsTree(format);

        IIOMetadataNode graphicControlExtension =
                getNode(root, "GraphicControlExtension");

        graphicControlExtension.setAttribute("disposalMethod", "none");
        graphicControlExtension.setAttribute("userInputFlag", "FALSE");
        graphicControlExtension.setAttribute("transparentColorFlag", "FALSE");
        graphicControlExtension.setAttribute("delayTime", String.valueOf(delayMs / 10));
        graphicControlExtension.setAttribute("transparentColorIndex", "0");

        IIOMetadataNode appExtensions =
                getNode(root, "ApplicationExtensions");

        IIOMetadataNode appExtension =
                new IIOMetadataNode("ApplicationExtension");

        appExtension.setAttribute("applicationID", "NETSCAPE");
        appExtension.setAttribute("authenticationCode", "2.0");

        byte[] loop = new byte[]{0x1, 0x0, 0x0};
        appExtension.setUserObject(loop);

        appExtensions.appendChild(appExtension);

        metadata.setFromTree(format, root);
    }

    private static IIOMetadataNode getNode(IIOMetadataNode rootNode, String nodeName) {

        for (int i = 0; i < rootNode.getLength(); i++) {
            if (rootNode.item(i).getNodeName().equalsIgnoreCase(nodeName)) {
                return (IIOMetadataNode) rootNode.item(i);
            }
        }

        IIOMetadataNode node = new IIOMetadataNode(nodeName);
        rootNode.appendChild(node);
        return node;
    }

    private static String formatoMB(long bytes) {
        double mb = bytes / 1024.0 / 1024.0;
        return String.format("%.2f MB", mb);
    }

    private static class ResultadoGeneracion {
        int framesValidos;
        int framesRepetidos;
        int framesInvalidos;

        ResultadoGeneracion(int framesValidos, int framesRepetidos, int framesInvalidos) {
            this.framesValidos = framesValidos;
            this.framesRepetidos = framesRepetidos;
            this.framesInvalidos = framesInvalidos;
        }
    }
}
