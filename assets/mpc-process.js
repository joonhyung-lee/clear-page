/* Continuous recorded execution. Predictions remain distinct from observations. */
(() => {
 const root=document.querySelector('#mpc-process');if(!root)return;
 const play=root.querySelector('#mpc-process-play'),slider=root.querySelector('#mpc-process-update');
 let data=null,loading=false,visible=false,playing=!reduced.matches,elapsed=0,duration=0,last=0,frame=0,hand=0;
 const panels=[...root.querySelectorAll('[data-process]')];
 function at(rows,t){let lo=0,hi=rows.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(rows[mid][0]<=t)lo=mid;else hi=mid-1;}const a=rows[lo],b=rows[Math.min(lo+1,rows.length-1)],u=b[0]>a[0]?Math.max(0,Math.min(1,(t-a[0])/(b[0]-a[0]))):0;return a.map((v,i)=>i?v+u*(b[i]-v):t);}
 function render(){
  if(!data)return;
  play.textContent=playing?'Pause':'Play';slider.value=elapsed/duration;
  root.dataset.elapsed=elapsed.toFixed(3);root.querySelector('#mpc-process-counter').textContent=elapsed.toFixed(1)+' / '+duration.toFixed(1)+' s';

  for(const panel of panels){
   const name=panel.dataset.process,r=data[name],start=r.updates[0].time,end=r.observed.at(-1)[0],time=Math.min(start+elapsed,end);
   let idx=0;while(idx+1<r.updates.length&&r.updates[idx+1].time<=time)idx++;
   let window=0;while(window+1<r.displaySnapshots.length&&r.updates[r.displaySnapshots[window+1]].time<=time+1e-6)window++;
   const held=r.displaySnapshots[window];
   const u=r.updates[held],actual=at(r.observed,time),color=name==='optimized'?'#658660':'#a46c68';
   const c=panel.querySelector('canvas'),ctx=c.getContext('2d');c.height=420;
   ctx.fillStyle='#fbfcfa';ctx.fillRect(0,0,560,420);ctx.font=Math.max(12,11*560/(c.clientWidth||560))+'px Arial';
   panel.dataset.update=String(u.sourceIndex);panel.dataset.time=time.toFixed(3);panel.dataset.snapshot=u.time.toFixed(3);panel.dataset.liveUpdate=String(r.updates[idx].sourceIndex);
   const direction=r.reference.at(-1).slice(0,2).map((v,i)=>v-r.reference[0][i]),length=Math.hypot(...direction)||1;
   const along=(p,o)=>(p[0]-o[0])*direction[0]/length+(p[1]-o[1])*direction[1]/length;
   function line(points,col,width=1,dash=[]){if(!points.length)return;ctx.beginPath();ctx.strokeStyle=col;ctx.lineWidth=width;ctx.setLineDash(dash);points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();ctx.setLineDash([]);}
   function dot(p,radius,fill){ctx.beginPath();ctx.arc(...p,radius,0,Math.PI*2);ctx.fillStyle=fill;ctx.fill();ctx.strokeStyle=color;ctx.lineWidth=1.4;ctx.stroke();}
   const object=actual.slice(7,10),error=Math.hypot(object[0]-r.reference.at(-1)[0],object[1]-r.reference.at(-1)[1]);
   ctx.fillStyle='#465344';ctx.fillText('Observed object progress',16,24);ctx.fillText('Goal error '+error.toFixed(2)+' m',360,24);
   line([[40,53],[520,53]],'#cdd5c8',2);
   for(let i=0;i<5;i++)dot([40+i*120,53],4,'#fff');
   dot([40+Math.max(0,Math.min(1,along(object,r.reference[0])/length))*480,53],7,color);
   ctx.fillStyle='#717a6c';ctx.fillText('start',28,77);ctx.fillText('goal',504,77);
   const endTime=duration+Math.max(...Object.values(data).map(v=>v.horizon)),x=t=>80+(t-start)/endTime*456;
   const bounds=[-1,3.5],span=bounds[1]-bounds[0];
   {
    const top=140,bottom=354,initial=r.observed[0].slice(1+hand*3,4+hand*3),origin=actual.slice(1+hand*3,4+hand*3);
    const y=p=>bottom-(along(p,initial)-bounds[0])/span*214;
    ctx.fillStyle='#53604e';ctx.fillText((hand?'Right':'Left')+' palm · travel (m)',16,112);
    for(let v=-1;v<=3.5;v+=1){const yy=bottom-(v-bounds[0])/span*214;line([[66,yy],[536,yy]],'#e8ece5');ctx.fillText(v.toFixed(0),22,yy+4);}
    for(let sec=0;sec<=duration;sec+=10){ctx.fillText(sec+' s',x(start+sec)-10,bottom+23);}
    const selected=u.paths[u.applied],point=(path,j)=>[x(u.time+r.futureTimes[j]),y(path[j][hand])];
    ctx.save();ctx.beginPath();ctx.rect(66,top,470,214);ctx.clip();
    line(r.observed.map(row=>[x(row[0]),y(row.slice(1+hand*3,4+hand*3))]),'#dfe4dc',1.3,[3,4]);
    line(r.observed.filter(row=>row[0]<=time).map(row=>[x(row[0]),y(row.slice(1+hand*3,4+hand*3))]),'#394b41',2.8);
    for(let n=0;n<r.population;n++)line(u.paths[n].map((_,j)=>point(u.paths[n],j)),u.elites.includes(n)?color:'#bdc7ba',u.elites.includes(n)?1.3:.8);
    line(selected.map((_,j)=>point(selected,j)),color,2);ctx.restore();
    const current=[x(time),y(origin)];dot(current,5,'#fff');
    const box=[x(u.time),top,x(u.time+r.horizon)-x(u.time),214],inset=[current[0]>280?86:272,148,264,178];
    ctx.strokeStyle=color;ctx.setLineDash([3,4]);ctx.strokeRect(...box);ctx.setLineDash([]);
    line([[box[0],top],[inset[0],inset[1]+inset[3]]],color,.8,[3,4]);
    line([[box[0]+box[2],top],[inset[0]+inset[2],inset[1]+inset[3]]],color,.8,[3,4]);
    ctx.fillStyle='#fff';ctx.fillRect(...inset);ctx.strokeStyle='#cbd4c6';ctx.strokeRect(...inset);
    // Subtract the same nominal prediction from every path. This exposes real
    // millimetre-scale candidate spread without inventing offsets or jitter.
    const deviations=u.paths.slice(0,r.population).map(path=>path.map((p,j)=>1000*along(p[hand],selected[j][hand])));
    const extent=Math.max(.1,...deviations.flat().map(Math.abs)),scale=10**Math.floor(Math.log10(extent));
    const limit=Math.ceil(extent/scale)*scale,dx=t=>inset[0]+46+(t-u.time)/r.horizon*202,dy=v=>inset[1]+89-v/limit*47;
    panel.dataset.residualLimit=String(limit);panel.dataset.horizon=String(r.horizon);panel.dataset.palm=String(hand);panel.dataset.candidateCount=String(deviations.length);
    ctx.save();ctx.font=Math.max(12,9*560/(c.clientWidth||560))+'px Arial';ctx.fillStyle='#53604e';
    ctx.fillText('Candidate deviation (mm)',inset[0]+10,inset[1]+20);
    for(const v of [-limit,0,limit]){line([[dx(u.time),dy(v)],[dx(u.time+r.horizon),dy(v)]],'#edf0e9');ctx.fillText(String(v),inset[0]+5,dy(v)+4);}
    ctx.save();ctx.beginPath();ctx.rect(dx(u.time),dy(limit)-2,202,98);ctx.clip();
    deviations.forEach((values,n)=>line(values.map((v,j)=>[dx(u.time+r.futureTimes[j]),dy(v)]),u.elites.includes(n)?color:'#b8c2b1',u.elites.includes(n)?1.8:.9));
    line([[dx(u.time),dy(0)],[dx(u.time+r.horizon),dy(0)]],color,2.2);
    function nominal(t){let j=0;const future=Math.max(0,Math.min(r.horizon,t-u.time));while(j+1<r.futureTimes.length&&r.futureTimes[j+1]<future)j++;const k=Math.min(j+1,selected.length-1),fraction=(future-r.futureTimes[j])/(r.futureTimes[k]-r.futureTimes[j]||1);return selected[j][hand].map((v,i)=>v+fraction*(selected[k][hand][i]-v));}
    const observed=r.observed.filter(row=>row[0]>=u.time&&row[0]<=time&&row[0]<=u.time+r.horizon).map(row=>[dx(row[0]),dy(1000*along(row.slice(1+hand*3,4+hand*3),nominal(row[0])))]);
    line(observed,'#394b41',2.3);ctx.restore();
    const error=1000*along(origin,nominal(time)),clamped=Math.max(-limit,Math.min(limit,error));
    panel.dataset.trackingError=String(error);
    dot([dx(Math.min(time,u.time+r.horizon)),dy(clamped)],4,'#fff');
    ctx.fillStyle='#53604e';ctx.fillText('0',dx(u.time)-3,inset[1]+155);ctx.fillText(r.horizon.toFixed(1)+' s',dx(u.time+r.horizon)-26,inset[1]+155);
    if(Math.abs(error)>limit){ctx.fillStyle='#394b41';ctx.fillText('Observed '+error.toFixed(1)+' mm · off scale',inset[0]+10,inset[1]+173);}
    ctx.restore();
    ctx.fillStyle='#6a7667';ctx.fillText('Execution time',16,405);
   }
   const values=[`${r.population} candidates · ${r.horizon.toFixed(1)} s forecast · saved at ${(u.time-start).toFixed(1)} s`,
    `Object moved ${along(object,r.reference[0]).toFixed(2)} m · goal error ${error.toFixed(2)} m`];
   panel.querySelector('.mpc-process-readout').replaceChildren(...values.map(v=>{const p=document.createElement('p');p.textContent=v;return p;}));
  }
 }
 function tick(now){frame=0;if(!visible||!playing||!data||document.hidden)return;if(last)elapsed=Math.min(duration,elapsed+(now-last)/1000);last=now;if(elapsed>=duration)playing=false;render();if(playing)frame=requestAnimationFrame(tick);}
 function schedule(){if(!frame&&visible&&playing&&data&&!document.hidden){last=0;frame=requestAnimationFrame(tick);}}
 async function initialize(){
  if(data||loading)return;loading=true;const status=root.querySelector('.mpc-process-loading');status.textContent='Preparing recorded execution…';
  try{await loadScript('assets/mpc-process-data.js',()=>!!window.CLEAR_MPC_PROCESS);data=window.CLEAR_MPC_PROCESS;
   for(const r of Object.values(data)){r.displaySnapshots=[0];let k=0;while(k+1<r.updates.length){let next=k+1;while(next+1<r.updates.length&&r.updates[next+1].time<=r.updates[k].time+r.horizon+1e-6)next++;r.displaySnapshots.push(next);k=next;}}
   duration=Math.max(...Object.values(data).map(r=>r.observed.at(-1)[0]-r.updates[0].time));status.hidden=true;root.querySelector('.mpc-process-content').hidden=false;render();schedule();}
  catch{status.textContent='Optimization replay is taking longer to load. ';const b=document.createElement('button');b.textContent='Retry replay';b.onclick=initialize;status.append(b);}finally{loading=false;}
 }
 new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible){initialize();schedule();}else{cancelAnimationFrame(frame);frame=0;last=0;}},{rootMargin:'120px'}).observe(root);
 play.onclick=()=>{playing=!playing;if(playing&&elapsed>=duration)elapsed=0;render();schedule();};root.querySelector('#mpc-process-replay').onclick=()=>{elapsed=0;playing=true;render();schedule();};slider.oninput=()=>{elapsed=+slider.value*duration;render();};
 root.querySelectorAll('[data-palm]').forEach(button=>button.onclick=()=>{hand=Number(button.dataset.palm);root.querySelectorAll('[data-palm]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();});
 new ResizeObserver(()=>{if(data)render();}).observe(root);
 document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;last=0;}else schedule();});
 reduced.addEventListener('change',()=>{if(reduced.matches){playing=false;render();}});
})();
