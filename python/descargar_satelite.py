#!/usr/bin/env python
import os
import re
import sys
from pathlib import Path
from datetime import datetime

import requests


LOGIN_URL = "https://imagenesmeteorologicas.faa.mil.ar/app/model/login.php"
IMG_URL = "https://imagenesmeteorologicas.faa.mil.ar/app/model/serve_realtime.php?f=G19_BAND13_SEC_LATEST.png"


def main():
    carpeta = Path("satelite")
    carpeta.mkdir(parents=True, exist_ok=True)

    usuario = os.environ.get("SAT_USER")
    password = os.environ.get("SAT_PASSWORD")

    if not usuario or not password:
        print("❌ Faltan SAT_USER o SAT_PASSWORD.")
        sys.exit(1)

    session = requests.Session()

    r = session.get(LOGIN_URL, timeout=30)
    r.raise_for_status()

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

    login = session.post(
        LOGIN_URL,
        data=form,
        headers={
            "Referer": LOGIN_URL,
            "Origin": "https://imagenesmeteorologicas.faa.mil.ar"
        },
        timeout=30
    )
    login.raise_for_status()

    fecha = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    archivo = carpeta / f"G19_BAND13_{fecha}.png"

    img = session.get(IMG_URL, timeout=60)
    img.raise_for_status()

    archivo.write_bytes(img.content)

    print(f"✔ Imagen descargada: {archivo}")


if __name__ == "__main__":
    main()
