/* Full execution context, local forecasts, and time-aligned candidate anchors. */
(() => {
 const root=document.querySelector('#mpc-process');if(!root)return;
 const play=root.querySelector('#mpc-process-play'),slider=root.querySelector('#mpc-process-update'),panels=[...root.querySelectorAll('[data-process]')];
 let data=null,loading=false,visible=false,playing=!reduced.matches,elapsed=0,duration=0,last=0,frame=0,anchor=1,rate=2,retainedOnly=false,axisEnd=0,coordinateBounds=[],detailAxis=0,inspectCandidate=-1;
 const ghostCache=new Map(),height=700;
 const mainX=t=>62+t/axisEnd*470;
 const mainY=(v,a)=>378+a*134-(v-coordinateBounds[a][0])/(coordinateBounds[a][1]-coordinateBounds[a][0])*96;
 const component=(p,o,r,a)=>a===2?p[2]-o[2]:a===0?(p[0]-o[0])*r.direction[0]+(p[1]-o[1])*r.direction[1]:-(p[0]-o[0])*r.direction[1]+(p[1]-o[1])*r.direction[0];
 function ghostLayer(name,r,hand){
  const key=name+hand+retainedOnly;if(ghostCache.has(key))return ghostCache.get(key);
  const layer=document.createElement('canvas');layer.width=560;layer.height=height;const ctx=layer.getContext('2d'),initial=r.observed[0].slice(1+hand*3,4+hand*3);let count=0;
  ctx.strokeStyle='#87918a';ctx.lineWidth=.7;
  for(const update of r.updates)for(let n=0;n<r.population;n++){
   if(retainedOnly&&!update.elites.includes(n))continue;count++;
   for(let a=0;a<3;a++){ctx.beginPath();update.paths[n].forEach((p,j)=>{const x=mainX(update.time-r.updates[0].time+r.futureTimes[j]),y=mainY(component(p[hand],initial,r,a),a);j?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();}
  }
  const result={layer,count};ghostCache.set(key,result);return result;
 }
 const format=n=>String(Number(n.toPrecision(3)));
 function at(rows,t){let lo=0,hi=rows.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(rows[mid][0]<=t)lo=mid;else hi=mid-1;}const a=rows[lo],b=rows[Math.min(lo+1,rows.length-1)],u=b[0]>a[0]?Math.max(0,Math.min(1,(t-a[0])/(b[0]-a[0]))):0;return a.map((v,i)=>i?v+u*(b[i]-v):t);}
 function render(){
  if(!data)return;play.textContent=playing?'Pause':'Play';slider.value=elapsed/duration;root.dataset.elapsed=elapsed.toFixed(3);root.dataset.candidateView=retainedOnly?'retained':'all';root.querySelector('#mpc-process-counter').textContent=elapsed.toFixed(1)+' / '+duration.toFixed(1)+' s';
  for(const panel of panels){
   const name=panel.dataset.process,r=data[name],start=r.updates[0].time,end=r.observed.at(-1)[0],time=Math.min(start+elapsed,end);let idx=0;
   while(idx+1<r.updates.length&&r.updates[idx+1].time<=time)idx++;
   const u=r.updates[idx],actual=at(r.observed,time),selected=u.paths[u.applied],color=name==='optimized'?'#557e5a':'#aa6b57',dark=name==='optimized'?'#214b30':'#703c2e';
   const along=(p,o)=>((p[0]-o[0])*r.direction[0]+(p[1]-o[1])*r.direction[1]),across=(p,o)=>((p[0]-o[0])*-r.direction[1]+(p[1]-o[1])*r.direction[0]);
   const anchorIndices=[0,r.horizon/2,r.horizon].map(t=>r.futureTimes.reduce((best,v,j)=>Math.abs(v-t)<Math.abs(r.futureTimes[best]-t)?j:best,0));
   const chosen=anchorIndices[anchor],letter='ABC'[anchor],windowStart=u.time-start,windowEnd=windowStart+r.horizon;
   panel.dataset.update=String(u.sourceIndex);panel.dataset.time=time.toFixed(3);panel.dataset.snapshot=u.time.toFixed(3);panel.dataset.horizon=String(r.horizon);panel.dataset.candidateCount=String(r.population);panel.dataset.visibleCandidates=String(retainedOnly?u.elites.length:r.population);panel.dataset.retained=u.elites.join(',');panel.dataset.complete=String(elapsed>=end-start);
   const completion=panel.querySelector('.mpc-recording-status');completion.textContent=elapsed>=end-start?'Recording complete · '+(end-start).toFixed(1)+' s':'Recorded duration · '+(end-start).toFixed(1)+' s';
   for(let hand=0;hand<2;hand++){
    const c=panel.querySelectorAll('canvas')[hand],ctx=c.getContext('2d');if(c.height!==height)c.height=height;
    ctx.clearRect(0,0,560,height);ctx.fillStyle='#fbfcfa';ctx.fillRect(0,0,560,height);ctx.font=Math.max(12,10*560/(c.clientWidth||560))+'px Arial';
    function line(points,col,width=1,dash=[]){if(!points.length)return;ctx.beginPath();ctx.strokeStyle=col;ctx.lineWidth=width;ctx.setLineDash(dash);points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();ctx.setLineDash([]);}
    function dot(p,radius,fill,stroke=color){ctx.beginPath();ctx.arc(...p,radius,0,Math.PI*2);ctx.fillStyle=fill;ctx.fill();ctx.strokeStyle=stroke;ctx.lineWidth=1.5;ctx.stroke();}
    const initial=r.observed[0].slice(1+hand*3,4+hand*3),ghost=ghostLayer(name,r,hand);
    c.dataset.recordedStart='0';c.dataset.recordedEnd=String(end-start);c.dataset.recordedPoints=String(r.observed.length);c.dataset.observedUntil=String(time-start);c.dataset.palm=String(hand);c.dataset.axisStart='0';c.dataset.axisEnd=String(axisEnd);c.dataset.coordinateBounds=JSON.stringify(coordinateBounds);c.dataset.horizon=String(r.horizon);c.dataset.windowStart=String(windowStart);c.dataset.windowEnd=String(windowEnd);c.dataset.ghostTrajectories=String(ghost.count);c.dataset.coordinates='X,Y,Z';c.dataset.inspectedCandidate=String(inspectCandidate);
    ctx.fillStyle='#435740';ctx.fillText((hand?'Right':'Left')+' palm · XYZ displacement',16,24);
    ctx.fillStyle='#788174';ctx.fillText((retainedOnly?'Retained forecasts · ':'All saved forecasts · ')+ghost.count+' trajectories',16,44);
    ctx.globalAlpha=.27;ctx.drawImage(ghost.layer,0,0);ctx.globalAlpha=1;
    const forecast=[82,62,230,168],spatial=[330,62,204,168];
    for(let a=0;a<3;a++){
     const [lo,hi]=coordinateBounds[a],y=v=>mainY(v,a),bottom=378+a*134;
     ctx.fillStyle='#465340';ctx.fillText(['X · Forward (m)','Y · Lateral (m)','Z · Vertical (m)'][a],16,bottom-109);
     for(const v of [lo,(lo+hi)/2,hi]){line([[62,y(v)],[532,y(v)]],'#e5eae0');ctx.fillStyle='#74806d';ctx.fillText(format(v),12,y(v)+4);}
     for(const t of [0,10,20,30,40,axisEnd]){line([[mainX(t),bottom-96],[mainX(t),bottom]],'#eff2eb');if(a===2){ctx.fillStyle='#74806d';ctx.fillText(t+' s',mainX(t)-10,bottom+19);}}
     line(r.observed.map(row=>[mainX(row[0]-start),y(component(row.slice(1+hand*3,4+hand*3),initial,r,a))]),'rgba(130,136,134,.4)',1.8);
     const history=r.observed.filter(row=>row[0]<=time).map(row=>[mainX(row[0]-start),y(component(row.slice(1+hand*3,4+hand*3),initial,r,a))]);history.push([mainX(time-start),y(component(actual.slice(1+hand*3,4+hand*3),initial,r,a))]);line(history,'#202421',2.2);
     for(let n=0;n<r.population;n++){if(retainedOnly&&!u.elites.includes(n))continue;line(u.paths[n].map((p,j)=>[mainX(windowStart+r.futureTimes[j]),y(component(p[hand],initial,r,a))]),u.elites.includes(n)?color:'#aab5a4',u.elites.includes(n)?1.3:.7);}
     line(selected.map((p,j)=>[mainX(windowStart+r.futureTimes[j]),y(component(p[hand],initial,r,a))]),dark,1.8);
     if(inspectCandidate>=0)line(u.paths[inspectCandidate].map((p,j)=>[mainX(windowStart+r.futureTimes[j]),y(component(p[hand],initial,r,a))]),'#476d9c',2.6);
     line([[mainX(end-start),bottom-96],[mainX(end-start),bottom]],'#82927b',1,[3,4]);
     if(elapsed>=end-start)dot(history.at(-1),5,'#fff',dark);else dot(history.at(-1),3.5,'#202421','#202421');
     if(a===0){ctx.fillStyle='#202421';ctx.fillText(elapsed>=end-start?'End':'Now',Math.max(63,history.at(-1)[0]-27),history.at(-1)[1]+17);}
     const values=u.paths.flatMap(path=>path.map(p=>component(p[hand],initial,r,a))),low=Math.min(...values),high=Math.max(...values),box=[mainX(windowStart),y(high)-3,Math.max(4,mainX(windowEnd)-mainX(windowStart)),Math.max(6,y(low)-y(high)+6)];
     ctx.strokeStyle=color;ctx.lineWidth=1;ctx.setLineDash([3,4]);ctx.strokeRect(...box);ctx.setLineDash([]);
     const mainAnchor=[mainX(windowStart+r.futureTimes[chosen]),y(component(selected[chosen][hand],initial,r,a))];dot(mainAnchor,3.5,'#fff',dark);ctx.fillStyle=dark;ctx.fillText(letter,mainAnchor[0]+6,mainAnchor[1]-5);
     if(a===detailAxis){line([[box[0],box[1]],[forecast[0],forecast[1]+forecast[3]]],color,.8,[4,4]);line([[box[0]+box[2],box[1]],[forecast[0]+forecast[2],forecast[1]+forecast[3]]],color,.8,[4,4]);}
    }
    ctx.fillStyle='#6c7866';ctx.fillText('Full execution time · fixed axes',16,689);
    for(const rect of [forecast,spatial]){ctx.fillStyle='#fff';ctx.fillRect(...rect);ctx.strokeStyle='#bfcab8';ctx.lineWidth=1;ctx.strokeRect(...rect);}
    // Detail magnifies the short window and removes the common nominal motion.
    const deviations=u.paths.slice(0,r.population).map(path=>path.map((p,j)=>1000*component(p[hand],selected[j][hand],r,detailAxis))),extent=Math.max(.1,...deviations.flat().map(Math.abs)),step=10**Math.floor(Math.log10(extent)),limit=Math.ceil(extent/step)*step;
    const localX=t=>forecast[0]+35+t/r.horizon*180,localY=v=>forecast[1]+89-v/limit*39;
    ctx.fillStyle='#475b42';ctx.fillText('XYZ'[detailAxis]+' forecast '+windowStart.toFixed(1)+'–'+windowEnd.toFixed(1)+' s',forecast[0]+8,forecast[1]+18);
    for(const v of [-limit,0,limit]){line([[localX(0),localY(v)],[localX(r.horizon),localY(v)]],'#eef1e9');ctx.fillStyle='#77816e';ctx.fillText(format(v),forecast[0]+3,localY(v)+4);}
    deviations.forEach((vs,n)=>{if(retainedOnly&&!u.elites.includes(n))return;line(vs.map((v,j)=>[localX(r.futureTimes[j]),localY(v)]),u.elites.includes(n)?color:'#b9c5b0',u.elites.includes(n)?2:.9);});line([[localX(0),localY(0)],[localX(r.horizon),localY(0)]],dark,2.5);
    if(inspectCandidate>=0)line(deviations[inspectCandidate].map((v,j)=>[localX(r.futureTimes[j]),localY(v)]),'#476d9c',2.4);
    anchorIndices.forEach((j,k)=>{const p=[localX(r.futureTimes[j]),localY(0)];dot(p,k===anchor?5:3.5,'#fff',dark);ctx.fillStyle=dark;ctx.fillText('ABC'[k],p[0]-4,p[1]-10);ctx.fillStyle='#6a7862';ctx.fillText((windowStart+r.futureTimes[j]).toFixed(1),p[0]-9,forecast[1]+145);});
    ctx.fillStyle='#6c7866';ctx.fillText('Deviation from nominal · mm',forecast[0]+8,forecast[1]+163);
    const center=selected[chosen][hand],points=u.paths.slice(0,r.population).map(path=>[1000*along(path[chosen][hand],center),1000*across(path[chosen][hand],center)]),spread=Math.max(.1,...points.flat().map(Math.abs)),detailStep=10**Math.floor(Math.log10(spread)),detailLimit=Math.ceil(spread/detailStep)*detailStep;
    const px=v=>spatial[0]+102+v/detailLimit*61,py=v=>spatial[1]+88-v/detailLimit*38;
    line([[localX(r.futureTimes[chosen]),localY(0)],[spatial[0],py(0)]],color,1,[3,3]);
    ctx.fillStyle='#fff';ctx.fillRect(spatial[0]+1,spatial[1]+1,spatial[2]-2,spatial[3]-2);
    ctx.fillStyle=dark;ctx.fillText(letter+' · '+(windowStart+r.futureTimes[chosen]).toFixed(1)+' s · XY slice',spatial[0]+9,spatial[1]+18);
    ctx.fillStyle='#77826f';ctx.fillText('Same time across paths',spatial[0]+9,spatial[1]+36);
    line([[px(-detailLimit),py(0)],[px(detailLimit),py(0)]],'#e8eee2');line([[px(0),py(-detailLimit)],[px(0),py(detailLimit)]],'#e8eee2');
    points.forEach((p,n)=>{if(retainedOnly&&!u.elites.includes(n))return;dot([px(p[0]),py(p[1])],u.elites.includes(n)?3.8:2.1,u.elites.includes(n)?color:'#c0cbb8',u.elites.includes(n)?color:'#c0cbb8');});dot([px(0),py(0)],5,'#fff',dark);if(inspectCandidate>=0)dot([px(points[inspectCandidate][0]),py(points[inspectCandidate][1])],5,'#476d9c','#476d9c');
    ctx.fillStyle=dark;ctx.fillText(r.executionPreview?'○ Applied mean command':'○ Applied candidate #'+(u.applied+1),spatial[0]+8,spatial[1]+143);ctx.fillStyle='#6c7866';ctx.fillText('XY scale ±'+format(detailLimit)+' mm',spatial[0]+8,spatial[1]+162);
    c.dataset.detailAxis=String(detailAxis);c.dataset.anchor=String(anchor);c.dataset.anchorLetter=letter;c.dataset.anchorTime=String(windowStart+r.futureTimes[chosen]);c.dataset.anchorOffset=String(r.futureTimes[chosen]);c.dataset.detailLimit=String(detailLimit);c.dataset.residualLimit=String(limit);c.dataset.applied=String(u.applied);c._anchorPixels=anchorIndices.map(j=>[localX(r.futureTimes[j]),localY(0)]);
   }
   const readout=[`${r.population} trajectories → ${u.elites.length} retained → ${r.executionPreview?'elite-mean command':'candidate #'+(u.applied+1)}`,
    `Update at ${windowStart.toFixed(1)} s · retained IDs ${u.elites.map(i=>'#'+(i+1)).join(', ')}`];
   panel.querySelector('.mpc-process-readout').replaceChildren(...readout.map(text=>{const p=document.createElement('p');p.textContent=text;return p;}));
  }
 }
 function tick(now){frame=0;if(!visible||!playing||!data||document.hidden)return;if(last)elapsed=Math.min(duration,elapsed+rate*(now-last)/1000);last=now;if(elapsed>=duration)playing=false;render();if(playing)frame=requestAnimationFrame(tick);}
 function schedule(){if(!frame&&visible&&playing&&data&&!document.hidden){last=0;frame=requestAnimationFrame(tick);}}
 async function initialize(){
  if(data||loading)return;loading=true;const status=root.querySelector('.mpc-process-loading');status.textContent='Preparing recorded execution…';
  try{await loadScript('assets/mpc-process-data.js',()=>!!window.CLEAR_MPC_PROCESS);data=window.CLEAR_MPC_PROCESS;
   duration=Math.max(...Object.values(data).map(r=>r.observed.at(-1)[0]-r.updates[0].time));axisEnd=Math.ceil((duration+Math.max(...Object.values(data).map(r=>r.horizon)))/5)*5;
   const extrema=Array.from({length:3},()=>[0,0]);
   for(const r of Object.values(data)){
    const direction=r.reference.at(-1).slice(0,2).map((v,i)=>v-r.reference[0][i]),length=Math.hypot(...direction)||1;r.direction=direction.map(v=>v/length);
    for(let hand=0;hand<2;hand++){
     const initial=r.observed[0].slice(1+hand*3,4+hand*3);
     const include=p=>{for(let a=0;a<3;a++){const v=component(p,initial,r,a);extrema[a][0]=Math.min(extrema[a][0],v);extrema[a][1]=Math.max(extrema[a][1],v);}};
     for(const row of r.observed)include(row.slice(1+hand*3,4+hand*3));
     for(const u of r.updates)for(const path of u.paths)for(const p of path)include(p[hand]);
    }
   }
   coordinateBounds=extrema.map(([lo,hi])=>{const step=10**Math.floor(Math.log10(Math.max(.01,hi-lo)))/2;return [Math.floor(lo/step)*step-step,Math.ceil(hi/step)*step+step];});
   status.hidden=true;root.querySelector('.mpc-process-content').hidden=false;render();schedule();
  }catch{status.textContent='Optimization replay is taking longer to load. ';const b=document.createElement('button');b.textContent='Retry replay';b.onclick=initialize;status.append(b);}finally{loading=false;}
 }
 new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible){initialize();schedule();}else{cancelAnimationFrame(frame);frame=0;last=0;}},{rootMargin:'120px'}).observe(root);
 function inspectAnchor(value){anchor=value;playing=false;root.querySelectorAll('button[data-anchor]').forEach(b=>b.setAttribute('aria-pressed',String(+b.dataset.anchor===anchor)));render();}
 play.onclick=()=>{playing=!playing;if(playing&&elapsed>=duration)elapsed=0;render();schedule();};root.querySelector('#mpc-process-replay').onclick=()=>{elapsed=0;playing=true;render();schedule();};slider.oninput=()=>{elapsed=+slider.value*duration;render();};
 root.querySelectorAll('canvas').forEach(canvas=>canvas.addEventListener('click',event=>{const rect=canvas.getBoundingClientRect(),x=(event.clientX-rect.left)*560/rect.width,y=(event.clientY-rect.top)*height/rect.height;let best=0,distance=Infinity;for(const[i,p]of(canvas._anchorPixels||[]).entries()){const delta=Math.hypot(x-p[0],y-p[1]);if(delta<distance){best=i;distance=delta;}}if(distance<25)inspectAnchor(best);}));
 root.querySelectorAll('button[data-anchor]').forEach(button=>button.onclick=()=>inspectAnchor(Number(button.dataset.anchor)));
 root.querySelectorAll('[data-candidates]').forEach(button=>button.onclick=()=>{retainedOnly=button.dataset.candidates==='retained';if(retainedOnly){inspectCandidate=-1;root.querySelector('#mpc-candidate-inspect').value='-1';}playing=false;root.querySelectorAll('[data-candidates]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();});
 root.querySelectorAll('button[data-detail-axis]').forEach(button=>button.onclick=()=>{detailAxis=Number(button.dataset.detailAxis);playing=false;root.querySelectorAll('button[data-detail-axis]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();});
 root.querySelector('#mpc-candidate-inspect').onchange=e=>{inspectCandidate=Number(e.target.value);playing=false;if(inspectCandidate>=0){retainedOnly=false;root.querySelectorAll('[data-candidates]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.candidates==='all')));}render();};
 root.querySelector('#mpc-process-speed').onchange=e=>{rate=Number(e.target.value);last=0;};new ResizeObserver(()=>{if(data)render();}).observe(root);
 document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;last=0;}else schedule();});reduced.addEventListener('change',()=>{if(reduced.matches){playing=false;render();}});
})();
