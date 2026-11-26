"""Construir el catálogo público a partir de artefactos validados de Actions."""
import argparse
import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from indice import DELTAS, LATS, LONS, diagnose

MODELS = ("GFS", "ECMWF")


def pack(frame):
    """Reconstruye la grilla muestreada y coteja cada fila con el motor existente."""
    z = np.full((len(LATS), len(LONS)), np.nan)
    if len(frame["rows"]) != len(LONS):
        raise ValueError("Cantidad de meridianos incorrecta")
    for j, row in enumerate(frame["rows"]):
        if row["lon"] != LONS[j] or [v["delta"] for v in row["details"]] != DELTAS:
            raise ValueError("Coordenadas incorrectas")
        for v in row["details"]:
            for lat, height in zip((40, 55, 50, 65), v["z"], strict=True):
                i = int((lat + v["delta"] - 30) / 2.5)
                if np.isfinite(z[i, j]) and z[i, j] != height:
                    raise ValueError("Alturas contradictorias")
                z[i, j] = height
    check = diagnose(z)
    if any(check[k] != frame[k] for k in ("rows", "sectors")):
        raise ValueError("Diagnóstico incompatible con las alturas")
    return z.tolist()


def read_run(path, model, previous):
    src = json.loads(path.read_text())
    run = datetime.fromisoformat(src["run"])
    if src["model"] != model or run.utcoffset() != timedelta(0) or run.minute or run.second or run.microsecond:
        raise ValueError("Inicialización incorrecta")
    data = previous or {"model": model, "run": run.isoformat(), "instant": {}, "daily": {}, "expected": []}
    new_steps = set()
    for frame in src["instant"]:
        step = frame["step"]
        if type(step) != int or step not in range(0, 241, 6) or step in new_steps:
            raise ValueError("Plazo no válido")
        valid = run + timedelta(hours=step)
        if datetime.fromisoformat(frame["valid"]) != valid:
            raise ValueError("Validez incorrecta")
        data["instant"][valid.isoformat()] = pack(frame)
        new_steps.add(step)
    if not new_steps:
        raise ValueError("Sin campos")
    expected = new_steps | set(map(int, src["errors"])) | set(data["expected"])
    data["expected"] = sorted(expected)
    touched = {(run + timedelta(hours=s)).date().isoformat() for s in new_steps}
    for day in touched:
        data["daily"].pop(day, None)
    for frame in src["daily"]:
        if frame.get("rows"):
            data["daily"][frame["date"]] = pack(frame)
    # Recalcular también días recuperados al combinar reintentos parciales.
    for day in {s[:10] for s in data["instant"]}:
        slots = [f"{day}T{h:02}:00:00+00:00" for h in (0, 6, 12, 18)]
        if day not in data["daily"] and all(s in data["instant"] for s in slots):
            data["daily"][day] = np.mean([data["instant"][s] for s in slots], axis=0).tolist()
    return data


def publish(source, dest, job):
    now = datetime.now(timezone.utc)
    dest.mkdir(parents=True, exist_ok=True)
    manifest = dest / "catalog.json"
    cat = json.loads(manifest.read_text()) if manifest.exists() else {"runs": [], "status": {}}
    cutoff = now - timedelta(days=30)
    for model in MODELS:
        try:
            files = list(source.rglob(model + ".json"))
            if len(files) != 1:
                raise ValueError("Artefacto ausente o ambiguo")
            init = datetime.fromisoformat(json.loads(files[0].read_text())["run"])
            if init < cutoff or init > now:
                raise ValueError("Corrida fuera de la ventana histórica")
            name = f"{model}/{init:%Y%m%d%H}.json.gz"
            path = dest / name
            previous = json.loads(gzip.decompress(path.read_bytes())) if path.exists() else None
            data = read_run(files[0], model, previous)
            valid = sorted(data["instant"])
            steps = [int((datetime.fromisoformat(t)-init).total_seconds()/3600) for t in valid]
            missing = sorted(set(data["expected"]) - set(steps))
            payload = json.dumps(data, separators=(",", ":"), allow_nan=False).encode()
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(gzip.compress(payload, mtime=0))
            record = dict(model=model, run=data["run"], file=name, steps=steps, missing=missing,
                          valid=valid, daily=sorted(data["daily"]), bytes=path.stat().st_size, job=job)
            cat["runs"] = [r for r in cat["runs"] if r["file"] != name] + [record]
            status = "incompleto" if missing else "completo"
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            status = "falló la actualización"
            print(model, exc)
        cat["status"][model] = dict(state=status, checked=now.isoformat(), job=job)
    # Conservar por modelo la última corrida válida incluso durante una interrupción prolongada.
    latest = {max((r["run"] for r in cat["runs"] if r["model"] == m), default="") for m in MODELS}
    for r in cat["runs"][:]:
        if datetime.fromisoformat(r["run"]) < cutoff and r["run"] not in latest:
            (dest / r["file"]).unlink(missing_ok=True)
            cat["runs"].remove(r)
    cat["runs"].sort(key=lambda r: r["run"], reverse=True)
    cat["updated"] = now.isoformat()
    manifest.write_text(json.dumps(cat, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("dest", type=Path)
    parser.add_argument("job")
    args = parser.parse_args()
    publish(args.source, args.dest, args.job)
