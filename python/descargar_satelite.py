#!/usr/bin/env python
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

import requests


LOGIN_URL = "https://imagenesmeteorologicas.faa.mil.ar/app/model/login.php"
IMG_URL = "https://imagenesmeteorologicas.faa.mil.ar/app/model/serve_realtime.php?f=G19_BAND13_SEC_LATEST.png"

MAX_INTENTOS = 3


def pedir_con_reintentos(session, metodo, url, **kwargs):
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            print(f"Intento {intento}/{MAX_INTENTOS}: {url}")

            respuesta = session.request(
                metodo,
                url,
                timeout=kwargs.pop("timeout", 30),
                **kwargs
            )

            respuesta.raise_for_status()
            return respuesta

        except requests.exceptions.ConnectTimeout:
            print("⚠ Timeout de conexión. El servidor no respondió.")

        except requests.exceptions.ReadTimeout:
            print("⚠ Timeout de lectura. La conexión abrió, pero no terminó de responder.")

        except requests.exceptions.ConnectionError as e:
            print(f"⚠ Error de conexión: {e}")

        except requests.exceptions.HTTPError as e:
            print(f"⚠ Error HTTP: {e}")

        except requests.exceptions.RequestException as e:
            print(f"⚠ Error inesperado en requests: {e}")

        if intento < MAX_INTENTOS:
            print("⏳ Reintentando en 60 segundos...")
            time.sleep(60)

    return None


def main():
    carpeta = Path("satelite")
    carpeta.mkdir(parents=True, exist_ok=True)

    usuario = os.environ.get("SAT_USER")
    password = os.environ.get("SAT_PASSWORD")

    if not usuario or not password:
        print("❌ Faltan SAT_USER o SAT_PASSWORD.")
        sys.exit(1)

    session = requests.Session()

    r = pedir_con_reintentos(session, "GET", LOGIN_URL, timeout=30)

    if r is None:
        print("❌ No se pudo acceder al login después de varios intentos.")
        sys.exit(1)

    match = re.search(r'name="csrf_token" value="([^"]+)"', r.text)

    if not match:
        print("❌ No se pudo obtener csrf_token.")
        sys.exit(1)

    token = match.group(1)

    form = {
        "csrf_token": token,
        "Usuario": usuario,
        "Contraseña": password
    }

    login = pedir_con_reintentos(
        session,
        "POST",
        LOGIN_URL,
        data=form,
        headers={
            "Referer": LOGIN_URL,
            "Origin": "https://imagenesmeteorologicas.faa.mil.ar"
        },
        timeout=30
    )

    if login is None:
        print("❌ No se pudo iniciar sesión después de varios intentos.")
        sys.exit(1)

    img = pedir_con_reintentos(session, "GET", IMG_URL, timeout=60)

    if img is None:
        print("❌ No se pudo descargar la imagen después de varios intentos.")
        sys.exit(1)

    content_type = img.headers.get("Content-Type", "")

    if "image" not in content_type.lower():
        print("❌ La respuesta no parece ser una imagen.")
        print(f"Content-Type recibido: {content_type}")
        sys.exit(1)

    fecha = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archivo = carpeta / f"G19_BAND13_{fecha}.png"

    archivo.write_bytes(img.content)

    print(f"✔ Imagen descargada: {archivo}")


if __name__ == "__main__":
    main()
