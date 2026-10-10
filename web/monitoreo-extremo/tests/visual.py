"""Exercise automatic ZIP loading and navigation with an identified input fixture.

Requires --zip and --metadata downloaded together from the real publication.
Use --synthetic only for explicit synthetic fixtures; these do not validate real data.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
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
if not a.synthetic:
    expected = json.loads((root/'docs/cartografia-monitoreo-extremo/publicacion.json').read_text())
    assert meta['ciclo_utc'] == expected['ciclo_utc'], 'Use the identified real cycle for this PR'
    assert hashlib.sha256(a.zip.read_bytes()).hexdigest() == '2f3a16329afb931b0f4bee4ae83e0eab5afc4c4ac05beb319a66f5eafeff4180', 'Real ZIP differs from the original PR validation'
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
        label_checks = []
        if not a.baseline_html:
            label_checks = page.evaluate('''()=>{
              const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
              ctx.font='bold 12px sans-serif';return COUNTRY_LABELS.map(label=>{
                const [x,y]=proj(label.lon,label.lat),width=ctx.measureText(label.text).width+7,height=19;
                const t=label.angle*RAD,c=Math.cos(t),s=Math.sin(t);
                const corners=[[-width/2,-height/2],[width/2,-height/2],[width/2,height/2],[-width/2,height/2]].map(([a,b])=>[x+a*c-b*s,y+a*s+b*c]);
                return {iso:label.iso,territory:puntoEnGeoJSON(label.lon,label.lat,countries.features.find(f=>f.properties.iso===label.iso).geometry),frame:corners.every(([a,b])=>a>0&&a<W&&b>0&&b<H)};
              });
            }''')
            assert len(label_checks)==6 and all(c['territory'] and c['frame'] for c in label_checks),label_checks
            # A deliberately oversize regression polygon tests rendering only;
            # real publication layers and screenshots stay unmodified.
            clip_result = page.evaluate('''()=>{
              const original={type:'FeatureCollection',features:[{properties:{nivel:'ROJO'},geometry:{type:'Polygon',coordinates:[[[-86,-56],[-44,-56],[-44,-19],[-86,-19],[-86,-56]]]}}]},snapshot=JSON.stringify(original);
              const empty=document.createElement('canvas'),filled=document.createElement('canvas');
              drawAlertMap(empty,{features:[]},'lluvia');drawAlertMap(filled,original,'lluvia');
              const ratio=window.devicePixelRatio||1,mask=document.createElement('canvas');mask.width=filled.width;mask.height=filled.height;
              const m=mask.getContext('2d');m.setTransform(ratio,0,0,ratio,0,0);m.fillStyle='white';m.strokeStyle='white';m.lineWidth=4;
              geoPath(m,ARGENTINA.geometry);m.fill('evenodd');m.stroke();
              const a=empty.getContext('2d').getImageData(0,0,empty.width,empty.height).data,b=filled.getContext('2d').getImageData(0,0,filled.width,filled.height).data,c=m.getImageData(0,0,mask.width,mask.height).data;
              let leaks=0,changedInside=0;for(let i=0;i<a.length;i+=4){if(a[i]!==b[i]||a[i+1]!==b[i+1]||a[i+2]!==b[i+2]){if(c[i+3]===0)leaks++;else changedInside++;}}
              return {leaks,changedInside,unchanged:JSON.stringify(original)===snapshot};
            }''')
            assert clip_result['leaks']==0 and clip_result['changedInside']>1000 and clip_result['unchanged'],clip_result
        else:
            clip_result = None
        asset = json.loads((root/'web/monitoreo-extremo/base-cartography.js').read_text().split('window.BASE_CARTOGRAPHY=',1)[1].rstrip(';\n'))
        argentina = shape(next(f['geometry'] for f in asset['countries']['features'] if f['properties']['iso']=='ARG'))
        outside_checks = []
        for day in range(1, 4):
            assert page.locator('#dayTitle').inner_text() == f'Día {day} de 3'
            assert page.locator('canvas').count() == 4
            # Verify the original alert polygon under its projected representative point.
            for fen, index in [('lluvia', 0), ('viento', 1)]:
                feature = next((f for f in layers[f'{fen}_{day*24}h']['features'] if f['properties'].get('nivel') in ('AMARILLO','NARANJA','ROJO') and not shape(f['geometry']).intersection(argentina).is_empty), None)
                if feature:
                    pos = shape(feature['geometry']).intersection(argentina).representative_point()
                    xy = page.evaluate('p=>alertProj(p[0],p[1])', [pos.x, pos.y])
                    can = page.locator('#alertGrid canvas').nth(index)
                    can.scroll_into_view_if_needed()
                    rect = can.bounding_box()
                    page.mouse.move(rect['x']+xy[0]*rect['width']/610, rect['y']+xy[1]*rect['height']/530)
                    assert page.locator('#tip').is_visible()
                    assert feature['properties']['nivel'].lower() in page.locator('#tip').inner_text()
            if not a.baseline_html:
                # Inspect actual tooltips over ocean, neighbors and coastal/border controls.
                controls=[('Atlantic',-60,-45),('Chile',-70.6693,-33.4489),('Uruguay',-56.1645,-34.9011),('Brazil',-51.23,-30.0346),('Rio de la Plata',-57,-34.8),('Buenos Aires coast',-57,-35.5),('Patagonian coast',-66.8,-45.5),('Tierra del Fuego Chile',-68.7,-54.8)]
                can=page.locator('#alertGrid canvas').first
                can.scroll_into_view_if_needed();rect=can.bounding_box()
                for name,lon,lat in controls:
                    assert not argentina.contains(shape({'type':'Point','coordinates':[lon,lat]})),name
                    xy=page.evaluate('p=>alertProj(p[0],p[1])',[lon,lat])
                    page.mouse.move(rect['x']+xy[0]*rect['width']/610,rect['y']+xy[1]*rect['height']/530)
                    assert not page.locator('#tip').is_visible(),name
                    outside_checks.append({'day':day,'place':name,'tooltip_hidden':True})
            if not a.baseline_html:
                xy=page.evaluate('alertProj(-64,-39.5)');can=page.locator('#alertGrid canvas').first
                can.scroll_into_view_if_needed();rect=can.bounding_box()
                page.mouse.move(rect['x']+xy[0]*rect['width']/610,rect['y']+xy[1]*rect['height']/530)
                assert page.locator('#tip').inner_text() == 'Nivel verde para lluvia'
            # A known loaded grid point must retain its numeric precipitation tooltip.
            point = page.evaluate('proj(csvRows.find(r=>r.lead===dayLeads[currentDay]&&r.model==="GFS").lon,csvRows.find(r=>r.lead===dayLeads[currentDay]&&r.model==="GFS").lat)')
            canvas = page.locator('#rainGrid canvas').first
            canvas.scroll_into_view_if_needed()
            bounds = canvas.bounding_box()
            page.mouse.move(bounds['x'] + point[0]*bounds['width']/610,
                            bounds['y'] + point[1]*bounds['height']/530)
            assert page.locator('#tip').is_visible()
            ecmwf=page.evaluate('proj(csvRows.find(r=>r.lead===dayLeads[currentDay]&&r.model==="ECMWF").lon,csvRows.find(r=>r.lead===dayLeads[currentDay]&&r.model==="ECMWF").lat)')
            second=page.locator('#rainGrid canvas').nth(1);second.scroll_into_view_if_needed();b=second.bounding_box()
            page.mouse.move(b['x']+ecmwf[0]*b['width']/610,b['y']+ecmwf[1]*b['height']/530)
            assert page.locator('#tip').is_visible() and 'ECMWF' in page.locator('#tip').inner_text()
            if a.synthetic:
                page.evaluate("status('PRUEBA CON DATOS SINTÉTICOS — NO OPERATIVA')")
            if day == 1:
                page.screenshot(path=str(a.out/'tooltip.png'), full_page=True)
            page.mouse.move(0, 0)
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(a.out/f'day-{day}.png'), full_page=True)
            if day == 1 and not a.baseline_html:
                # Enlarged excerpts of the real render for coastline/border inspection.
                for name,lon,lat in [('rio-plata',-58,-35),('litoral-bonaerense',-57.4,-37),('costa-patagonica',-66.5,-47),('frontera-chile',-70,-36),('tierra-fuego',-68.4,-54)]:
                    page.evaluate('''p=>{
                      const panel=document.createElement('div');panel.id='geographic-review-detail';panel.style='width:700px;padding:20px;background:white;color:#173950';
                      const title=document.createElement('h2');title.textContent=p.name+' · Detalle del render real · 2026-10-09 12 UTC';panel.append(title);
                      const [x,y]=proj(p.lon,p.lat);
                      for(const [selector,label] of [['#alertGrid canvas','Vigilancia lluvia'],['#rainGrid canvas','Precipitación GFS']]){
                        const heading=document.createElement('h3');heading.textContent=label;panel.append(heading);
                        const src=document.querySelector(selector),can=document.createElement('canvas');can.width=600;can.height=360;
                        const ratio=src.width/W,sx=Math.max(0,Math.min(W-100,x-50)),sy=Math.max(0,Math.min(H-60,y-30));
                        can.getContext('2d').drawImage(src,sx*ratio,sy*ratio,100*ratio,60*ratio,0,0,600,360);panel.append(can);
                      }
                      document.body.append(panel);
                    }''',{'name':name,'lon':lon,'lat':lat})
                    page.locator('#geographic-review-detail').screenshot(path=str(a.out/f'detail-{name}.png'))
                    page.evaluate("document.getElementById('geographic-review-detail').remove()")
            if day < 3:
                page.locator('#nextDay').click()
        page.locator('#prevDay').click()
        assert page.locator('#dayTitle').inner_text() == 'Día 2 de 3'
        assert page.evaluate('alertFeatures') == layers, 'Navigation mutated original alert polygons'
        assert not errors, errors
        report = {'input': str(a.zip.resolve()), 'synthetic': a.synthetic,
                  'cycle': meta['ciclo_utc'], 'days_checked': 3, 'maps_per_day': 4,
                  'original_alert_polygons_preserved': True, 'javascript_errors': errors, 'baseline': bool(a.baseline_html), 'labels':label_checks,'canvas_clipping':clip_result,'outside_tooltips':outside_checks,'zip_sha256':hashlib.sha256(a.zip.read_bytes()).hexdigest()}
        (a.out/'results.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
        browser.close()
finally:
    server.shutdown()
    server.server_close()
