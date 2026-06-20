import javax.imageio.*;
import javax.imageio.metadata.*;
import javax.imageio.stream.ImageOutputStream;
import java.awt.image.BufferedImage;
import java.io.File;
import java.util.Arrays;
import java.util.List;

public class CrearGifDesdeCarpeta {

    public static void main(String[] args) throws Exception {

        File carpeta = new File(args[0]);
       String fechaHora = java.time.LocalDateTime.now()
        .format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));

File carpetaSalida = new File("C:/modelos/loops");
carpetaSalida.mkdirs();

File salida = new File(
        carpetaSalida,
        "animacion_" + fechaHora + ".gif"
);

        int delayMs = 1000; // tiempo entre imágenes

        List<File> imagenes = Arrays.stream(carpeta.listFiles())
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

        ImageWriter writer = ImageIO.getImageWritersBySuffix("gif").next();

        try (ImageOutputStream output = ImageIO.createImageOutputStream(salida)) {

            writer.setOutput(output);
            writer.prepareWriteSequence(null);

            for (File archivo : imagenes) {
                BufferedImage imagen = ImageIO.read(archivo);

                ImageWriteParam params = writer.getDefaultWriteParam();
                IIOMetadata metadata = writer.getDefaultImageMetadata(
                        new ImageTypeSpecifier(imagen), params
                );

                configurarMetadata(metadata, delayMs);

                IIOImage frame = new IIOImage(imagen, null, metadata);
                writer.writeToSequence(frame, params);
            }

            writer.endWriteSequence();
        }

        System.out.println("GIF generado correctamente: " + salida.getAbsolutePath());
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

        byte[] loop = new byte[] { 0x1, 0x0, 0x0 };
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