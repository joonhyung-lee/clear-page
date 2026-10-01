/* A shared illustrative maze. Geometry and object IDs match every method view. */
(() => {
 const ordering=document.querySelector('#method-order .sequence-explanation'),generation=document.querySelector('#method-flow .sequence-explanation');if(!ordering||!generation)return;
 const objects=[{id:0,p:[1.2,4.7],selected:false,color:'#bcc7b6'},{id:1,p:[3,2.5],selected:true,color:'#c99773'},{id:2,p:[7,4.5],selected:true,color:'#7d9eaf'}];
 const walls=[[0,0,.12,6],[9.88,0,10,6],[0,0,10,.12],[0,5.88,10,6],[2.7,0,3.3,2],[2.7,3,3.3,6],[6.7,0,7.3,4],[6.7,5,7.3,6]];
 const route=[[1,1],[2.1,2.5],[4,2.5],[5.9,4.5],[8.1,4.5],[9,5.2]];
 const references={1:[[3,2.5],[4,2.5],[4.5,2.5],[4.5,1.2]],2:[[7,4.5],[8,4.5],[8.5,4.5],[8.5,3]]};
 const noise={1:[[3,2.5],[4.7,4.9],[2.9,.8],[5.2,3.7]],2:[[7,4.5],[6.1,2.8],[8.3,1.8],[5.9,4.9]]};
 let time=0,selectionTime=reduced.matches?1:0,selectionPlaying=!reduced.matches,view='2d',mask=false,rank=1,playing=!reduced.matches;
 const project=(p,mode)=>mode==='2d'?[36+p[0]*60,380-p[1]*57]:[44+p[0]*47+p[1]*21,345+p[0]*5-p[1]*39-(p[2]||0)*45];
 function scene(mode='2d',kind='ordering',t=0){
  const xy=p=>project(p,mode),points=ps=>ps.map(p=>xy(p).join(',')).join(' ');
  const polygon=(ps,color,cls='',opacity=1)=>`<polygon class="${cls}" points="${points(ps)}" fill="${color}" fill-opacity="${opacity}" stroke="${color}"/>`;
  const box=(p,color,ghost=false,size=.7,height=.7)=>{const a=size/2,bottom=[[-a,-a],[a,-a],[a,a],[-a,a]].map(([x,y])=>[p[0]+x,p[1]+y,0]);let out=polygon(bottom,color,ghost?'flow-ghost':'object-footprint',ghost?.15:.85);
   if(mode==='3d'){const top=bottom.map(([x,y])=>[x,y,height]);out+=polygon(top,color,ghost?'flow-ghost-top':'',ghost?.12:.6);bottom.forEach((p,i)=>{out+=`<polyline points="${points([p,top[i]])}" fill="none" stroke="${color}"/>`;});}return out;};
  let svg=polygon([[0,0],[10,0],[10,6],[0,6]],'#f4f6f0');
  for(let x=1;x<10;x++)svg+=`<polyline points="${points([[x,0],[x,6]])}" stroke="#e5e9df"/>`;
  for(let y=1;y<6;y++)svg+=`<polyline points="${points([[0,y],[10,y]])}" stroke="#e5e9df"/>`;
  walls.forEach(([a,b,c,d])=>{svg+=polygon([[a,b],[c,b],[c,d],[a,d]],'#bec8bd','maze-wall');if(mode==='3d')svg+=polygon([[a,b,.55],[c,b,.55],[c,d,.55],[a,d,.55]],'#d0d7ca','maze-wall-top');});
  if(kind!=='scene')svg+=`<polyline class="query-route" points="${points(route)}" fill="none" stroke="#768c67" stroke-width="2" stroke-dasharray="6 5"/>`;
  for(const [p,label]of [[route[0],'Start'],[route.at(-1),'Goal']]){const q=xy(p);svg+=`<circle cx="${q[0]}" cy="${q[1]}" r="6" fill="#577647"/><text x="${q[0]+9}" y="${q[1]+5}">${label}</text>`;}
  objects.forEach(o=>{
   const faded=mask&&kind==='flow'&&o.id>rank,color=faded?'#cbd0c8':o.color;
   svg+=`<g data-object="${o.id}" data-selected="${o.selected}"><title>OBJ ${o.id}: ${o.selected?'selected to clear a passage':'omitted, outside the route'}</title>`+box(o.p,color);
   if(o.selected&&kind==='ordering'&&t>=(o.id===1?.24:.60)){const q=xy(o.p);svg+=`<rect class="selection-ring" x="${q[0]-28}" y="${q[1]-27}" width="56" height="54" rx="3" fill="none" stroke="${color}" stroke-width="3"/>`;}
   const q=xy([...o.p,.8]);svg+=`<text x="${q[0]}" y="${q[1]-29}" text-anchor="middle">OBJ ${o.id}</text></g>`;
   if(!o.selected||kind!=='flow')return;
   const localTime=o.id===1?Math.min(1,t*2):Math.max(0,t*2-1);
   const path=references[o.id].map((p,i)=>p.map((v,j)=>noise[o.id][i][j]*(1-localTime)+v*localTime));
   svg+=`<polyline class="generated-path" points="${points(path)}" fill="none" stroke="${color}" stroke-width="2.5"/>`;
   path.forEach((p,i)=>{const q=xy(p);svg+=`<circle class="waypoint" cx="${q[0]}" cy="${q[1]}" r="4" fill="white" stroke="${color}"><title>OBJ ${o.id} waypoint ${i}: ${p.map(v=>v.toFixed(2)).join(', ')}</title></circle>`;});
   svg+=box(path[2],color,true)+box(path.at(-1),color,true);
  });
  if(mode==='3d')for(const [p,label]of [[[1,0,0],'X'],[[0,1,0],'Y'],[[0,0,1],'Z']]){const q=xy(p);svg+=`<polyline points="${points([[0,0,0],p])}" stroke="#71876c"/><text x="${q[0]}" y="${q[1]+18}">${label}</text>`;}
  if(kind==='ordering'){
   const progress=Math.min(1,t)* (route.length-1),index=Math.min(route.length-2,Math.floor(progress)),fraction=Math.min(1,progress-index);
   const p=route[index].map((v,j)=>v+(route[index+1][j]-v)*fraction),q=xy(p);
   svg+=`<circle class="selection-probe" cx="${q[0]}" cy="${q[1]}" r="7" fill="#577647" stroke="white" stroke-width="2"/>`;
  }
  return svg;
 }
 const controls=document.createElement('div');controls.className='illustration-controls';controls.innerHTML='<div role="group" aria-label="Generation view"><button type="button" data-illustration-view="2d" aria-pressed="true">2D map</button><button type="button" data-illustration-view="3d" aria-pressed="false">3D scene</button></div><button type="button" data-flow-toggle>Pause</button><label>Flow time <input type="range" min="0" max="1" step=".01" value="0" aria-label="Illustrative flow time"><output>0.00</output></label><button type="button" data-attention-mask aria-pressed="false">Show attention mask</button>';
 generation.querySelector('svg').after(controls);
 const attention=document.createElement('div');attention.className='illustration-attention';attention.hidden=true;attention.innerHTML='<label>Current interaction <select aria-label="Current interaction"><option value="1">OBJ 1</option><option value="2">OBJ 2</option></select></label><p></p>';generation.append(attention);
 const summary=document.createElement('div');summary.className='illustration-order-summary';summary.innerHTML='<strong>OBJ 1 → OBJ 2</strong>';ordering.querySelector('svg').after(summary);
 const distribution=document.createElementNS('http://www.w3.org/2000/svg','svg');distribution.setAttribute('viewBox','0 0 660 165');distribution.setAttribute('role','img');distribution.setAttribute('aria-label','Illustrative priority distributions');distribution.classList.add('illustration-priorities');summary.after(distribution);
 const selectionControls=document.createElement('div');selectionControls.className='illustration-controls';selectionControls.innerHTML='<button type="button" data-selection-toggle>Pause</button><output>Trace the route</output>';ordering.querySelector('svg').after(selectionControls);
 let curves='<path d="M50 110H610" stroke="#c5d1be"/>';
 for(const [id,mu,sigma]of [[1,-1,.45],[2,.8,.6]]){const color=objects[id].color;const pts=Array.from({length:121},(_,i)=>{const u=-3+i/20;return [50+(u+3)*560/6,110-65*Math.exp(-.5*((u-mu)/sigma)**2)].join(',');}).join(' ');curves+=`<polyline points="${pts}" stroke="${color}" fill="none" stroke-width="2"/><circle cx="${50+(mu+3)*560/6}" cy="45" r="4" fill="${color}"/><text x="${50+(mu+3)*560/6}" y="25" text-anchor="middle">OBJ ${id} · score ${mu}</text>`;}
 for(const u of [-3,-2,-1,0,1,2,3])curves+=`<text x="${50+(u+3)*560/6}" y="130" text-anchor="middle">${u}</text>`;
 curves+='<text x="330" y="157" text-anchor="middle">Lower sampled score → earlier interaction</text>';distribution.innerHTML=curves;
 ordering.querySelector('figcaption').hidden=true;generation.querySelector('figcaption').hidden=true;
 ordering.setAttribute('aria-label','Illustrative object selection and priority distributions');generation.setAttribute('aria-label','Illustrative rank-causal object generation');

 function draw(){const a=ordering.querySelector('svg'),b=generation.querySelector('svg');for(const svg of [a,b])svg.setAttribute('viewBox','0 0 660 410');a.innerHTML=scene('2d','ordering',selectionTime);ordering.dataset.selectionTime=selectionTime.toFixed(2);selectionControls.querySelector('button').textContent=selectionPlaying?'Pause':'Play';selectionControls.querySelector('output').textContent=selectionTime<.24?'Trace the route':selectionTime<.60?'Select OBJ 1':'Select OBJ 2';b.innerHTML=scene(view,'flow',time);generation.dataset.flowTime=time.toFixed(2);generation.dataset.view=view;controls.querySelector('output').textContent=time.toFixed(2);controls.querySelector('input').value=time;controls.querySelector('[data-flow-toggle]').textContent=playing?'Pause':'Play';attention.querySelector('p').textContent=rank===1?'OBJ 1 reads the scene context. OBJ 2 is a later interaction and is masked.':'OBJ 2 reads the scene context and OBJ 1’s generated reference.';}
 controls.querySelector('input').oninput=e=>{time=+e.target.value;playing=false;draw();};controls.querySelector('[data-flow-toggle]').onclick=()=>{playing=!playing;draw();};
 controls.querySelectorAll('[data-illustration-view]').forEach(button=>button.onclick=()=>{view=button.dataset.illustrationView;controls.querySelectorAll('[data-illustration-view]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));draw();});
 controls.querySelector('[data-attention-mask]').onclick=e=>{mask=!mask;e.currentTarget.setAttribute('aria-pressed',String(mask));attention.hidden=!mask;draw();};attention.querySelector('select').onchange=e=>{rank=+e.target.value;draw();};
 selectionControls.querySelector('button').onclick=()=>{selectionPlaying=!selectionPlaying;draw();};
 let near=false,last=0;const visible=new Set(),observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting)visible.add(entry.target);else visible.delete(entry.target);}near=visible.size>0;last=0;});observer.observe(ordering);observer.observe(generation);
 function tick(now){if(near&&!document.hidden&&(playing||selectionPlaying)){const dt=last?Math.min(now-last,100):0;if(playing)time=(time+dt/6500)%1.18;if(selectionPlaying)selectionTime=(selectionTime+dt/6000)%1.2;const saved=time;time=Math.min(time,1);draw();time=saved;}last=now;requestAnimationFrame(tick);}requestAnimationFrame(tick);
 window.CLEAR_METHOD_SCHEMATIC={objects,walls,route,scene,createPreview(kind){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 660 410');svg.setAttribute('aria-label','Shared illustrative maze');svg.setAttribute('role','img');svg.dataset.methodPreview=kind;let active=false,start=0;new IntersectionObserver(entries=>{active=entries.at(-1).isIntersecting;}).observe(svg);function update(now){if(active&&!document.hidden){if(!start)start=now;const t=reduced.matches?1:Math.min(1,((now-start)/6500)%1.18);svg.innerHTML=scene('2d',kind,t);svg.dataset.flowTime=t.toFixed(3);}requestAnimationFrame(update);}svg.innerHTML=scene('2d',kind,0);requestAnimationFrame(update);return svg;}};
 draw();
})();
