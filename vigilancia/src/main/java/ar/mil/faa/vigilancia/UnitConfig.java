package ar.mil.faa.vigilancia;
public record UnitConfig(String name, double lat, double lon, String rainRegion,
                         String windRegion, String snowRegion, boolean zondaApplicable, boolean active) {
    public String regionFor(Phenomenon p) {
        return switch (p) {
            case LLUVIA -> rainRegion;
            case VIENTO -> windRegion;
            case NIEVE -> snowRegion;
            case ZONDA -> "ZONDA";
        };
    }
}
