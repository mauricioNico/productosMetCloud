import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generar_alertas_web as alertas
import crear_demo

ROOT = Path(__file__).resolve().parents[3]
THRESHOLDS = ROOT / "vigilancia/config/umbrales.csv"


class TestAlertasWeb(unittest.TestCase):
    def test_consenso_conservador_y_cobertura(self):
        a = np.array([[2, 3, 0, -1, 0]], dtype=np.int8)
        b = np.array([[1, 3, -1, -1, 2]], dtype=np.int8)
        level, src, confianza = alertas.consenso(a, b)
        self.assertEqual(level.tolist(), [[1, 3, 0, -1, 2]])
        self.assertEqual(confianza.tolist(), [["MEDIA", "ALTA", "BAJA", "NO_EVALUADA", "BAJA"]])
        self.assertEqual(src[0, 4], "ECMWF")

    def test_seis_capas_marcadas_simulacion_y_recorte(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            crear_demo.construir(d / "datos")
            datos = d / "datos"
            manifest = alertas.generar(
                datos / "gfs.npz", datos / "ecmwf.npz",
                datos / "mascara_ficticia.geojson", THRESHOLDS,
                d / "salida", simulacion=True
            )
            self.assertEqual(len(manifest["capas"]), 6)
            self.assertEqual(manifest["estado"], "SIMULACION")
            self.assertIs(manifest["publicacion_autorizada"], False)
            any_alert = False
            for filename in manifest["capas"].values():
                geo = json.loads((d / "salida" / filename).read_text())
                self.assertEqual(geo["type"], "FeatureCollection")
                for feat in geo["features"]:
                    p = feat["properties"]
                    self.assertTrue(p["simulacion"])
                    self.assertIn(p["nivel"], alertas.NIVELES)
                    self.assertTrue(shape(feat["geometry"]).is_valid)
                    self.assertGreaterEqual(shape(feat["geometry"]).bounds[1], -38.001)
                    self.assertLessEqual(shape(feat["geometry"]).bounds[3], -24.999)
                    if p["nivel"] not in ("VERDE",):
                        any_alert = True
            self.assertTrue(any_alert)

    def test_sin_datos_no_es_verde(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            crear_demo.construir(d)
            model = alertas.cargar_modelo(d / "gfs.npz")
            reglas = alertas.leer_umbrales(THRESHOLDS)
            model["precip_interval_mm"][:, 0, 0] = np.nan
            level = alertas.evaluar(model, reglas, "lluvia", 0, 24)
            self.assertEqual(level[0, 0], -1)
            self.assertGreaterEqual(level[1, 1], 1)


if __name__ == "__main__":
    unittest.main()
