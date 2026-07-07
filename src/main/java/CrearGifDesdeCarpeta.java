import javax.imageio.*;
import javax.imageio.metadata.*;
import javax.imageio.stream.ImageOutputStream;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;
import java.util.Arrays;
import java.util.List;

public class CrearGifDesdeCarpeta {

    private static final long LIMITE_BYTES = 5L * 1024L * 1024L; // 5 MB

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

        double[] escalas = {
                1.00, 0.98, 0.96, 0.94, 0.92, 0.90, 0.88, 0.85, 0.82, 0.80
        };

        File mejorArchivo = null;

        for (double escala : escalas) {

            File salidaTemporal = new File(
                    carpetaSalida,
                    "temp_animacion_" + fechaHora + "_" + (int) (escala * 100) + ".gif"
            );

            int[] resultado = generarGif(imagenes, salidaTemporal, delayMs, escala);

            int validas = resultado[0];
            int omitidas = resultado[1];

            if (validas == 0) {
                salidaTemporal.delete();
                continue;
            }

            long peso = salidaTemporal.length();

            System.out.println("-----------------------------------");
            System.out.println("Prueba escala: " + (int) (escala * 100) + "%");
            System.out.println("Tamaño: " + formatoMB(peso));
            System.out.println("-----------------------------------");

            if (mejorArchivo == null || peso < mejorArchivo.length()) {
                if (mejorArchivo != null && mejorArchivo.exists()) {
                    mejorArchivo.delete();
                }
                mejorArchivo = salidaTemporal;
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

        mejorArchivo.renameTo(salidaFinal);

        System.out.println("===================================");
        System.out.println("GIF generado correctamente:");
        System.out.println(salidaFinal.getAbsolutePath());
        System.out.println("Tamaño final: " + formatoMB(salidaFinal.length()));

        if (salidaFinal.length() <= LIMITE_BYTES) {
            System.out.println("Estado: OK, menor a 5 MB");
        } else {
            System.out.println("Estado: supera 5 MB, pero se usó la máxima reducción configurada");
        }

        System.out.println("===================================");
    }

    private static int[] generarGif(
            List<File> imagenes,
            File salida,
            int delayMs,
            double escala
    ) throws Exception {

        ImageWriter writer = ImageIO.getImageWritersBySuffix("gif").next();

        int imagenesValidas = 0;
        int imagenesOmitidas = 0;

        try (ImageOutputStream output = ImageIO.createImageOutputStream(salida)) {

            writer.setOutput(output);
            writer.prepareWriteSequence(null);

            for (File archivo : imagenes) {

                BufferedImage imagen;

                try {
                    imagen = ImageIO.read(archivo);

                    if (imagen == null) {
                        System.out.println("⚠ Imagen inválida, se omite: " + archivo.getName());
                        imagenesOmitidas++;
                        continue;
                    }

                } catch (Exception e) {
                    System.out.println("⚠ Error leyendo imagen, se omite: " + archivo.getName());
                    System.out.println("  " + e.getMessage());
                    imagenesOmitidas++;
                    continue;
                }

                BufferedImage optimizada = optimizarImagen(imagen, escala);

                ImageWriteParam params = writer.getDefaultWriteParam();

                IIOMetadata metadata = writer.getDefaultImageMetadata(
                        new ImageTypeSpecifier(optimizada),
                        params
                );

                configurarMetadata(metadata, delayMs);

                IIOImage frame = new IIOImage(optimizada, null, metadata);
                writer.writeToSequence(frame, params);

                imagenesValidas++;
                System.out.println("✔ Frame agregado: " + archivo.getName());
            }

            writer.endWriteSequence();
        }

        writer.dispose();

        return new int[]{imagenesValidas, imagenesOmitidas};
    }

    private static BufferedImage optimizarImagen(BufferedImage original, double escala) {

        int ancho = Math.max(1, (int) (original.getWidth() * escala));
        int alto = Math.max(1, (int) (original.getHeight() * escala));

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
        g.drawImage(original, 0, 0, ancho, alto, null);
        g.dispose();

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
}
