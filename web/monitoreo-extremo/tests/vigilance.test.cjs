const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'..'),sandbox={window:{}};vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root,'base-cartography.js'),'utf8'),sandbox);
vm.runInContext("const countries=window.BASE_CARTOGRAPHY.countries;let ARGENTINA=countries.features.find(f=>f.properties.iso==='ARG');",sandbox);
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
vm.runInContext(html.slice(html.indexOf('function puntoEnAnillo'),html.indexOf('function drawAlertMap')),sandbox);
vm.runInContext(html.slice(html.indexOf('const COUNTRY_LABELS='),html.indexOf('function drawCountryNames')),sandbox);
const evaluate=code=>vm.runInContext(code,sandbox);
function level(x,y,layer){sandbox.layer=layer;return evaluate(`nivelVigilancia(${x},${y},layer)`);}
const polygon=(ring,holes=[])=>({type:'Polygon',coordinates:[ring,...holes]});
const square=(x,y,size)=>[[x-size,y-size],[x+size,y-size],[x+size,y+size],[x-size,y+size],[x-size,y-size]];
const layer=(nivel,geometry)=>({type:'FeatureCollection',features:[{type:'Feature',properties:{nivel,unchanged:'original'},geometry}]});
const covering=polygon([[-86,-56],[-44,-56],[-44,-19],[-86,-19],[-86,-56]]);
const outside=[['Atlantic',-60,-45],['Chile',-70.6693,-33.4489],['Uruguay',-56.1645,-34.9011],['Brazil',-51.23,-30.0346],['Rio de la Plata',-57,-34.8]];
for(const color of ['AMARILLO','NARANJA','ROJO']){
 const original=layer(color,covering),before=JSON.stringify(original);
 for(const [name,x,y] of outside)assert.equal(level(x,y,original),null,name+' '+color);
 // Domain-wide invariant even when an alert spans sea and neighboring countries.
 let checked=0;for(let lon=-85;lon<=-45;lon+=.5)for(let lat=-55;lat<=-20;lat+=.5){
  if(!evaluate(`puntoEnGeoJSON(${lon},${lat},ARGENTINA.geometry)`)){assert.equal(level(lon,lat,original),null);checked++;}
 }
 assert(checked>4000);assert.equal(level(-58.3816,-34.6037,original),color);
 assert.equal(JSON.stringify(original),before,'Tooltip mutated original layer');
}
assert.equal(level(-64,-39.5,{features:[]}), 'VERDE');
for(const label of evaluate('COUNTRY_LABELS')){
 sandbox.label=label;assert(evaluate('puntoEnGeoJSON(label.lon,label.lat,countries.features.find(f=>f.properties.iso===label.iso).geometry)'),label.iso+' label outside country');
}
// Multiparts and interior holes in the national mask and alert geometry.
evaluate("ARGENTINA={geometry:{type:'MultiPolygon',coordinates:[[[[0,0],[8,0],[8,8],[0,8],[0,0]],[[2,2],[4,2],[4,4],[2,4],[2,2]]],[[[10,0],[12,0],[12,2],[10,2],[10,0]]]]}}");
const test=layer('ROJO',polygon(square(5,4,20)));
assert.equal(level(3,3,test),null,'National hole must exclude alert');
assert.equal(level(11,1,test),'ROJO','Second national part');
assert.equal(level(9,1,test),null,'Gap between national parts');
const hollow=layer('NARANJA',polygon(square(5,5,2),[square(5,5,.5)]));
assert.equal(level(5,5,hollow),'VERDE','Alert hole reveals base');
assert.equal(level(6,5,hollow),'NARANJA');
console.log('Vigilance OK: outside-country invariant for 3 levels, green base, national/alert holes and multiparts, 6 interior labels, immutable inputs.');
