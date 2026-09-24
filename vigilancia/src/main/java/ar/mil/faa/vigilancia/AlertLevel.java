package ar.mil.faa.vigilancia;
public enum AlertLevel {
    NONE(0), AMARILLO(1), NARANJA(2), ROJO(3);
    private final int rank;
    AlertLevel(int rank) { this.rank = rank; }
    public int rank() { return rank; }
    public static AlertLevel min(AlertLevel a, AlertLevel b) { return a.rank <= b.rank ? a : b; }
}
