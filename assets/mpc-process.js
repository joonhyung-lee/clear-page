/* Continuous recorded execution. Predictions remain distinct from observations. */
(() => {
 const root=document.querySelector('#mpc-process');if(!root)return;
 const play=root.querySelector('#mpc-process-play'),slider=root.querySelector('#mpc-process-update');
 let data=null,loading=false,visible=false,playing=!reduced.matches,elapsed=0,duration=0,last=0,frame=0,full=false;
 const panels=[...root.querySelectorAll('[data-process]')];
 const control=document.createElement('button');control.type='button';control.textContent='Show full horizons';control.setAttribute('aria-pressed','false');
 root.querySelector('.mpc-process-controls').append(control);
 control.onclick=()=>{full=!full;control.setAttribute('aria-pressed',String(full));control.textContent=full?'Use shared 0.6 s window':'Show full horizons';render();};
 function at(rows,t){let lo=0,hi=rows.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(rows[mid][0]<=t)lo=mid;else hi=mid-1;}const a=rows[lo],b=rows[Math.min(lo+1,rows.length-1)],u=b[0]>a[0]?Math.max(0,Math.min(1,(t-a[0])/(b[0]-a[0]))):0;return a.map((v,i)=>i?v+u*(b[i]-v):t);}
 function render(){
  if(!data)return;
  play.textContent=playing?'Pause':'Play';slider.value=elapsed/duration;
  root.dataset.elapsed=elapsed.toFixed(3);root.querySelector('#mpc-process-counter').textContent=elapsed.toFixed(1)+' / '+duration.toFixed(1)+' s';
  root.querySelectorAll('.mpc-stages span').forEach(el=>el.classList.add('active'));
  for(const panel of panels){
   const name=panel.dataset.process,r=data[name],start=r.updates[0].time,end=r.observed.at(-1)[0],time=Math.min(start+elapsed,end);
   let idx=0;while(idx+1<r.updates.length&&r.updates[idx+1].time<=time)idx++;
   const u=r.updates[idx],actual=at(r.observed,time),color=name==='optimized'?'#658660':'#a46c68';
   const c=panel.querySelector('canvas'),ctx=c.getContext('2d');c.height=650;
   ctx.fillStyle='#fbfcfa';ctx.fillRect(0,0,560,650);ctx.font=Math.max(12,11*560/(c.clientWidth||560))+'px Arial';
   panel.dataset.update=String(u.sourceIndex);panel.dataset.time=time.toFixed(3);
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
   const future=full?Math.max(...Object.values(data).map(v=>v.horizon)):.6,past=1.,nowX=100+428*past/(past+future),x=t=>100+(t-time+past)*428/(past+future),scale=full?1:.4;
   for(let hand=0;hand<2;hand++){
    const cy=hand?338:174,origin=actual.slice(1+hand*3,4+hand*3),y=p=>cy-along(p,origin)*60/scale;
    ctx.fillStyle='#53604e';ctx.fillText(hand?'Right palm':'Left palm',16,cy-69);
    ctx.fillText('+'+Math.round(scale*100)+' cm',7,cy-43);ctx.fillText('−'+Math.round(scale*100)+' cm',7,cy+52);
    ctx.fillStyle='#eef1eb';ctx.fillRect(100,cy-60,nowX-100,120);
    line([[100,cy],[528,cy]],'#d7ded2');
    for(const dt of [-1,-.5,0,.3,.6,...(full?[1,1.5,2,2.5]:[])]){if(dt>future)continue;line([[x(time+dt),cy-60],[x(time+dt),cy+60]],dt===0?'#879780':'#e2e7de',1,dt===0?[3,3]:[]);}
    ctx.save();ctx.beginPath();ctx.rect(100,cy-60,428,120);ctx.clip();
    const history=r.observed.filter(row=>row[0]>=time-past&&row[0]<=time).map(row=>[x(row[0]),y(row.slice(1+3*hand,4+3*hand))]);
    history.push([nowX,cy]);line(history,'#465343',2.5);
    const point=(path,j)=>[x(u.time+r.futureTimes[j]),y(path[j][hand])];
    for(let n=0;n<r.population;n++)line(u.paths[n].map((_,j)=>point(u.paths[n],j)),u.elites.includes(n)?color:'#cbd3c5',u.elites.includes(n)?1.5:.8);
    const selected=u.paths[u.applied];line(selected.map((_,j)=>point(selected,j)),color,2.5);
    for(let j=0;j<selected.length;j++)dot(point(selected,j),2.5,'#fff');
    ctx.restore();dot([nowX,cy],5,'#fff');
    const box=[nowX-11,cy-11,22,22],inset=[hand?302:30,496,228,120];
    ctx.strokeStyle=color;ctx.lineWidth=1;ctx.setLineDash([4,4]);ctx.strokeRect(...box);ctx.setLineDash([]);
    // Paired leaders terminate exactly on the two outer corners of the inset.
    line(hand?[[box[0],box[1]+22],[inset[0],inset[1]]]:[[box[0],box[1]+22],[18,cy+72],[18,inset[1]-16],[inset[0],inset[1]]],color,1,[4,4]);
    line(hand?[[box[0]+22,box[1]+22],[inset[0]+inset[2],inset[1]]]:[[box[0]+22,box[1]+22],[26,cy+84],[26,inset[1]-24],[inset[0]+inset[2],inset[1]]],color,1,[4,4]);
    ctx.fillStyle='#fff';ctx.fillRect(...inset);ctx.strokeStyle=color;ctx.setLineDash([4,4]);ctx.strokeRect(...inset);ctx.setLineDash([]);
    const detailPast=.15,detailFuture=.15,detailX=t=>inset[0]+12+(t-time+detailPast)/(detailPast+detailFuture)*(inset[2]-24),detailY=p=>inset[1]+60-along(p,origin)/.06*46;
    ctx.save();ctx.beginPath();ctx.rect(inset[0]+1,inset[1]+1,inset[2]-2,inset[3]-2);ctx.clip();
    line([[inset[0]+12,inset[1]+60],[inset[0]+216,inset[1]+60]],'#e2e7de');
    const trail=r.observed.filter(row=>row[0]>=time-detailPast&&row[0]<=time).map(row=>[detailX(row[0]),detailY(row.slice(1+3*hand,4+3*hand))]);trail.push([detailX(time),detailY(origin)]);line(trail,'#465343',2.5);
    for(let n=0;n<r.population;n++)line(u.paths[n].map((p,j)=>[detailX(u.time+r.futureTimes[j]),detailY(p[hand])]),u.elites.includes(n)?color:'#dce2d8',1);
    line(selected.map((p,j)=>[detailX(u.time+r.futureTimes[j]),detailY(p[hand])]),color,2.5);dot([detailX(time),detailY(origin)],5,'#fff');ctx.restore();
    ctx.fillStyle='#53604e';ctx.fillText(hand?'Right contact detail':'Left contact detail',inset[0]+10,inset[1]+19);ctx.fillText('±6 cm · ±0.15 s',inset[0]+10,inset[1]+108);
   }
   ctx.fillStyle='#677460';ctx.fillText('Observed history',100,424);ctx.fillText('now',nowX-11,448);ctx.textAlign='right';ctx.fillText('Prediction +'+future.toFixed(1)+' s',528,424);ctx.textAlign='left';
   const done=start+elapsed>=end,delta=time-u.time;
   const values=[`${done?'Replay finished':'Continuous replay'} · ${(time-start).toFixed(2)} s`,
    `Recorded population ${u.sourceIndex} / ${r.sourceUpdates} · ${Math.max(0,delta).toFixed(2)} s since this saved update`,
    `${r.population} candidates · ${u.elites.length} selected · ${r.step.toFixed(2)} s control interval`,
    `${r.horizon.toFixed(1)} s native horizon · ${full?'full horizon':'shared first 0.6 s shown'}`];
   panel.querySelector('.mpc-process-readout').replaceChildren(...values.map(v=>{const p=document.createElement('p');p.textContent=v;return p;}));
  }
 }
 function tick(now){frame=0;if(!visible||!playing||!data||document.hidden)return;if(last)elapsed=Math.min(duration,elapsed+(now-last)/1000);last=now;if(elapsed>=duration)playing=false;render();if(playing)frame=requestAnimationFrame(tick);}
 function schedule(){if(!frame&&visible&&playing&&data&&!document.hidden){last=0;frame=requestAnimationFrame(tick);}}
 async function initialize(){
  if(data||loading)return;loading=true;const status=root.querySelector('.mpc-process-loading');status.textContent='Preparing recorded execution…';
  try{await loadScript('assets/mpc-process-data.js',()=>!!window.CLEAR_MPC_PROCESS);data=window.CLEAR_MPC_PROCESS;duration=Math.max(...Object.values(data).map(r=>r.observed.at(-1)[0]-r.updates[0].time));status.hidden=true;root.querySelector('.mpc-process-content').hidden=false;render();schedule();}
  catch{status.textContent='Optimization replay is taking longer to load. ';const b=document.createElement('button');b.textContent='Retry replay';b.onclick=initialize;status.append(b);}finally{loading=false;}
 }
 new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible){initialize();schedule();}else{cancelAnimationFrame(frame);frame=0;last=0;}},{rootMargin:'120px'}).observe(root);
 play.onclick=()=>{playing=!playing;if(playing&&elapsed>=duration)elapsed=0;render();schedule();};root.querySelector('#mpc-process-replay').onclick=()=>{elapsed=0;playing=true;render();schedule();};slider.oninput=()=>{elapsed=+slider.value*duration;render();};
 new ResizeObserver(()=>{if(data)render();}).observe(root);
 document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;last=0;}else schedule();});
 reduced.addEventListener('change',()=>{if(reduced.matches){playing=false;render();}});
})();
