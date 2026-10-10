"""Exercise automatic ZIP loading and navigation with an identified input fixture.

Requires --zip and --metadata downloaded together from the real publication.
Use --synthetic only for explicit synthetic fixtures; these do not validate real data.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import zipfile
from shapely.geometry import shape
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--zip', type=Path, required=True)
parser.add_argument('--metadata', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--synthetic', action='store_true')
parser.add_argument('--baseline-html', type=Path, help='Render an original HTML snapshot for before/after review')
a = parser.parse_args()
root = Path(__file__).resolve().parents[3]
meta = json.loads(a.metadata.read_text())
assert meta['estado'] == 'PUBLICADO' and meta['publicacion_autorizada'] is False
with zipfile.ZipFile(a.zip) as archive:
    layers = {f'{fen}_{lead}h': json.loads(archive.read(f'{fen}_{lead}h.geojson'))
              for fen in ('lluvia', 'viento') for lead in (24, 48, 72)}
assert all(layer['type'] == 'FeatureCollection' for layer in layers.values())
a.out.mkdir(parents=True, exist_ok=True)
server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        if a.baseline_html:
            page.route('**/web/monitoreo-extremo/index.html', lambda r: r.fulfill(content_type='text/html', body=a.baseline_html.read_bytes()))
            page.route('https://raw.githubusercontent.com/mauricioNico/productosMetCloud/master/web/cartografia/*', lambda r: r.fulfill(content_type='application/json', body=(root/'web/cartografia'/r.request.url.rsplit('/',1)[1]).read_bytes()))
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.route('**/datos/publicacion.json?*', lambda r: r.fulfill(content_type='application/json', body=a.metadata.read_bytes()))
        page.route('**/datos/monitoreo-extremo.zip?*', lambda r: r.fulfill(content_type='application/zip', body=a.zip.read_bytes()))
        page.goto(f'http://127.0.0.1:{server.server_port}/web/monitoreo-extremo/index.html')
        page.wait_for_function("document.getElementById('state').className==='good'", timeout=30000)
        assert page.evaluate('csvRows.length') > 100
        assert page.evaluate('alertFeatures') == layers, 'Alert coordinates/properties changed on load'
        for day in range(1, 4):
            assert page.locator('#dayTitle').inner_text() == f'Día {day} de 3'
            assert page.locator('canvas').count() == 4
            # Verify the original alert polygon under its projected representative point.
            for fen, index in [('lluvia', 0), ('viento', 1)]:
                feature = next((f for f in layers[f'{fen}_{day*24}h']['features'] if f['properties'].get('nivel') in ('AMARILLO','NARANJA','ROJO') and not shape(f['geometry']).is_empty), None)
                if feature:
                    pos = shape(feature['geometry']).representative_point()
                    xy = page.evaluate('p=>alertProj(p[0],p[1])', [pos.x, pos.y])
                    can = page.locator('#alertGrid canvas').nth(index)
                    can.scroll_into_view_if_needed()
                    rect = can.bounding_box()
                    page.mouse.move(rect['x']+xy[0]*rect['width']/610, rect['y']+xy[1]*rect['height']/530)
                    assert page.locator('#tip').is_visible()
                    assert feature['properties']['nivel'].lower() in page.locator('#tip').inner_text()
            # A known loaded grid point must retain its numeric precipitation tooltip.
            point = page.evaluate('proj(csvRows.find(r=>r.lead===dayLeads[currentDay]&&r.model==="GFS").lon,csvRows.find(r=>r.lead===dayLeads[currentDay]&&r.model==="GFS").lat)')
            canvas = page.locator('#rainGrid canvas').first
            canvas.scroll_into_view_if_needed()
            bounds = canvas.bounding_box()
            page.mouse.move(bounds['x'] + point[0]*bounds['width']/610,
                            bounds['y'] + point[1]*bounds['height']/530)
            assert page.locator('#tip').is_visible()
            if a.synthetic:
                page.evaluate("status('PRUEBA CON DATOS SINTÉTICOS — NO OPERATIVA')")
            if day == 1:
                page.screenshot(path=str(a.out/'tooltip.png'), full_page=True)
            page.mouse.move(0, 0)
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(a.out/f'day-{day}.png'), full_page=True)
            if day < 3:
                page.locator('#nextDay').click()
        page.locator('#prevDay').click()
        assert page.locator('#dayTitle').inner_text() == 'Día 2 de 3'
        assert page.evaluate('alertFeatures') == layers, 'Navigation mutated original alert polygons'
        assert not errors, errors
        report = {'input': str(a.zip.resolve()), 'synthetic': a.synthetic,
                  'cycle': meta['ciclo_utc'], 'days_checked': 3, 'maps_per_day': 4,
                  'original_alert_polygons_preserved': True, 'javascript_errors': errors, 'baseline': bool(a.baseline_html)}
        (a.out/'results.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
        browser.close()
finally:
    server.shutdown()
    server.server_close()
