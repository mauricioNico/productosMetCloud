"""Smoke test in real browser with the latest *real* meteorological ZIP.

Usage:
 python web/monitoreo-extremo/tests/localidades-browser.py --zip /tmp/real.zip --metadata /tmp/meta.json
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser()
parser.add_argument('--zip',type=Path,required=True)
parser.add_argument('--metadata',type=Path,required=True)
parser.add_argument('--screenshot',type=Path)
args=parser.parse_args()
root=Path(__file__).resolve().parents[3]
metadata=json.loads(args.metadata.read_text(encoding='utf-8'))
assert metadata['estado']=='PUBLICADO'
assert args.zip.stat().st_size>1000
server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(root)))
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1440,'height':1000})
  errors=[]
  page.on('pageerror',lambda err:errors.append(str(err)))
  page.route('**/datos/publicacion.json?*',
             lambda route:route.fulfill(content_type='application/json',body=args.metadata.read_bytes()))
  page.route('**/datos/monitoreo-extremo.zip?*',
             lambda route:route.fulfill(content_type='application/zip',body=args.zip.read_bytes()))
  page.goto(f'http://127.0.0.1:{server.server_port}/web/monitoreo-extremo/index.html')
  page.wait_for_function("document.getElementById('placesStatus').textContent.includes('GeoRef')",timeout=30000)
  page.wait_for_function("csvRows.length > 100 && Object.keys(alertFeatures).length === 6",timeout=45000)
  assert page.locator('canvas.mapcanvas').count()==4
  initial=page.evaluate("document.querySelector('#rainGrid canvas')._placeHits.length")
  assert initial>15, 'Initial clustered locality markers missing'
  page.locator('#showPlaces').uncheck()
  assert page.evaluate("document.querySelector('#rainGrid canvas')._placeHits.length")==0
  page.locator('#showPlaces').check()
  assert page.evaluate("document.querySelector('#rainGrid canvas')._placeHits.length")>15
  page.locator('#showPlaceLabels').uncheck()
  page.locator('#showPlaceLabels').check()
  # Search by place and province, accents optional.
  page.locator('#placeSearch').fill('Rio Cuarto')
  first=page.locator('#placeSuggestions button').first
  first.wait_for(timeout=5000)
  assert 'Río Cuarto' in first.inner_text()
  first.click()
  assert 'Río Cuarto' in page.locator('#placeSearch').input_value()
  assert page.evaluate("Array.from(document.querySelectorAll('canvas.mapcanvas')).every(c=>c._mapZoom.factor>=3.3)")
  # Navigation must preserve a selected georeferenced locality on the next set of canvases.
  page.locator('#nextDay').click()
  assert page.locator('#dayTitle').inner_text()=='Día 2 de 3'
  assert page.evaluate("Array.from(document.querySelectorAll('canvas.mapcanvas')).every(c=>c._mapZoom.factor>=3.3)")
  assert page.locator('canvas.mapcanvas').count()==4
  assert page.evaluate("document.querySelector('#rainGrid canvas')._placeHits.length")>0
  # Zoom and pan still work with the overlay.
  c=page.locator('#rainGrid canvas').first
  c.scroll_into_view_if_needed()
  before=page.evaluate("document.querySelector('#rainGrid canvas')._mapZoom.factor")
  c.hover()
  page.mouse.wheel(0,-110)
  after=page.evaluate("document.querySelector('#rainGrid canvas')._mapZoom.factor")
  assert after>before
  page.locator('#placeClear').click()
  assert not page.locator('#placeSearch').input_value()
  assert not errors,errors
  if args.screenshot:
   args.screenshot.parent.mkdir(parents=True,exist_ok=True)
   page.screenshot(path=str(args.screenshot),full_page=True)
  print(json.dumps({'status':'OK','metadata_cycle':metadata['ciclo_utc'],
    'localities':page.locator('#placesStatus').inner_text(),'initial_markers':initial,
    'four_maps':True,'selection_survives_day_navigation':True,
    'zoom_and_search':True,'js_errors':errors},ensure_ascii=False))
  browser.close()
finally:
 server.shutdown()
 server.server_close()
