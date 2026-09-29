/* Recorded bimanual trajectories in a shared 2D or oblique 3D coordinate view. */
(() => {
 const root=document.querySelector('#mpc-process');if(!root)return;
 const play=root.querySelector('#mpc-process-play'),slider=root.querySelector('#mpc-process-update'),panels=[...root.querySelectorAll('[data-process]')];
 const W=560,H=560,cache=new Map();let data=null,loading=false,visible=false,playing=!reduced.matches,elapsed=0,duration=0,axisEnd=45,mode='3d',last=0,frame=0,bounds=[],screenBounds=[];
 const format=n=>String(Number(n.toPrecision(2)));
 function at(rows,t){let lo=0,hi=rows.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(rows[mid][0]<=t)lo=mid;else hi=mid-1;}const a=rows[lo],b=rows[Math.min(lo+1,rows.length-1)],u=b[0]>a[0]?Math.max(0,Math.min(1,(t-a[0])/(b[0]-a[0]))):0;return a.map((v,i)=>i?v+u*(b[i]-v):t);}
 function coords(p,r){const x=p[0]-r.origin[0],y=p[1]-r.origin[1];return [x*r.direction[0]+y*r.direction[1],-x*r.direction[1]+y*r.direction[0],p[2]];}
 const oblique=p=>[.866*p[0]+.5*p[1],.28*p[0]-.485*p[1]-.84*p[2]];
 function project(p){const [x,y]=oblique(p),[[xmin,xmax],[ymin,ymax]]=screenBounds,s=Math.min(440/(xmax-xmin),390/(ymax-ymin));return [280+(x-(xmin+xmax)/2)*s,205+(y-(ymin+ymax)/2)*s];}
 const tx=t=>60+t/axisEnd*470,ty=(v,a)=>177+a*151-(v-bounds[a][0])/(bounds[a][1]-bounds[a][0])*111;
 function stroke(ctx,points,color,width=1,dash=[]){if(!points.length)return;ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();ctx.setLineDash([]);}
 function path(ctx,points,times,r,color,width=1){const world=points.map(p=>coords(p,r));if(mode==='3d')stroke(ctx,world.map(project),color,width);else for(let a=0;a<3;a++)stroke(ctx,world.map((p,j)=>[tx(times[j]),ty(p[a],a)]),color,width);}
 function dot(ctx,p,fill,radius=4){ctx.beginPath();ctx.arc(...p,radius,0,Math.PI*2);ctx.fillStyle=fill;ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=1.3;ctx.stroke();}
 function ghosts(name,r){const key=name+mode;if(cache.has(key))return cache.get(key);const layer=document.createElement('canvas');layer.width=W;layer.height=mode==='3d'?420:H;const ctx=layer.getContext('2d');let count=0;
  for(const update of r.updates){const times=r.futureTimes.map(t=>update.time-r.updates[0].time+t);for(let n=0;n<r.population;n++)for(let hand=0;hand<2;hand++){path(ctx,update.paths[n].map(p=>p[hand]),times,r,'#87918a',.65);count++;}}
  const entry={layer,count};cache.set(key,entry);return entry;
 }
 function drawGrid(ctx){ctx.font=Math.max(13,10*W/(ctx.canvas.clientWidth||W))+'px Arial';ctx.fillStyle='#707c6a';
  if(mode==='2d'){
   for(let a=0;a<3;a++){const[lo,hi]=bounds[a],bottom=177+a*151;ctx.fillText(['X · Forward (m)','Y · Lateral (m)','Z · Height (m)'][a],15,bottom-130);
    for(const v of [lo,(lo+hi)/2,hi]){stroke(ctx,[[60,ty(v,a)],[530,ty(v,a)]],'#e4e9df');ctx.fillText(format(v),12,ty(v,a)+4);}
    for(const t of [0,10,20,30,40,axisEnd]){stroke(ctx,[[tx(t),bottom-111],[tx(t),bottom]],'#edf0e9');if(a===2)ctx.fillText(t+' s',tx(t)-10,bottom+21);}
   }ctx.fillText('Full execution time · fixed scales',16,542);return;
  }
  const[xlo,xhi]=bounds[0],[ylo,yhi]=bounds[1];
  for(let x=Math.ceil(xlo);x<=xhi;x++)stroke(ctx,[project([x,ylo,0]),project([x,yhi,0])],'#e5eae1');
  for(let y=Math.ceil(ylo);y<=yhi;y++)stroke(ctx,[project([xlo,y,0]),project([xhi,y,0])],'#e5eae1');
  const origin=[xlo,ylo,0],directions=[[xhi,ylo,0],[xlo,yhi,0],[xlo,ylo,bounds[2][1]]];
  directions.forEach((end,a)=>{stroke(ctx,[project(origin),project(end)],'#8a9880',1.3);const p=project(end);ctx.fillStyle='#53654a';ctx.fillText(['X · Forward','Y · Lateral','Z · Height'][a],Math.max(10,Math.min(470,p[0]+6)),p[1]-6);});
  ctx.fillStyle='#7a8572';ctx.fillText('Shared XYZ frame · metres',16,402);
 }
 function render(){if(!data)return;play.textContent=playing?'Pause':'Play';slider.value=elapsed/duration;root.dataset.elapsed=elapsed.toFixed(3);root.dataset.view=mode;root.querySelector('#mpc-process-counter').textContent=elapsed.toFixed(1)+' / '+duration.toFixed(1)+' s';
  for(const panel of panels){const name=panel.dataset.process,r=data[name],start=r.updates[0].time,end=r.observed.at(-1)[0],time=Math.min(start+elapsed,end),done=elapsed>=end-start;let index=0;while(index+1<r.updates.length&&r.updates[index+1].time<=time)index++;
   const u=r.updates[index],actual=at(r.observed,time),c=panel.querySelector('canvas'),ctx=c.getContext('2d'),ghost=ghosts(name,r),colors=name==='optimized'?['#537d59','#739b97']:['#b97773','#bd9891'];
   panel.dataset.update=String(u.sourceIndex);panel.dataset.time=String(time);panel.dataset.complete=String(done);panel.dataset.retained=u.elites.join(',');panel.dataset.candidateCount=String(r.population);
   panel.querySelector('.mpc-recording-status').textContent=(done?'Recording complete · ':'Recorded duration · ')+(end-start).toFixed(1)+' s';
   c.width=W;c.height=mode==='3d'?420:H;c.dataset.view=mode;c.dataset.hands='2';c.dataset.ghostTrajectories=String(ghost.count);c.dataset.coordinateBounds=JSON.stringify(bounds);c.dataset.axisEnd=String(axisEnd);c.dataset.observedUntil=String(time-start);c.dataset.recordedEnd=String(end-start);c.dataset.applied=String(u.applied);
   ctx.fillStyle='#fbfcfa';ctx.fillRect(0,0,W,H);drawGrid(ctx);ctx.globalAlpha=.27;ctx.drawImage(ghost.layer,0,0);ctx.globalAlpha=1;
   const currentTimes=r.futureTimes.map(t=>u.time-start+t);
   for(let hand=0;hand<2;hand++){
    const all=r.observed.map(row=>row.slice(1+hand*3,4+hand*3)),allTimes=r.observed.map(row=>row[0]-start);path(ctx,all,allTimes,r,'rgba(130,136,134,.4)',1.8);
    for(let n=0;n<r.population;n++)path(ctx,u.paths[n].map(p=>p[hand]),currentTimes,r,u.elites.includes(n)?colors[hand]:'#b4bdb0',u.elites.includes(n)?1.3:.7);
    path(ctx,u.paths[u.applied].map(p=>p[hand]),currentTimes,r,colors[hand],2.2);
    const history=r.observed.filter(row=>row[0]<=time),positions=history.map(row=>row.slice(1+hand*3,4+hand*3)),times=history.map(row=>row[0]-start),now=actual.slice(1+hand*3,4+hand*3);positions.push(now);times.push(time-start);path(ctx,positions,times,r,'#29302a',2.3);
    const point=coords(now,r),locations=mode==='3d'?[project(point)]:point.map((v,a)=>[tx(time-start),ty(v,a)]);
    locations.forEach(p=>{dot(ctx,p,colors[hand],done?5.5:4);ctx.fillStyle=colors[hand];ctx.font=Math.max(13,10*W/(ctx.canvas.clientWidth||W))+'px Arial';ctx.fillText(hand?'R':'L',p[0]+7,p[1]+(hand?13:-7));});
   }
   if(mode==='2d')for(let a=0;a<3;a++)stroke(ctx,[[tx(end-start),66+a*151],[tx(end-start),177+a*151]],'#94a28a',1,[3,4]);
  }
 }
 function tick(now){frame=0;if(!visible||!playing||!data||document.hidden)return;if(last)elapsed=Math.min(duration,elapsed+2*(now-last)/1000);last=now;if(elapsed>=duration)playing=false;render();if(playing)frame=requestAnimationFrame(tick);}
 function schedule(){if(!frame&&visible&&playing&&data&&!document.hidden){last=0;frame=requestAnimationFrame(tick);}}
 async function initialize(){if(data||loading)return;loading=true;const status=root.querySelector('.mpc-process-loading');status.textContent='Preparing recorded trajectories…';
  try{await loadScript('assets/mpc-process-data.js',()=>!!window.CLEAR_MPC_PROCESS);data=window.CLEAR_MPC_PROCESS;duration=Math.max(...Object.values(data).map(r=>r.observed.at(-1)[0]-r.updates[0].time));axisEnd=Math.ceil((duration+Math.max(...Object.values(data).map(r=>r.horizon)))/5)*5;
   const ext=[[0,0],[0,0],[0,0]];
   for(const r of Object.values(data)){const d=r.reference.at(-1).slice(0,2).map((v,i)=>v-r.reference[0][i]),length=Math.hypot(...d)||1;r.direction=d.map(v=>v/length);r.origin=[(r.observed[0][1]+r.observed[0][4])/2,(r.observed[0][2]+r.observed[0][5])/2,0];
    const include=p=>coords(p,r).forEach((v,a)=>{ext[a][0]=Math.min(ext[a][0],v);ext[a][1]=Math.max(ext[a][1],v);});
    for(const row of r.observed){include(row.slice(1,4));include(row.slice(4,7));}for(const update of r.updates)for(const candidate of update.paths)for(const pair of candidate)pair.forEach(include);
   }
   bounds=ext.map(([lo,hi])=>[Math.floor(lo*5)/5-.2,Math.ceil(hi*5)/5+.2]);bounds[2][0]=0;
   const corners=[];for(const x of bounds[0])for(const y of bounds[1])for(const z of bounds[2])corners.push(oblique([x,y,z]));screenBounds=[0,1].map(a=>[Math.min(...corners.map(p=>p[a])),Math.max(...corners.map(p=>p[a]))]);
   status.hidden=true;root.querySelector('.mpc-process-content').hidden=false;render();schedule();
  }catch(error){data=null;status.textContent='Trajectories are taking longer to load. ';const b=document.createElement('button');b.textContent='Retry';b.onclick=initialize;status.append(b);}finally{loading=false;}
 }
 new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible){initialize();schedule();}else{cancelAnimationFrame(frame);frame=0;last=0;}},{rootMargin:'120px'}).observe(root);
 play.onclick=()=>{playing=!playing;if(playing&&elapsed>=duration)elapsed=0;render();schedule();};slider.oninput=()=>{elapsed=+slider.value*duration;render();};
 root.querySelectorAll('[data-mpc-view]').forEach(button=>button.onclick=()=>{mode=button.dataset.mpcView;root.querySelectorAll('[data-mpc-view]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();});
 document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;last=0;}else schedule();});reduced.addEventListener('change',()=>{if(reduced.matches){playing=false;render();}});
})();
