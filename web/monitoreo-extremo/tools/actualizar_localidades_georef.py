#!/usr/bin/env python3
"""Versionar los centroides de localidades de GeoRef para el visor (sin interpolar coordenadas).

Uso:
    python web/monitoreo-extremo/tools/actualizar_localidades_georef.py

Descarga oficial: https://www.argentina.gob.ar/georef/descarga-de-la-base-completa
El JSON generado se publica con Pages; el navegador no solicita servicios externos.
"""
from __future__ import annotations

import hashlib
import json
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
DEST = ROOT / "web/monitoreo-extremo/localidades-georef.json"
URLS = (
    "https://apis.datos.gob.ar/georef/api/v2.0/localidades.json",
    "https://apis.datos.gob.ar/georef/api/localidades.json",
)


def fetch() -> tuple[str, bytes]:
    failures = []
    for url in URLS:
        for retry in range(2):
            try:
                req = Request(url, headers={"User-Agent": "productosMetCloud-visor/1.0 (GeoRef public source)", "Accept": "application/json"})
                with urlopen(req, timeout=60) as response:
                    content = response.read(35 * 1024 * 1024 + 1)
                    if len(content) > 35 * 1024 * 1024:
                        raise ValueError("Archivo demasiado grande")
                    return url, content
            except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                failures.append(f"{url}: {exc}")
                time.sleep(3 * (retry + 1))
    raise RuntimeError("No se pudo recuperar la base oficial:\n" + "\n".join(failures))


def norm(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if unicodedata.category(c) != "Mn")


def main() -> None:
    url, raw = fetch()
    response = json.loads(raw)
    # GeoRef v1/v2 may include metadata outside the collection.
    if isinstance(response, list):
        entries = response
    else:
        entries = response.get("localidades") or response.get("datos") or response.get("data") or response.get("features")
        if not isinstance(entries, list):
            raise ValueError(f"Esquema GeoRef inesperado: {list(response)[:10]}")
    rows = []
    ids = set()
    for entry in entries:
        if entry.get("type") == "Feature":
            attr = entry.get("properties", {})
            geom = entry.get("geometry") or {}
        else:
            attr, geom = entry, {}
        geo = attr.get("centroide") or {}
        lon, lat = geo.get("lon"), geo.get("lat")
        if lon is None or lat is None:
            coords = geom.get("coordinates")
            if geom.get("type") == "Point" and isinstance(coords, list) and len(coords) >= 2:
                lon, lat = coords[:2]
        try:
            lon, lat = float(lon), float(lat)
        except (TypeError, ValueError):
            continue
        if not (-86 <= lon <= -44 and -56 <= lat <= -19):
            continue
        identifier = str(attr.get("id", "")).strip()
        name = str(attr.get("nombre", "")).strip()
        provincia = attr.get("provincia") or {}
        province_name = provincia.get("nombre", "") if isinstance(provincia, dict) else str(provincia)
        province_name = str(province_name).strip()
        if not identifier or not name or not province_name or identifier in ids:
            continue
        ids.add(identifier)
        # schema [id, nombre, provincia, lon, lat, categoria] (lon/lat WGS84)
        rows.append([identifier, name, province_name, round(lon, 6), round(lat, 6),
                     str(attr.get("categoria", "") or "")])
    provinces = Counter(row[2] for row in rows)
    if len(rows) < 3000 or len(provinces) < 20 or len(rows) > 15000:
        raise ValueError(f"Base GeoRef incompleta: {len(rows)} localidades y {len(provinces)} provincias")
    rows.sort(key=lambda row: (norm(row[2]), norm(row[1]), row[0]))
    output = {
        "fuente": "GeoRef Argentina - listado oficial de localidades",
        "url": url,
        "capturado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256_descarga": hashlib.sha256(raw).hexdigest(),
        "total": len(rows),
        "campos": ["id", "nombre", "provincia", "lon", "lat", "categoria"],
        "localidades": rows,
    }
    DEST.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"GeoRef: {len(rows)} localidades, {len(provinces)} provincias; {DEST.stat().st_size} bytes")
    print(f"Fuente: {url}; sha256={output['sha256_descarga']}")
    for example in ["La Plata", "Córdoba", "Rosario", "Mar del Plata"]:
        matching = [r for r in rows if norm(r[1]) == norm(example)]
        print(f"Control {example}: {matching[:2]}")


if __name__ == "__main__":
    main()
