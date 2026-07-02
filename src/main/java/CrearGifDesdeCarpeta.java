import javax.imageio.*;
import javax.imageio.metadata.*;
import javax.imageio.stream.ImageOutputStream;
import java.awt.image.BufferedImage;
import java.io.File;
import java.util.Arrays;
import java.util.List;

public class CrearGifDesdeCarpeta {

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

        String fechaHora = java.time.LocalDateTime.now()
                .format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));

        File salida = new File(
                carpetaSalida,
                "animacion_satelite_" + fechaHora + ".gif"
        );

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

                ImageWriteParam params = writer.getDefaultWriteParam();
                IIOMetadata metadata = writer.getDefaultImageMetadata(
                        new ImageTypeSpecifier(imagen), params
                );

                configurarMetadata(metadata, delayMs);

                IIOImage frame = new IIOImage(imagen, null, metadata);
                writer.writeToSequence(frame, params);

                imagenesValidas++;
                System.out.println("✔ Frame agregado: " + archivo.getName());
            }

            writer.endWriteSequence();
        }

        if (imagenesValidas == 0) {
            System.out.println("❌ No hubo imágenes válidas. Se elimina GIF vacío.");
            salida.delete();
            return;
        }

        System.out.println("===================================");
        System.out.println("GIF generado correctamente:");
        System.out.println(salida.getAbsolutePath());
        System.out.println("Imágenes válidas:  " + imagenesValidas);
        System.out.println("Imágenes omitidas: " + imagenesOmitidas);
        System.out.println("===================================");
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
}
