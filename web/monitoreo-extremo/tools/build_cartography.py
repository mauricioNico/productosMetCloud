"""Build the viewer-only asset from pinned Natural Earth and preserved IGN data."""
import argparse
import hashlib
import json
from pathlib import Path
from shapely import make_valid
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--natural-earth', type=Path, required=True)
a = parser.parse_args()
root = Path(__file__).resolve().parents[3]
source = root/'web/cartografia/provincias_ign.geojson'
current = root/'web/monitoreo-extremo/base-cartography.js'
previous = json.loads(current.read_text().split('window.BASE_CARTOGRAPHY=', 1)[1].rstrip(';\n'))
assert hashlib.sha256(a.natural_earth.read_bytes()).hexdigest() == previous['source_sha256'], 'Unexpected Natural Earth revision'
assert hashlib.sha256(source.read_bytes()).hexdigest() == previous['province_source_sha256'], 'Unexpected IGN snapshot'
domain = box(-86, -56, -44, -19)
countries = []
for f in json.loads(a.natural_earth.read_text())['features']:
    if f['properties']['ADM0_A3'] in ('ARG', 'CHL', 'BOL', 'PRY', 'BRA', 'URY', 'PER'):
        countries.append({'type': 'Feature', 'properties': {'name': f['properties']['ADMIN'], 'iso': f['properties']['ADM0_A3']},
                          'geometry': mapping(shape(f['geometry']).intersection(domain))})
provinces = []
for f in json.loads(source.read_text())['features']:
    assert f['properties']['fuente'] == 'IGN'
    geom = shape(f['geometry'])
    if not geom.is_valid:
        # Repair nested shells in the source for rendering only. Raw source stays untouched.
        geom = make_valid(geom)
    if geom.geom_type == 'GeometryCollection':
        geom = unary_union([p for p in geom.geoms if p.geom_type in ('Polygon', 'MultiPolygon')])
    geom = geom.intersection(domain)
    assert geom.is_valid and not geom.is_empty
    provinces.append({'type': 'Feature', 'properties': f['properties'], 'geometry': mapping(geom)})
argentina = unary_union([shape(f['geometry']) for f in provinces])
for f in countries:
    if f['properties']['iso'] == 'ARG':
        f['geometry'] = mapping(argentina)
        f['properties']['source'] = 'IGN via Georef'
previous.update(countries={'type': 'FeatureCollection', 'features': countries}, provinces=provinces)
current.write_text('// Countries: Natural Earth 1:10m. Argentina and provinces: IGN via Georef. See CARTOGRAFIA.md.\nwindow.BASE_CARTOGRAPHY='+json.dumps(previous, separators=(',', ':'), ensure_ascii=False)+';\n')
