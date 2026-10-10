"""Validate viewer geometry without changing original official or weather inputs."""
import hashlib
import json
from pathlib import Path
from shapely.geometry import shape
from shapely.ops import unary_union
root = Path(__file__).resolve().parents[3]
asset = root/'web/monitoreo-extremo/base-cartography.js'
j = json.loads(asset.read_text().split('window.BASE_CARTOGRAPHY=', 1)[1].rstrip(';\n'))
source = root/'web/cartografia/provincias_ign.geojson'
assert hashlib.sha256(source.read_bytes()).hexdigest() == j['province_source_sha256']
assert len(j['provinces']) == 24
geometries = [shape(f['geometry']) for f in j['provinces']]
assert all(g.is_valid and not g.is_empty for g in geometries)
arg = shape(next(f['geometry'] for f in j['countries']['features'] if f['properties']['iso'] == 'ARG'))
assert arg.is_valid
assert arg.symmetric_difference(unary_union(geometries)).area < 1e-10, 'Argentina outline must exactly follow official provinces'
assert all(g.difference(arg).area < 1e-10 for g in geometries), 'Province crosses official country outline'
# Source has small overlaps; report them instead of changing official boundaries.
overlap = sum(g.area for g in geometries) - arg.area
assert overlap/arg.area < .0001, 'Unexpected province overlap exceeds source tolerance'
print(f'24 valid official geometries; union equals national outline; source overlap {overlap:.8f} deg² retained.')
