import unittest
import numpy as np
from indice import diagnose,LATS,LONS
class Test(unittest.TestCase):
    def test_normal(self):
        z=np.tile((6000-20*LATS)[:,None],(1,len(LONS)))
        self.assertFalse(any(diagnose(z)["sectors"].values()))
    def test_block(self):
        z=np.tile((6000-20*LATS)[:,None],(1,len(LONS)))
        for lon in (-60,-57.5,-55):
            j=list(LONS).index(lon)
            z[list(LATS).index(55),j]=5900
        self.assertTrue(diagnose(z)["sectors"]["ATL"])
    def test_missing(self):
        with self.assertRaises(ValueError): diagnose(np.zeros((1,1)))
