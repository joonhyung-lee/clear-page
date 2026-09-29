/* Continuous recorded execution. Predictions remain distinct from observations. */
(() => {
 const root=document.querySelector('#mpc-process');if(!root)return;
 const play=root.querySelector('#mpc-process-play'),slider=root.querySelector('#mpc-process-update');
 let data=null,loading=false,visible=false,playing=!reduced.matches,elapsed=0,duration=0,last=0,frame=0,anchor=1,rate=2;
 const panels=[...root.querySelectorAll('[data-process]')];
 function at(rows,t){let lo=0,hi=rows.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(rows[mid][0]<=t)lo=mid;else hi=mid-1;}const a=rows[lo],b=rows[Math.min(lo+1,rows.length-1)],u=b[0]>a[0]?Math.max(0,Math.min(1,(t-a[0])/(b[0]-a[0]))):0;return a.map((v,i)=>i?v+u*(b[i]-v):t);}
 function render(){
  if(!data)return;
  play.textContent=playing?'Pause':'Play';slider.value=elapsed/duration;
  root.dataset.elapsed=elapsed.toFixed(3);root.querySelector('#mpc-process-counter').textContent=elapsed.toFixed(1)+' / '+duration.toFixed(1)+' s';

  for(const panel of panels){
   const name=panel.dataset.process,r=data[name],start=r.updates[0].time,end=r.observed.at(-1)[0],time=Math.min(start+elapsed,end);
   let idx=0;while(idx+1<r.updates.length&&r.updates[idx+1].time<=time)idx++;
   const u=r.updates[idx],actual=at(r.observed,time),color=name==='optimized'?'#658660':'#a46c68';
   for(let hand=0;hand<2;hand++){
   const c=panel.querySelectorAll('canvas')[hand],ctx=c.getContext('2d');c.height=440;
   ctx.fillStyle='#fbfcfa';ctx.fillRect(0,0,560,440);ctx.font=Math.max(12,11*560/(c.clientWidth||560))+'px Arial';
   panel.dataset.update=String(u.sourceIndex);panel.dataset.time=time.toFixed(3);panel.dataset.snapshot=u.time.toFixed(3);panel.dataset.liveUpdate=String(r.updates[idx].sourceIndex);
   const direction=r.reference.at(-1).slice(0,2).map((v,i)=>v-r.reference[0][i]),length=Math.hypot(...direction)||1;
   const along=(p,o)=>(p[0]-o[0])*direction[0]/length+(p[1]-o[1])*direction[1]/length;
   function line(points,col,width=1,dash=[]){if(!points.length)return;ctx.beginPath();ctx.strokeStyle=col;ctx.lineWidth=width;ctx.setLineDash(dash);points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();ctx.setLineDash([]);}
   function dot(p,radius,fill){ctx.beginPath();ctx.arc(...p,radius,0,Math.PI*2);ctx.fillStyle=fill;ctx.fill();ctx.strokeStyle=color;ctx.lineWidth=1.4;ctx.stroke();}
   const object=actual.slice(7,10),error=Math.hypot(object[0]-r.reference.at(-1)[0],object[1]-r.reference.at(-1)[1]);
   const origin=u.paths[u.applied][0][hand],selected=u.paths[u.applied];
   const lateral=(p,o)=>((p[0]-o[0])*-direction[1]+(p[1]-o[1])*direction[0])/length;
   const deviations=u.paths.slice(0,r.population).map(path=>path.map((p,j)=>1000*along(p[hand],selected[j][hand])));
   const limit=r.displayLimit;
   const x=t=>64+t/r.horizon*454,y=v=>280-v/limit*115;
   panel.dataset.residualLimit=String(limit);panel.dataset.horizon=String(r.horizon);c.dataset.palm=String(hand);c.dataset.residualLimit=String(limit);c.dataset.horizon=String(r.horizon);panel.dataset.candidateCount=String(deviations.length);
   ctx.fillStyle='#53604e';ctx.fillText((hand?'Right':'Left')+' palm · forecast ensemble',16,22);
   ctx.font=Math.max(12,10*560/(c.clientWidth||560))+'px Arial';
   for(const v of [-limit,0,limit]){line([[64,y(v)],[518,y(v)]],'#e5eae0');ctx.fillStyle='#687563';ctx.fillText(String(Number(v.toPrecision(3))),14,y(v)+4);}
   ctx.fillText('Deviation from nominal (mm)',16,155);
   deviations.forEach((values,n)=>line(values.map((v,j)=>[x(r.futureTimes[j]),y(v)]),u.elites.includes(n)?color:'#bcc7b5',u.elites.includes(n)?2:1));
   line([[x(0),y(0)],[x(r.horizon),y(0)]],color,2.5);
   const dt=Math.max(0,Math.min(r.horizon,time-u.time));let j=0;while(j+1<r.futureTimes.length&&r.futureTimes[j+1]<dt)j++;const k=Math.min(j+1,selected.length-1),mix=(dt-r.futureTimes[j])/(r.futureTimes[k]-r.futureTimes[j]||1),nominal=selected[j][hand].map((v,i)=>v+mix*(selected[k][hand][i]-v));
   const tracking=1000*along(actual.slice(1+3*hand,4+3*hand),nominal);dot([x(dt),y(Math.max(-limit,Math.min(limit,tracking)))],4,'#394b41');c.dataset.trackingError=String(tracking);
   if(Math.abs(tracking)>limit){ctx.fillStyle='#394b41';ctx.fillText('Observation '+tracking.toFixed(1)+' mm · outside plot',16,435);}
   const times=[0,r.horizon/2,r.horizon],anchors=times.map(t=>r.futureTimes.reduce((best,v,j)=>Math.abs(v-t)<Math.abs(r.futureTimes[best]-t)?j:best,0));
   anchors.forEach((j,k)=>{dot([x(r.futureTimes[j]),y(0)],k===anchor?6:4,'#fff');ctx.fillStyle='#56664e';ctx.fillText(r.futureTimes[j].toFixed(1)+' s',x(r.futureTimes[j])-12,416);});
   const chosen=anchors[anchor],center=selected[chosen][hand],anchorX=x(r.futureTimes[chosen]);
   const points=u.paths.slice(0,r.population).map(path=>[1000*along(path[chosen][hand],center),1000*lateral(path[chosen][hand],center)]);
   const spread=Math.max(.1,...points.flat().map(Math.abs)),detailScale=10**Math.floor(Math.log10(spread)),detailLimit=Math.ceil(spread/detailScale)*detailScale;
   const inset=[290,40,242,96],px=v=>inset[0]+121+v/detailLimit*66,py=v=>inset[1]+48-v/detailLimit*28;
   const anchorSpread=Math.max(...deviations.map(v=>Math.abs(v[chosen]))),box=[anchorX-5,y(anchorSpread)-5,10,Math.max(10,2*anchorSpread/limit*115+10)];
   ctx.strokeStyle=color;ctx.setLineDash([4,4]);ctx.strokeRect(...box);ctx.setLineDash([]);
   line([[box[0],box[1]],[inset[0],inset[1]+inset[3]]],color,1,[4,4]);line([[box[0]+box[2],box[1]],[inset[0]+inset[2],inset[1]+inset[3]]],color,1,[4,4]);
   ctx.fillStyle='#fff';ctx.fillRect(...inset);ctx.strokeStyle='#bcc9b5';ctx.strokeRect(...inset);
   line([[px(-detailLimit),py(0)],[px(detailLimit),py(0)]],'#e6ece0');line([[px(0),py(-detailLimit)],[px(0),py(detailLimit)]],'#e6ece0');
   points.forEach((p,n)=>{ctx.beginPath();ctx.arc(px(p[0]),py(p[1]),u.elites.includes(n)?3.4:2.2,0,Math.PI*2);ctx.fillStyle=u.elites.includes(n)?color:'#b9c5b2';ctx.fill();});dot([px(0),py(0)],4,'#fff');
   ctx.fillStyle='#53644d';ctx.fillText('Anchor at +'+r.futureTimes[chosen].toFixed(1)+' s',inset[0]+8,inset[1]+16);ctx.fillText('XY scale ±'+Number(detailLimit.toPrecision(3))+' mm',inset[0]+8,inset[1]+90);
   c.dataset.anchor=String(anchor);c.dataset.anchorTime=String(r.futureTimes[chosen]);c.dataset.detailLimit=String(detailLimit);
   c._anchorPixels=anchors.map(j=>[x(r.futureTimes[j]),y(0)]);
   }
   const values=[`${r.population} candidates · ${r.horizon.toFixed(1)} s forecast · saved at ${(u.time-start).toFixed(1)} s`,
    `Fixed ±${r.displayLimit} mm · ${r.step.toFixed(2)} s control interval`];
   panel.querySelector('.mpc-process-readout').replaceChildren(...values.map(v=>{const p=document.createElement('p');p.textContent=v;return p;}));
  }
 }
 function tick(now){frame=0;if(!visible||!playing||!data||document.hidden)return;if(last)elapsed=Math.min(duration,elapsed+rate*(now-last)/1000);last=now;if(elapsed>=duration)playing=false;render();if(playing)frame=requestAnimationFrame(tick);}
 function schedule(){if(!frame&&visible&&playing&&data&&!document.hidden){last=0;frame=requestAnimationFrame(tick);}}
 async function initialize(){
  if(data||loading)return;loading=true;const status=root.querySelector('.mpc-process-loading');status.textContent='Preparing recorded execution…';
  try{await loadScript('assets/mpc-process-data.js',()=>!!window.CLEAR_MPC_PROCESS);data=window.CLEAR_MPC_PROCESS;
   // One scale per controller, shared by both palms and every saved update.
   for(const r of Object.values(data)){
    const direction=r.reference.at(-1).slice(0,2).map((v,i)=>v-r.reference[0][i]),length=Math.hypot(...direction)||1;let extent=.1;
    for(const u of r.updates)for(const path of u.paths.slice(0,r.population))for(let j=0;j<path.length;j++)for(let hand=0;hand<2;hand++){
     const nominal=u.paths[u.applied][j][hand],p=path[j][hand];extent=Math.max(extent,1000*Math.abs(((p[0]-nominal[0])*direction[0]+(p[1]-nominal[1])*direction[1])/length));
    }
    const step=10**Math.floor(Math.log10(extent));r.displayLimit=Math.ceil(extent/step)*step;
   }
   duration=Math.max(...Object.values(data).map(r=>r.observed.at(-1)[0]-r.updates[0].time));status.hidden=true;root.querySelector('.mpc-process-content').hidden=false;render();schedule();}
  catch{status.textContent='Optimization replay is taking longer to load. ';const b=document.createElement('button');b.textContent='Retry replay';b.onclick=initialize;status.append(b);}finally{loading=false;}
 }
 new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible){initialize();schedule();}else{cancelAnimationFrame(frame);frame=0;last=0;}},{rootMargin:'120px'}).observe(root);
 play.onclick=()=>{playing=!playing;if(playing&&elapsed>=duration)elapsed=0;render();schedule();};root.querySelector('#mpc-process-replay').onclick=()=>{elapsed=0;playing=true;render();schedule();};slider.oninput=()=>{elapsed=+slider.value*duration;render();};
 root.querySelectorAll('canvas').forEach(canvas=>{canvas.addEventListener('click',event=>{const rect=canvas.getBoundingClientRect(),x=(event.clientX-rect.left)*560/rect.width,y=(event.clientY-rect.top)*440/rect.height;let best=0,distance=Infinity;for(const [i,p] of (canvas._anchorPixels||[]).entries()){const delta=Math.hypot(x-p[0],y-p[1]);if(delta<distance){best=i;distance=delta;}}if(distance<35){anchor=best;root.querySelectorAll('[data-anchor]').forEach(b=>b.setAttribute('aria-pressed',String(+b.dataset.anchor===anchor)));render();}});});
 root.querySelectorAll('[data-anchor]').forEach(button=>button.onclick=()=>{anchor=Number(button.dataset.anchor);root.querySelectorAll('[data-anchor]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();});
 const speed=root.querySelector('#mpc-process-speed');speed.onchange=()=>{rate=Number(speed.value);last=0;};
 new ResizeObserver(()=>{if(data)render();}).observe(root);
 document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;last=0;}else schedule();});
 reduced.addEventListener('change',()=>{if(reduced.matches){playing=false;render();}});
})();
