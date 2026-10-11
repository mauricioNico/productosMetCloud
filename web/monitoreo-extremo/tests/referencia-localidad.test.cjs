const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const original=JSON.parse(fs.readFileSync(path.join(root,'localidades-georef.json'),'utf8'));
const ui={};
const document={
  getElementById(id){return ui[id] ||= {
    value:'',disabled:false,hidden:true,checked:true,style:{},
    addEventListener(){},setAttribute(){},replaceChildren(){},
    append(){},querySelector(){return null;},textContent:''
  }},
  querySelectorAll(){return []},
  addEventListener(){}
};
const window={innerWidth:1200};
const ctx={window,document,console,fetch:async()=>({ok:true,json:async()=>original})};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(root,'localidades-layer.js'),'utf8'),ctx);
const api=window.GeoRefPlaces;
const nearLat=api.haversineKm(-57,-35,-57,-34);
assert(Math.abs(nearLat-111.195)<.2,'Una diferencia de 1° de latitud debe medir aprox. 111.2 km');
assert.equal(api.haversineKm(-65,-40,-65,-40),0);
assert(Math.abs(api.haversineKm(-57,-34,-60,-34)-api.haversineKm(-60,-34,-57,-34))<1e-9);
async function run(){
  assert.equal(api.nearest(-57.95,-34.92),null,'Sin GeoRef no se inventan localidades');
  api.init({proj:(lon,lat)=>[lon,lat],W:610,H:530});
  await new Promise(resolve=>setImmediate(resolve));
  const laPlata=api.searchResults('la plata').find(x=>x.province==='Buenos Aires');
  assert(laPlata,'La Plata faltante');
  const found=api.nearest(laPlata.lon,laPlata.lat);
  assert(found,'Nearest debe devolver localidad');
  assert(found.km<0.001,'El centroide coincide con una localidad GeoRef');
  assert.equal(found.province,'Buenos Aires');
  assert(Math.abs(found.lat-laPlata.lat)<0.03);
  const p=api.nearest(-69,-34.25);
  assert(p && Number.isFinite(p.km) && p.km>=0,'Mendoza debe devolver referencia geográfica');
  assert.equal(p.province,'Mendoza');
  // El mapa sin selección no debe volver a renderizar localidades dispersas.
  const canvas={width:1220,_mapZoom:{factor:1,cx:305,cy:265}};
  const drawCtx={save(){},restore(){},setTransform(){},beginPath(){},
    arc(){},fill(){},stroke(){},fillText(){},strokeText(){},
    measureText(s){return{width:s.length*6}}};
  api.draw(canvas,drawCtx,canvas._mapZoom);
  assert.equal(canvas._placeHits.length,0,'Mapa debe permanecer limpio sin selección');
  assert.equal(api.nearest(NaN,-35),null,'No usar coordenadas inválidas');
  console.log('Referencia GeoRef OK: Haversine, La Plata, Mendoza, GeoRef no cargado y mapa limpio.');
}
run().catch(error=>{console.error(error);process.exitCode=1});
