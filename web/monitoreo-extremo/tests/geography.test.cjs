const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const path=require('node:path'),root=path.resolve(__dirname,'..');
const sandbox={window:{}};vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root,'base-cartography.js'),'utf8'),sandbox);
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const start=html.indexOf('const W='),end=html.indexOf('function color',start);
vm.runInContext(html.slice(start,end),sandbox);
const evaluate=code=>vm.runInContext(code,sandbox);
let error=0;
for(let lon=-85;lon<=-45;lon+=.5)for(let lat=-55;lat<=-20;lat+=.5){
 const [x,y]=evaluate(`proj(${lon},${lat})`),[a,b]=evaluate(`unproj(${x},${y})`);
 error=Math.max(error,Math.abs(a-lon),Math.abs(b-lat));
 assert(x>=0&&x<=610&&y>=0&&y<=530,'domain outside frame');
}
assert(error<1e-9,'projection inverse drifts');
assert(html.includes('function alertProj(lon,lat){return proj(lon,lat)}'));
assert(!html.includes('VIGILANCIA_VIEW')&&!html.includes('loadProvinces'));
const countries=sandbox.window.BASE_CARTOGRAPHY.countries.features;
for(const iso of ['ARG','CHL','BOL','PRY','BRA','URY'])assert(countries.some(f=>f.properties.iso===iso));
assert.equal(sandbox.window.BASE_CARTOGRAPHY.provinces.length,24);
assert(sandbox.window.BASE_CARTOGRAPHY.provinces.every(f=>f.properties.fuente==='IGN'));
assert.equal(countries.find(f=>f.properties.iso==='ARG').properties.source,'IGN via Georef');
// Known geographic locations must fall inside each country's original geography.
function insideRing(x,y,ring){let inside=false;for(let i=0,j=ring.length-1;i<ring.length;j=i++){const a=ring[i],b=ring[j];if((a[1]>y)!==(b[1]>y)&&x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])inside=!inside;}return inside;}
function inside(x,y,g){const polys=g.type==='Polygon'?[g.coordinates]:g.coordinates;return polys.some(r=>insideRing(x,y,r[0])&&!r.slice(1).some(h=>insideRing(x,y,h)));}
for(const [iso,lon,lat] of [['ARG',-58.3816,-34.6037],['CHL',-70.6693,-33.4489],['URY',-56.1645,-34.9011],['PRY',-57.5759,-25.2637],['BRA',-51.2300,-30.0346],['BOL',-64.7296,-21.5355]])assert(inside(lon,lat,countries.find(f=>f.properties.iso===iso).geometry),iso+' control point outside country');
assert(!inside(-60,-45,countries.find(f=>f.properties.iso==='ARG').geometry),'Atlantic control wrongly classified as land');
console.log(`Geography OK: 6 country control points, Atlantic exclusion, shared frame, inverse error ${error} degrees. Official IGN province provenance checked.`);
