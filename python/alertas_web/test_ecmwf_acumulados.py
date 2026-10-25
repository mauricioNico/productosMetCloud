"""Regresiones para la normalización de precipitación GRIB experimental."""
import unittest

import numpy as np

from clasificar_grilla_regional_lab import PASOS, normalizar_acumulados


class PruebasECMWFAcumulados(unittest.TestCase):
    def datos(self, acumulados):
        pp = np.asarray(acumulados, dtype=float).reshape(len(PASOS), 1, -1)
        ventanas = np.asarray(PASOS, dtype=float).reshape(len(PASOS), 1, 1)
        return {
            "model": "ECMWF",
            "precip_interval_mm": pp,
            "precip_window_h": np.broadcast_to(ventanas, pp.shape),
        }

    def test_monotono_sin_correccion(self):
        d = self.datos(np.arange(12))
        resultado = normalizar_acumulados(d)
        self.assertTrue(np.all(resultado >= 0))
        self.assertAlmostEqual(resultado.sum(), 11)

    def test_cuantizacion_0245_en_f060(self):
        a = np.arange(12, dtype=float)
        a[9] = a[8] - 0.245  # f060 frente a f054
        d = self.datos(a)
        resultado = normalizar_acumulados(d)
        self.assertEqual(resultado[9, 0, 0], 0)
        self.assertTrue(np.all(resultado >= 0))

    def test_reinicio_relevante_se_rechaza(self):
        a = np.arange(12, dtype=float)
        a[9] = a[8] - 0.8
        with self.assertRaisesRegex(ValueError, "f060: acumulado no monótono"):
            normalizar_acumulados(self.datos(a))

    def test_ventana_incompatible_se_rechaza(self):
        d = self.datos(np.arange(12))
        d["precip_window_h"] = d["precip_window_h"].copy()
        d["precip_window_h"][7] = 6
        with self.assertRaisesRegex(ValueError, "f48: acumulado distinto"):
            normalizar_acumulados(d)


if __name__ == "__main__":
    unittest.main()
