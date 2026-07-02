name: Generar loop satelital

concurrency:
  group: satelite
  cancel-in-progress: false

on:
  workflow_dispatch:

  schedule:
    - cron: "0 */2 * * *"

jobs:
  loop-satelital:
    runs-on: ubuntu-latest
    timeout-minutes: 180

    steps:
      - name: Descargar repositorio
        uses: actions/checkout@v4

      - name: Instalar Java 17
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: 17

      - name: Instalar Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Instalar requests
        run: |
          python -m pip install --upgrade pip
          pip install requests

      - name: Compilar proyecto Java
        run: |
          mvn clean package

      - name: Descargar 6 imagenes cada 17 minutos
        env:
          SAT_USER: ${{ secrets.SAT_USER }}
          SAT_PASSWORD: ${{ secrets.SAT_PASSWORD }}
        run: |
          mkdir -p satelite

          for i in {1..6}
          do
            echo "Descargando imagen $i de 6..."
            python python/descargar_satelite.py

            if [ "$i" -lt 6 ]; then
              echo "Esperando 17 minutos..."
              sleep 1020
            fi
          done

          echo "Imagenes descargadas:"
          ls -lh satelite

      - name: Generar GIF satelital
        run: |
          mkdir -p loops
          java -jar target/generador-cartas-gfs-1.0.0-gif.jar satelite loops 1000

      - name: Ver tamaño del GIF
        run: |
          echo "Archivos generados:"
          ls -lh loops

      - name: Subir loop satelital
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: loop-satelital
          path: loops/
          retention-days: 7
