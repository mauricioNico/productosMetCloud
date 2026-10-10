const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const raw=JSON.parse(fs.readFileSync(path.join(root,'localidades-georef.json'),'utf8'));
assert(raw.total>=3000);
assert(new Set(raw.localidades.map(x=>x[2])).size===24,'Expected the 24 Argentine jurisdictions');
const ui={};
function stub(id){
  if(!ui[id])ui[id]={
    value:'',disabled:false,hidden:true,checked:true,style:{},listeners:{},attributes:{},
    textContent:'',children:[],
    addEventListener(name,fn){this.listeners[name]=fn;},
    setAttribute(k,v){this.attributes[k]=v;},
    replaceChildren(){this.children=[];},
    append(...items){this.children.push(...items);},
    querySelector(){return null;}
  };
  return ui[id];
}
const document={
  getElementById:stub,
  querySelectorAll(){return[];},
  addEventListener(){}
};
const window={innerWidth:1200};
const sandbox={document,window,console,fetch:async()=>({ok:true,json:async()=>raw})};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root,'localidades-layer.js'),'utf8'),sandbox);
const api=window.GeoRefPlaces;
assert(api,'Expected localities layer');
assert.equal(api.normalize('Río Cuarto'),'rio cuarto');
const decoded=api.decode(raw);
assert(decoded.length>=3000 && decoded.length<=raw.total);
assert(decoded.some(p=>p.name==='La Plata'&&p.province==='Buenos Aires'));
assert(decoded.some(p=>p.name==='Tandil'));
async function run(){
 const proj=(lon,lat)=>[(lon+86)/42*610,(lat+56)/37*530];
 api.init({proj,W:610,H:530});
 await new Promise(resolve=>setImmediate(resolve));
 assert(ui.placesStatus.textContent.includes('GeoRef'),'Data should load');
 assert(api.searchResults('cordoba').length>0);
 assert(api.searchResults('río cuarto').some(x=>x.name==='Río Cuarto'));
 assert(api.searchResults('la plata').some(x=>x.province==='Buenos Aires'));
 assert(api.searchResults('Tandil Buenos Aires').some(x=>x.name==='Tandil'));
 const z={factor:1,cx:305,cy:265};
 const groups=api.groupPoints(decoded,z,610,530);
 assert(groups.length>60 && groups.length<decoded.length,'Clustering must reduce markers');
 assert(groups.some(g=>g.n>1),'Clusters should contain multiple localities');
 const zoomed=api.groupPoints(decoded,{factor:5,cx:305,cy:265},610,530);
 assert(zoomed.some(g=>g.n===1),'High zoom should reveal individuals');
 const context={
   save(){},restore(){},setTransform(){},beginPath(){},arc(){},fill(){},stroke(){},
   fillText(){},strokeText(){},measureText(t){return{width:t.length*6}},
 };
 const canvas={width:1220,_mapZoom:z,getBoundingClientRect(){return{left:0,top:0,width:610,height:530}}};
 api.draw(canvas,context,z);
 assert(canvas._placeHits.length>50,'The layer should draw projected markers');
 console.log('GeoRef OK:',raw.total,'source localities,',decoded.length,'visible items,',
  groups.length,'clusters at 1x; search, accent normalization and progressive zoom passed');
}
run().catch(err=>{console.error(err);process.exitCode=1;});
