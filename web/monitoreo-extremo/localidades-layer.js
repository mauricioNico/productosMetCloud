/* Capa de localidades GeoRef para Monitoreo Extremo FAA.
 * Datos locales versionados en ./localidades-georef.json (lat/lon oficiales).
 * Las agrupaciones son visuales; nunca alteran la cartografía ni el campo meteorológico.
 */
(function () {
  'use strict';
  const state={items:[],filtered:[],selected:null,visible:true,labels:true,proj:null,W:610,H:530,ready:false};
  const $=id=>document.getElementById(id);
  const normalize=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('es').trim();
  const canvases=()=>document.querySelectorAll('canvas.mapcanvas');
  const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));

  function decode(json){
    if(!json || !Array.isArray(json.localidades) || json.localidades.length<3000)
      throw Error('Listado GeoRef incompleto.');
    const seen=new Map(),out=[];
    for(const row of json.localidades){
      if(!Array.isArray(row)||row.length<5)continue;
      const [id,name,province,lon,lat,category]=row;
      if(!name||!province||!Number.isFinite(lon)||!Number.isFinite(lat))continue;
      if(lon<-86||lon>-44||lat<-56||lat>-19)continue;
      const item={id:String(id),name:String(name),province:String(province),
        lon,lat,category:String(category||'')};
      item.norm=normalize(item.name);item.regionNorm=normalize(item.province);
      // GeoRef sometimes includes an "Entidad" near the parent locality: keep the official
      // original in JSON, but avoid rendering two identical labels at practically the same site.
      const key=item.norm+'|'+item.regionNorm;
      const earlier=seen.get(key)||[];
      const overlapping=earlier.find(other=>
        Math.abs(other.lon-lon)<.025&&Math.abs(other.lat-lat)<.025&&
        (item.category==='Entidad'||other.category==='Entidad'));
      if(overlapping){
        if(overlapping.category==='Entidad'&&item.category!=='Entidad'){
          const index=out.indexOf(overlapping);
          if(index>=0)out[index]=item;
          earlier.splice(earlier.indexOf(overlapping),1,item);
        }
        continue;
      }
      out.push(item);earlier.push(item);seen.set(key,earlier);
    }
    if(out.length<3000)throw Error('El catálogo GeoRef carece de suficientes localidades.');
    return out;
  }

  function groupPoints(points,z,W,H){
    const spacing=z.factor<1.8?42:z.factor<3.3?29:z.factor<5?20:13;
    const groups=new Map();
    for(const item of points){
      const xy=state.proj(item.lon,item.lat);
      const x=W/2+(xy[0]-z.cx)*z.factor,y=H/2+(xy[1]-z.cy)*z.factor;
      if(x<-24||y<-24||x>W+24||y>H+24)continue;
      const key=Math.floor(x/spacing)+':'+Math.floor(y/spacing);
      let group=groups.get(key);
      if(!group){group={x:0,y:0,n:0,items:[]};groups.set(key,group);}
      group.x+=x;group.y+=y;group.n++;group.items.push(item);
    }
    return [...groups.values()].map(g=>({x:g.x/g.n,y:g.y/g.n,n:g.n,items:g.items}));
  }

  function draw(canvas,ctx,z){
    canvas._placeHits=[];
    if(!state.ready||!state.visible||!state.items.length||!state.proj)return;
    const W=state.W,H=state.H;
    const groups=[]; // Solo se dibuja la localidad elegida en el buscador.
    const ratio=canvas.width/W;
    ctx.save();ctx.setTransform(ratio,0,0,ratio,0,0);
    ctx.textAlign='center';ctx.textBaseline='middle';
    const singles=[];
    for(const group of groups){
      const {x,y,n}=group,cluster=n>1;
      const radius=cluster?Math.min(17,Math.max(10,8+Math.sqrt(n)*1.35)):3.5;
      ctx.beginPath();ctx.arc(x,y,radius,0,2*Math.PI);
      ctx.fillStyle=cluster?'rgba(0,48,113,.84)':'#123f72';ctx.fill();
      ctx.lineWidth=cluster?1.5:1.2;ctx.strokeStyle='#ffffff';ctx.stroke();
      if(cluster){
        ctx.fillStyle='#fff';ctx.font='bold 10px system-ui';
        ctx.fillText(n>999?'999+':String(n),x,y+.2);
      }else singles.push(group);
      canvas._placeHits.push({x,y,r:radius+5,group});
    }
    if(false && state.labels && z.factor>=1.7){
      // Label budget rises with zoom; bbox avoidance keeps the map legible.
      const limit=z.factor<2.5?14:z.factor<3.8?32:z.factor<5?65:105;
      const selected=state.selected;
      const priority=new Set(['buenos aires','cordoba','rosario','la plata','mar del plata',
        'bahia blanca','mendoza','salta','san miguel de tucuman','san juan',
        'neuquen','parana','santa fe','posadas','resistencia','corrientes',
        'rio cuarto','tandil','ushuaia','comodoro rivadavia']);
      singles.sort((a,b)=>{
        const aa=a.items[0],bb=b.items[0];
        const ap=(priority.has(aa.norm)?10:0)+(selected?.id===aa.id?100:0);
        const bp=(priority.has(bb.norm)?10:0)+(selected?.id===bb.id?100:0);
        return bp-ap || aa.name.localeCompare(bb.name,'es');
      });
      const occupied=[];let printed=0;ctx.textAlign='left';ctx.textBaseline='middle';
      ctx.font='bold 10px system-ui';ctx.lineJoin='round';
      for(const group of singles){
        if(printed>=limit)break;
        const item=group.items[0],text=item.name;
        const x=group.x+7,y=group.y-9;
        const width=ctx.measureText(text).width+5;
        if(x+width>W-3||x<2||y<10||y>H-10)continue;
        if(occupied.some(b=>x<b.x+b.w && x+width>b.x && y-7<b.y+b.h && y+7>b.y))continue;
        occupied.push({x,y:y-7,w:width,h:14});
        ctx.strokeStyle='rgba(255,255,255,.97)';ctx.lineWidth=3.3;
        ctx.strokeText(text,x,y);ctx.fillStyle='#193955';ctx.fillText(text,x,y);printed++;
      }
    }
    if(state.selected){
      const pos=state.proj(state.selected.lon,state.selected.lat);
      const x=W/2+(pos[0]-z.cx)*z.factor,y=H/2+(pos[1]-z.cy)*z.factor;
      if(x>=-15&&x<=W+15&&y>=-15&&y<=H+15){
        ctx.font='bold 12px system-ui';ctx.textAlign='left';ctx.textBaseline='middle';
        const label=state.selected.name+' · '+state.selected.province;
        const labelX=Math.min(W-ctx.measureText(label).width-12,Math.max(12,x+13));
        const labelY=Math.max(15,Math.min(H-15,y-12));
        ctx.lineWidth=4;ctx.strokeStyle='#fff';ctx.strokeText(label,labelX,labelY);
        ctx.fillStyle='#123f72';ctx.fillText(label,labelX,labelY);
        ctx.beginPath();ctx.arc(x,y,8,0,2*Math.PI);
        ctx.strokeStyle='#ffffff';ctx.lineWidth=4;ctx.stroke();
        ctx.beginPath();ctx.arc(x,y,7,0,2*Math.PI);
        ctx.strokeStyle='#f33442';ctx.lineWidth=2.8;ctx.stroke();
        ctx.beginPath();ctx.arc(x,y,2.6,0,2*Math.PI);
        ctx.fillStyle='#f33442';ctx.fill();
      }
    }
    ctx.restore();
  }

  function hit(canvas,event){
    if(!state.ready||!state.visible)return null;
    const rect=canvas.getBoundingClientRect();
    const x=(event.clientX-rect.left)*state.W/rect.width,
          y=(event.clientY-rect.top)*state.H/rect.height;
    const hits=canvas._placeHits||[];
    let closest=null,distance=Infinity;
    for(const marker of hits){
      const d=Math.hypot(x-marker.x,y-marker.y);
      if(d<=marker.r && d<distance){closest=marker;distance=d;}
    }
    return closest;
  }

  function hover(canvas,event){
    if(canvas._mapZoom?.drag || !state.visible)return;
    const h=hit(canvas,event);if(!h)return;
    const tip=$('tip');if(!tip)return;
    tip.style.display='block';
    tip.style.left=Math.min(window.innerWidth-260,event.clientX+14)+'px';
    tip.style.top=Math.max(10,event.clientY-55)+'px';
    const g=h.group;
    tip.textContent=g.n>1?(g.n+' localidades agrupadas. Hacé clic para acercar.'):
      (g.items[0].name+' · '+g.items[0].province+'\nLocalidad GeoRef · '+g.items[0].lat.toFixed(3)+'° / '+g.items[0].lon.toFixed(3)+'°');
  }

  function choose(item){
    state.selected=item;
    const input=$('placeSearch');
    if(input)input.value=item.name+' — '+item.province;
    const clear=$('placeClear');if(clear)clear.disabled=false;
    closeSuggestions();
    for(const canvas of canvases()){
      const z=canvas._mapZoom;
      if(z?.focus)z.focus(item.lon,item.lat,Math.max(3.3,z.factor));
    }
  }

  function click(canvas,e){
    if(canvas._suppressPlaceClick){canvas._suppressPlaceClick=false;return;}
    const h=hit(canvas,e);if(!h)return;
    if(h.group.n===1){choose(h.group.items[0]);return;}
    const z=canvas._mapZoom;
    if(!z?.focus)return;
    const center=h.group.items.reduce((xy,item)=>{
      const p=state.proj(item.lon,item.lat);xy[0]+=p[0];xy[1]+=p[1];return xy;
    },[0,0]);
    z.focusProjected(center[0]/h.group.n,center[1]/h.group.n,Math.min(6,z.factor*1.8));
  }

  function renderAll(){
    for(const canvas of canvases())canvas._mapZoom?.render?.();
  }
  function focusCurrent(canvas){
    if(state.selected&&canvas._mapZoom?.focus)
      canvas._mapZoom.focus(state.selected.lon,state.selected.lat,3.3);
  }

  function closeSuggestions(){
    const results=$('placeSuggestions');if(results){results.replaceChildren();results.hidden=true;}
    const input=$('placeSearch');if(input)input.setAttribute('aria-expanded','false');
    state.filtered=[];
  }
  function searchResults(query){
    const key=normalize(query);
    if(key.length<2)return [];
    const tokens=key.replace(/[—–,]/g,' ').split(/\s+/).filter(Boolean);
    const matches=state.items.filter(item=>tokens.every(token=>(item.norm+' '+item.regionNorm).includes(token)));
    const score=item=>(item.norm===key?0:item.norm.startsWith(key)?1:2)+
      (item.category==='Entidad'?0.25:0);
    matches.sort((a,b)=>score(a)-score(b)||
      a.name.localeCompare(b.name,'es')||a.province.localeCompare(b.province,'es'));
    return matches.slice(0,9);
  }
  function suggest(query){
    const results=$('placeSuggestions'),input=$('placeSearch');
    if(!results||!input)return;
    results.replaceChildren();
    const matches=searchResults(query);state.filtered=matches;
    if(!matches.length){
      if(normalize(query).length>=2){
        const empty=document.createElement('div');empty.className='placeempty';
        empty.textContent=state.ready?'No se encontraron localidades':'Cargando localidades…';
        results.append(empty);results.hidden=false;
      }else closeSuggestions();
      return;
    }
    for(const item of matches){
      const button=document.createElement('button');
      button.type='button';button.className='placeoption';button.setAttribute('role','option');
      const name=document.createElement('strong');name.textContent=item.name;
      const province=document.createElement('small');province.textContent=item.province;
      button.append(name,province);
      button.addEventListener('click',()=>choose(item));
      results.append(button);
    }
    results.hidden=false;input.setAttribute('aria-expanded','true');
  }

  function init(options){
    state.proj=options.proj;state.W=options.W;state.H=options.H;
    $('showPlaces')?.addEventListener('change',e=>{state.visible=e.target.checked;renderAll();});
    $('showPlaceLabels')?.addEventListener('change',e=>{state.labels=e.target.checked;renderAll();});
    const input=$('placeSearch'),clear=$('placeClear');
    input?.addEventListener('input',e=>suggest(e.target.value));
    input?.addEventListener('keydown',e=>{
      if(e.key==='Escape'){closeSuggestions();return;}
      if(e.key==='Enter'&&state.filtered.length){e.preventDefault();choose(state.filtered[0]);}
      if(e.key==='ArrowDown'&&state.filtered.length){
        e.preventDefault();$('placeSuggestions')?.querySelector('button')?.focus();
      }
    });
    clear?.addEventListener('click',()=>{
      state.selected=null;input.value='';closeSuggestions();clear.disabled=true;
      renderAll();
    });
    document.addEventListener('click',e=>{
      if(!e.target.closest?.('.placefinder'))closeSuggestions();
    });
    const status=$('placesStatus');
    if(status)status.textContent='Cargando base GeoRef…';
    fetch('./localidades-georef.json',{cache:'force-cache'})
      .then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();})
      .then(json=>{
        state.items=decode(json);state.ready=true;
        if(status)status.textContent=state.items.length.toLocaleString('es-AR')+
          ' localidades GeoRef · '+new Set(state.items.map(p=>p.province)).size+' jurisdicciones';
        renderAll();
      })
      .catch(err=>{
        if(status)status.textContent='No se pudo cargar la capa de localidades.';
        console.warn('GeoRef (visor): '+err.message);
      });
  }

  window.GeoRefPlaces={init,draw,hover,click,renderAll,focusCurrent,normalize,decode,groupPoints,searchResults};
})();
