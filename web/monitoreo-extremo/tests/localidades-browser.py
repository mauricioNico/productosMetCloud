"""Prueba en Chromium de GeoRef y el tooltip de distancia con publicación meteorológica real.

Ejecutar con:
 python web/monitoreo-extremo/tests/localidades-browser.py --zip archivo-real.zip --metadata publicacion.json
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
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
  page.wait_for_function("csvRows.length>100 && Object.keys(alertFeatures).length===6",timeout=45000)
  assert page.locator('canvas.mapcanvas').count()==6
  assert page.evaluate("Array.from(document.querySelectorAll('canvas.mapcanvas')).every(c=>c._placeHits.length===0)"),'The map must be clean without search'
  page.locator('#placeSearch').fill('Tupungato')
  suggestion=page.locator('#placeSuggestions button').filter(has_text='Tupungato').first
  suggestion.wait_for(timeout=5000)
  suggestion.click()
  assert 'Tupungato' in page.locator('#placeSearch').input_value()
  assert page.evaluate("Array.from(document.querySelectorAll('canvas.mapcanvas')).every(c=>c._mapZoom.factor>=3.3)")

  # Center of each zoomed map corresponds to the selected GeoRef locality (Tupungato).
  texts={}
  for section in ('#alertGrid canvas','#rainGrid canvas','#tempGrid canvas'):
   for index in (0,1):
    canvas=page.locator(section).nth(index)
    canvas.scroll_into_view_if_needed()
    w=canvas.evaluate('(c)=>c.getBoundingClientRect().width')
    h=canvas.evaluate('(c)=>c.getBoundingClientRect().height')
    canvas.click(position={'x':w/2,'y':h/2},timeout=10000)
    tip=page.locator('#tip')
    msg=tip.inner_text()
    assert re.search(r'A [0-9.,]+ km de .+ \(Mendoza\)',msg),msg
    assert 'GeoRef' in msg and 'Clic:' in msg,msg
    if section=='#rainGrid canvas':
     assert 'Lluvia:' in msg and ('GFS' in msg or 'ECMWF' in msg),msg
    elif section=='#tempGrid canvas':
     assert 'Anomalía:' in msg and 'Normal NASA 1991–2020:' in msg,msg
     assert 'Media prevista 24h:' in msg,msg
    else:
     assert 'Nivel' in msg,msg
    texts[section+str(index)]=msg
  # Pinning persists during pointer motion; pan/zoom clears it.
  c=page.locator('#rainGrid canvas').first
  c.scroll_into_view_if_needed()
  width=c.evaluate('(x)=>x.getBoundingClientRect().width')
  height=c.evaluate('(x)=>x.getBoundingClientRect().height')
  c.click(position={'x':width/2,'y':height/2})
  msg=page.locator('#tip').inner_text()
  point=c.bounding_box()
  page.mouse.move(point['x']+width/2+4,point['y']+height/2+4)
  assert page.locator('#tip').inner_text()==msg,'Click tooltip should not be replaced by hover'
  before=c.evaluate('(x)=>x._mapZoom.factor')
  page.mouse.wheel(0,-110)
  after=c.evaluate('(x)=>x._mapZoom.factor')
  assert after>before
  assert c.evaluate('(x)=>x._clickedReference') is False
  # The selected locality remains centered when changing forecast day.
  page.locator('#nextDay').click()
  assert page.locator('#dayTitle').inner_text()=='Día 2 de 3'
  assert page.evaluate("Array.from(document.querySelectorAll('canvas.mapcanvas')).every(c=>c._mapZoom.factor>=3.3)")
  c=page.locator('#rainGrid canvas').first
  c.scroll_into_view_if_needed()
  width=c.evaluate('(x)=>x.getBoundingClientRect().width')
  height=c.evaluate('(x)=>x.getBoundingClientRect().height')
  c.click(position={'x':width/2,'y':height/2})
  assert re.search(r'km de .+ \(Mendoza\)',page.locator('#tip').inner_text())
  page.locator('#placeClear').click()
  assert not page.locator('#placeSearch').input_value()
  assert page.evaluate("Array.from(document.querySelectorAll('canvas.mapcanvas')).every(c=>c._placeHits.length===0)")
  assert not errors,errors
  if args.screenshot:
   args.screenshot.parent.mkdir(parents=True,exist_ok=True)
   page.screenshot(path=str(args.screenshot),full_page=True)
  print(json.dumps({'status':'OK','cycle':metadata['ciclo_utc'],
    'six_maps_clicked':len(texts),'references':texts,
    'search_and_day_navigation':True,'click_tooltip_persists':True,
    'zoom_clears_pin':True,'javascript_errors':errors},ensure_ascii=False))
  browser.close()
finally:
 server.shutdown()
 server.server_close()
