/* Continuous recorded execution. Predictions remain distinct from observations. */
(() => {
 const root=document.querySelector('#mpc-process');if(!root)return;
 const play=root.querySelector('#mpc-process-play'),slider=root.querySelector('#mpc-process-update');
 let data=null,loading=false,visible=false,playing=!reduced.matches,elapsed=0,duration=0,last=0,frame=0;
 const panels=[...root.querySelectorAll('[data-process]')];
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
   const endTime=duration+Math.max(...Object.values(data).map(v=>v.horizon)),x=t=>80+(t-start)/endTime*456;
   const bounds=[-1,3.5],span=bounds[1]-bounds[0];
   for(let hand=0;hand<2;hand++){
    const top=hand?376:112,bottom=top+210,initial=r.observed[0].slice(1+hand*3,4+hand*3),origin=actual.slice(1+hand*3,4+hand*3);
    const y=p=>bottom-(along(p,initial)-bounds[0])/span*210;
    ctx.fillStyle='#53604e';ctx.fillText(hand?'Right palm · travel (m)':'Left palm · travel (m)',16,top-14);
    for(let v=bounds[0];v<=bounds[1]+.001;v+=.5){const yy=bottom-(v-bounds[0])/span*210;line([[80,yy],[536,yy]],'#e2e7de');ctx.fillText(v.toFixed(1),18,yy+4);}
    for(let sec=0;sec<=duration;sec+=10){line([[x(start+sec),top],[x(start+sec),bottom]],'#e2e7de');ctx.fillText(sec+' s',x(start+sec)-10,bottom+20);}
    ctx.save();ctx.beginPath();ctx.rect(80,top,456,210);ctx.clip();
    line(r.observed.filter(row=>row[0]<=time).map(row=>[x(row[0]),y(row.slice(1+hand*3,4+hand*3))]),'#465343',2.5);
    const selected=u.paths[u.applied],point=(path,j)=>[x(u.time+r.futureTimes[j]),y(path[j][hand])];
    for(let n=0;n<r.population;n++)line(u.paths[n].map((_,j)=>point(u.paths[n],j)),u.elites.includes(n)?color:'#cad2c5',u.elites.includes(n)?1.5:.8);
    line(selected.map((_,j)=>point(selected,j)),color,2.5);ctx.restore();
    const current=[x(time),y(origin)];dot(current,5,'#fff');
    const box=[x(time-.2),current[1]-.3/span*210,.8/endTime*456,.6/span*210],inset=[350,top+8,174,94];
    ctx.strokeStyle=color;ctx.setLineDash([4,4]);ctx.strokeRect(...box);ctx.setLineDash([]);
    line([[box[0],box[1]],[inset[0],inset[1]+inset[3]]],color,1,[4,4]);
    line([[box[0]+box[2],box[1]],[inset[0]+inset[2],inset[1]+inset[3]]],color,1,[4,4]);
    ctx.fillStyle='#ffffffed';ctx.fillRect(...inset);ctx.strokeStyle=color;ctx.setLineDash([4,4]);ctx.strokeRect(...inset);ctx.setLineDash([]);
    const dx=t=>inset[0]+10+(t-time+.2)/.8*154,dy=p=>inset[1]+54-along(p,origin)/.3*24;
    ctx.save();ctx.beginPath();ctx.rect(inset[0]+10,inset[1]+30,154,48);ctx.clip();
    line([[inset[0]+10,inset[1]+54],[inset[0]+164,inset[1]+54]],'#e2e7de');
    const history=r.observed.filter(row=>row[0]>=time-.2&&row[0]<=time).map(row=>[dx(row[0]),dy(row.slice(1+3*hand,4+3*hand))]);history.push([dx(time),dy(origin)]);line(history,'#465343',2);
    for(let n=0;n<r.population;n++)line(u.paths[n].map((p,j)=>[dx(u.time+r.futureTimes[j]),dy(p[hand])]),u.elites.includes(n)?color:'#dce2d8',1);
    line(selected.map((p,j)=>[dx(u.time+r.futureTimes[j]),dy(p[hand])]),color,2);dot([dx(time),dy(origin)],4,'#fff');
    ctx.restore();ctx.save();ctx.fillStyle='#53604e';ctx.font=Math.max(12,9*560/(c.clientWidth||560))+'px Arial';ctx.fillText('Current segment',inset[0]+8,inset[1]+16);ctx.fillText('−.2..+.6 s · ±.3 m',inset[0]+8,inset[1]+86);ctx.restore();
   }
   const done=start+elapsed>=end,delta=time-u.time;
   const values=[`${done?'Replay finished':'Continuous replay'} · ${(time-start).toFixed(2)} s`,
    `Recorded population ${u.sourceIndex} / ${r.sourceUpdates} · ${Math.max(0,delta).toFixed(2)} s since this saved update`,
    `${r.population} candidates · ${u.elites.length} selected · ${r.step.toFixed(2)} s control interval`,
    `${r.horizon.toFixed(1)} s prediction · full execution on shared axes`];
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
