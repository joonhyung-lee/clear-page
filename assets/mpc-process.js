/* Recorded bimanual trajectories in a shared 2D or oblique 3D coordinate view. */
(() => {
 const root=document.querySelector('#mpc-process');if(!root)return;
 const play=root.querySelector('#mpc-process-play'),slider=root.querySelector('#mpc-process-update'),panels=[...root.querySelectorAll('[data-process]')];
 const W=560,H=560,cache=new Map();let data=null,loading=false,visible=false,playing=!reduced.matches,elapsed=0,duration=0,axisEnd=45,mode='3d',last=0,frame=0,bounds=[],screenBounds=[],playEnd=15;
 const camera={yaw:Math.PI/6,pitch:.6,zoom:1,pan:[0,0]},pointers=new Map();let baseScale=1,paintPending=false,robotOverlay=false,lastContextTime=-1;
 const rotate=p=>[Math.cos(camera.yaw)*p[0]+Math.sin(camera.yaw)*p[1],Math.sin(camera.pitch)*(Math.sin(camera.yaw)*p[0]-Math.cos(camera.yaw)*p[1])-Math.cos(camera.pitch)*p[2]];
 const format=n=>String(Number(n.toPrecision(2)));
 function at(rows,t){let lo=0,hi=rows.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(rows[mid][0]<=t)lo=mid;else hi=mid-1;}const a=rows[lo],b=rows[Math.min(lo+1,rows.length-1)],u=b[0]>a[0]?Math.max(0,Math.min(1,(t-a[0])/(b[0]-a[0]))):0;return a.map((v,i)=>i?v+u*(b[i]-v):t);}
 function coords(p,r){const x=p[0]-r.origin[0],y=p[1]-r.origin[1];return [x*r.direction[0]+y*r.direction[1],-x*r.direction[1]+y*r.direction[0],p[2]];}
 const oblique=p=>[Math.cos(Math.PI/6)*p[0]+Math.sin(Math.PI/6)*p[1],Math.sin(.6)*(Math.sin(Math.PI/6)*p[0]-Math.cos(Math.PI/6)*p[1])-Math.cos(.6)*p[2]];
 function project(p){const q=rotate(p.map((v,a)=>v-(bounds[a][0]+bounds[a][1])/2));return [280+q[0]*baseScale*camera.zoom+camera.pan[0],235+q[1]*baseScale*camera.zoom+camera.pan[1]];}
 function repaint(){if(paintPending)return;paintPending=true;requestAnimationFrame(()=>{paintPending=false;render();});}
 function cameraChanged(){for(const key of cache.keys())if(key.endsWith('3d'))cache.delete(key);repaint();}
 function resetCamera(){camera.yaw=Math.PI/6;camera.pitch=.6;camera.zoom=1;camera.pan=[0,0];cameraChanged();}
 const tx=t=>60+t/axisEnd*470,ty=(v,a)=>177+a*151-(v-bounds[a][0])/(bounds[a][1]-bounds[a][0])*111;
 function stroke(ctx,points,color,width=1,dash=[]){if(!points.length)return;ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();ctx.setLineDash([]);}
 function path(ctx,points,times,r,color,width=1){const world=points.map(p=>coords(p,r));if(mode==='3d')stroke(ctx,world.map(project),color,width);else for(let a=0;a<3;a++)stroke(ctx,world.map((p,j)=>[tx(times[j]),ty(p[a],a)]),color,width);}
 function dot(ctx,p,fill,radius=4){ctx.beginPath();ctx.arc(...p,radius,0,Math.PI*2);ctx.fillStyle=fill;ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=1.3;ctx.stroke();}
 function ghosts(name,r){const key=name+mode;if(cache.has(key))return cache.get(key);const layer=document.createElement('canvas');layer.width=W;layer.height=mode==='3d'?420:H;const ctx=layer.getContext('2d');let count=0;
  if(mode==='3d'){
   // World coordinates stay fixed. Reproject them without rebuilding point arrays on every drag.
   const cy=Math.cos(camera.yaw),sy=Math.sin(camera.yaw),sp=Math.sin(camera.pitch),cp=Math.cos(camera.pitch),scale=baseScale*camera.zoom,center=bounds.map(([lo,hi])=>(lo+hi)/2);
   ctx.strokeStyle='#87918a';ctx.lineWidth=.65;
   for(let n=0;n<r.ghostPaths.length;n++){
    if(n%48===0)ctx.beginPath();
    const points=r.ghostPaths[n];for(let j=0;j<points.length;j+=3){const x=points[j]-center[0],y=points[j+1]-center[1],z=points[j+2]-center[2],px=280+(cy*x+sy*y)*scale+camera.pan[0],py=235+(sp*(sy*x-cy*y)-cp*z)*scale+camera.pan[1];if(j)ctx.lineTo(px,py);else ctx.moveTo(px,py);}
    if(n%48===47||n===r.ghostPaths.length-1)ctx.stroke();count++;
   }
  }else for(const update of r.updates){const times=r.futureTimes.map(t=>update.time-r.updates[0].time+t);for(let n=0;n<r.population;n++)for(let hand=0;hand<2;hand++){path(ctx,update.paths[n].map(p=>p[hand]),times,r,'#87918a',.65);count++;}}
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
  ctx.fillStyle='#7a8572';ctx.fillText('Drag to rotate · wheel to zoom · double-click to reset',16,402);
 }
 function detail(ctx,r,u,actual,time,colors,c,forecastValid){
  if(mode!=='3d')return;
  const world=forecastValid?u.paths.flatMap(path=>path.flatMap(pair=>pair.map(p=>coords(p,r)))):[],past=r.observed.filter(row=>row[0]>=time-.6&&row[0]<=time);
  for(const row of [...past,actual])for(let h=0;h<2;h++)world.push(coords(row.slice(1+h*3,4+h*3),r));
  const projected=world.map(project),lo=[0,1].map(a=>Math.min(...projected.map(p=>p[a]))),hi=[0,1].map(a=>Math.max(...projected.map(p=>p[a]))),box=[lo[0]-5,lo[1]-5,Math.max(10,hi[0]-lo[0]+10),Math.max(10,hi[1]-lo[1]+10)];
  ctx.strokeStyle=colors[0];ctx.lineWidth=1;ctx.setLineDash([4,4]);ctx.strokeRect(...box);ctx.setLineDash([]);stroke(ctx,[[box[0]+box[2],box[1]],[334,168]],colors[0],.8,[3,4]);
  const local=world.map(rotate),extent=[0,1].map(a=>[Math.min(...local.map(p=>p[a])),Math.max(...local.map(p=>p[a]))]),scale=Math.min(180/Math.max(.08,extent[0][1]-extent[0][0]),96/Math.max(.08,extent[1][1]-extent[1][0]));
  const mini=p=>{const q=rotate(coords(p,r));return [438+(q[0]-(extent[0][0]+extent[0][1])/2)*scale,100+(q[1]-(extent[1][0]+extent[1][1])/2)*scale];};
  ctx.save();ctx.fillStyle='#eef3e9';ctx.fillRect(334,18,210,150);ctx.fillStyle='#e1e9d9';ctx.fillRect(334,18,210,25);ctx.strokeStyle='#8da080';ctx.strokeRect(334,18,210,150);ctx.beginPath();ctx.rect(335,40,208,126);ctx.clip();
  // A metric plane and coordinate triad give the magnified paths a spatial reference.
  const center=world.reduce((s,p)=>p.map((v,a)=>s[a]+v/world.length),[0,0,0]);
  const miniWorld=p=>{const q=rotate(p);return [438+(q[0]-(extent[0][0]+extent[0][1])/2)*scale,100+(q[1]-(extent[1][0]+extent[1][1])/2)*scale];};
  for(let i=-10;i<=10;i++){const d=i*.1;stroke(ctx,[miniWorld([center[0]+d,center[1]-1,center[2]]),miniWorld([center[0]+d,center[1]+1,center[2]])],'#d2ddc8',.6);stroke(ctx,[miniWorld([center[0]-1,center[1]+d,center[2]]),miniWorld([center[0]+1,center[1]+d,center[2]])],'#d2ddc8',.6);}
  for(let h=0;h<2;h++){
   for(let n=0;forecastValid&&n<r.population;n++)stroke(ctx,u.paths[n].map(pair=>mini(pair[h])),u.elites.includes(n)?colors[h]:'#c9d1c2',u.elites.includes(n)?1.2:.65);
   if(forecastValid)stroke(ctx,u.paths[u.applied].map(pair=>mini(pair[h])),colors[h],2);
   const history=past.map(row=>mini(row.slice(1+h*3,4+h*3)));history.push(mini(actual.slice(1+h*3,4+h*3)));stroke(ctx,history,'#29302a',2.1);const point=history.at(-1);dot(ctx,point,colors[h]);ctx.fillStyle=colors[h];ctx.fillText(h?'R':'L',point[0]+6,point[1]+(h?12:-6));
  }ctx.restore();ctx.fillStyle='#53654a';ctx.font=Math.max(13,10*W/(ctx.canvas.clientWidth||W))+'px Arial';ctx.fillText('Palm detail · '+(time-r.updates[0].time).toFixed(1)+' s',344,35);
  ctx.font='10px Arial';const triad=[350,150];for(let a=0;a<3;a++){const v=[0,0,0];v[a]=15;const q=rotate(v);stroke(ctx,[triad,[triad[0]+q[0],triad[1]+q[1]]],'#65795a',1);ctx.fillText(['X','Y','Z'][a],triad[0]+q[0]+2,triad[1]+q[1]-2);}const metric=scale*.1<70?.1:.05,bar=Math.min(75,metric*scale);stroke(ctx,[[450,153],[450+bar,153]],'#65795a',1.5);ctx.fillText(metric+' m',452,146);
  c.dataset.detailTime=String(time-r.updates[0].time);c.dataset.detailBox=JSON.stringify(box);c.dataset.detailScale=String(scale);c.dataset.detailApplied=String(u.applied);
 }
 function render(){if(!data)return;play.textContent=playing?'Pause':'Play';slider.value=elapsed/playEnd;root.setAttribute('data-play-limit',String(playEnd));root.querySelector(".mpc-time-pin").style.left=(14/playEnd*100)+"%";root.dataset.elapsed=elapsed.toFixed(3);root.dataset.view=mode;root.querySelector('#mpc-process-counter').textContent=elapsed.toFixed(1)+' / '+playEnd.toFixed(1)+' s';
  for(const panel of panels){const name=panel.dataset.process,r=data[name],start=r.updates[0].time,end=r.observed.at(-1)[0],interactionEnd=r.interactionEnd??end,time=Math.min(start+elapsed,end),done=elapsed>=interactionEnd-start;let index=0;while(index+1<r.updates.length&&r.updates[index+1].time<=time)index++;
   const u=r.updates[index],forecastValid=time<=interactionEnd+1e-6,actual=at(r.observed,time),c=panel.querySelector('canvas'),ctx=c.getContext('2d'),ghost=ghosts(name,r),colors=name==='optimized'?['#537d59','#739b97']:['#b97773','#bd9891'];
   panel.dataset.update=String(u.sourceIndex);panel.dataset.time=String(time);panel.dataset.complete=String(done);panel.dataset.retained=u.elites.join(',');panel.dataset.candidateCount=String(r.population);
   panel.querySelector('.mpc-recording-status').textContent=name==='baseline'&&elapsed>14.14?'Contact lost':name==='optimized'&&done?'Interaction complete':'';
   c.width=W;c.height=mode==='3d'?420:H;c.dataset.view=mode;c.dataset.hands='2';c.dataset.ghostTrajectories=String(ghost.count);c.dataset.coordinateBounds=JSON.stringify(bounds);c.dataset.axisEnd=String(axisEnd);c.dataset.observedUntil=String(time-start);c.dataset.recordedEnd=String(end-start);c.dataset.applied=String(u.applied);c.dataset.camera=JSON.stringify(camera);c.dataset.forecastValid=String(forecastValid);c.dataset.postContact=String(name==='baseline'&&elapsed>14.14);
   ctx.fillStyle='#fbfcfa';ctx.fillRect(0,0,W,H);drawGrid(ctx);ctx.globalAlpha=.27;ctx.drawImage(ghost.layer,0,0);ctx.globalAlpha=1;
   const currentTimes=r.futureTimes.map(t=>u.time-start+t);
   for(let hand=0;hand<2;hand++){
    const all=r.observed.map(row=>row.slice(1+hand*3,4+hand*3)),allTimes=r.observed.map(row=>row[0]-start);path(ctx,all,allTimes,r,'rgba(130,136,134,.4)',1.8);
    for(let n=0;forecastValid&&n<r.population;n++)path(ctx,u.paths[n].map(p=>p[hand]),currentTimes,r,u.elites.includes(n)?colors[hand]:'#b4bdb0',u.elites.includes(n)?1.3:.7);
    if(forecastValid)path(ctx,u.paths[u.applied].map(p=>p[hand]),currentTimes,r,colors[hand],2.2);
    const history=r.observed.filter(row=>row[0]<=time),positions=history.map(row=>row.slice(1+hand*3,4+hand*3)),times=history.map(row=>row[0]-start),now=actual.slice(1+hand*3,4+hand*3);positions.push(now);times.push(time-start);path(ctx,positions,times,r,'#29302a',2.3);
    const point=coords(now,r),locations=mode==='3d'?[project(point)]:point.map((v,a)=>[tx(time-start),ty(v,a)]);
    locations.forEach(p=>{dot(ctx,p,colors[hand],done?5.5:4);ctx.fillStyle=colors[hand];ctx.font=Math.max(13,10*W/(ctx.canvas.clientWidth||W))+'px Arial';ctx.fillText(hand?'R':'L',p[0]+7,p[1]+(hand?13:-7));});
   }
   detail(ctx,r,u,actual,time,colors,c,forecastValid);
   if(mode==='2d')for(let a=0;a<3;a++)stroke(ctx,[[tx(interactionEnd-start),66+a*151],[tx(interactionEnd-start),177+a*151]],'#94a28a',1,[3,4]);
  }syncContext();
  root.dispatchEvent(new CustomEvent('clear-mpc-clock',{bubbles:true,detail:{time:elapsed,playing:playing&&visible&&!document.hidden,speed:2}}));
 }
 function syncContext(force=false){if(!robotOverlay)return;if(!force&&Math.abs(elapsed-lastContextTime)<.05)return;lastContextTime=elapsed;for(const panel of panels)panel.querySelector('.mpc-context-viewer iframe.scene-ready')?.contentWindow.postMessage({type:'clear-playback-command',time:elapsed,playing:false},'*');}
 function showContext(){
  root.querySelector('#mpc-robot-context').setAttribute('aria-pressed',String(robotOverlay));
  for(const panel of panels){let viewer=panel.querySelector('.mpc-context-viewer');const canvas=panel.querySelector('canvas');
   if(robotOverlay&&!viewer){viewer=document.createElement('div');viewer.className='viewer mpc-context-viewer';viewer.dataset.scene='mpc-context-'+panel.dataset.process;viewer.dataset.title='Measured robot skeleton and palm trajectories';viewer.dataset.generation='true';viewer.dataset.externalTimeline='true';const preview=document.createElement('img');preview.className='preview-image';preview.alt='Recorded palm trajectories while the robot view loads';preview.src=canvas.toDataURL();const launch=document.createElement('button');launch.className='launch';launch.type='button';launch.textContent='Load robot overlay';viewer.append(preview,launch);canvas.after(viewer);wireViewer(viewer);viewer.addEventListener('scene-settled',()=>syncContext(true));launch.click();}
   canvas.hidden=robotOverlay;if(viewer){viewer.hidden=!robotOverlay;viewer.querySelector('iframe')?.contentWindow.postMessage({type:'clear-scene-visible',visible:robotOverlay&&visible},'*');}
  }syncContext(true);
 }
 function tick(now){frame=0;if(!visible||!playing||!data||document.hidden)return;if(last)elapsed=Math.min(playEnd,elapsed+2*(now-last)/1000);last=now;if(elapsed>=playEnd)playing=false;render();if(playing)frame=requestAnimationFrame(tick);}
 function schedule(){if(!frame&&visible&&playing&&data&&!document.hidden){last=0;frame=requestAnimationFrame(tick);}}
 async function initialize(){if(data||loading)return;loading=true;const status=root.querySelector('.mpc-process-loading');status.textContent='Preparing recorded trajectories…';
  try{await loadScript('assets/mpc-process-data.js',()=>!!window.CLEAR_MPC_PROCESS);data=window.CLEAR_MPC_PROCESS;duration=Math.max(...Object.values(data).map(r=>r.observed.at(-1)[0]-r.updates[0].time));axisEnd=Math.ceil((duration+Math.max(...Object.values(data).map(r=>r.horizon)))/5)*5;
   const ext=[[0,0],[0,0],[0,0]];
   for(const r of Object.values(data)){const d=r.reference.at(-1).slice(0,2).map((v,i)=>v-r.reference[0][i]),length=Math.hypot(...d)||1;r.direction=d.map(v=>v/length);r.origin=[(r.observed[0][1]+r.observed[0][4])/2,(r.observed[0][2]+r.observed[0][5])/2,0];
    const include=p=>coords(p,r).forEach((v,a)=>{ext[a][0]=Math.min(ext[a][0],v);ext[a][1]=Math.max(ext[a][1],v);});
    for(const row of r.observed){include(row.slice(1,4));include(row.slice(4,7));}for(const update of r.updates)for(const candidate of update.paths)for(const pair of candidate)pair.forEach(include);
    r.ghostPaths=[];for(const update of r.updates)for(let n=0;n<r.population;n++)for(let hand=0;hand<2;hand++)r.ghostPaths.push(new Float64Array(update.paths[n].flatMap(pair=>coords(pair[hand],r))));
   }
   bounds=ext.map(([lo,hi])=>[Math.floor(lo*5)/5-.2,Math.ceil(hi*5)/5+.2]);bounds[2][0]=0;
   const corners=[];for(const x of bounds[0])for(const y of bounds[1])for(const z of bounds[2])corners.push(oblique([x,y,z]));screenBounds=[0,1].map(a=>[Math.min(...corners.map(p=>p[a])),Math.max(...corners.map(p=>p[a]))]);
   baseScale=Math.min(440/(screenBounds[0][1]-screenBounds[0][0]),300/(screenBounds[1][1]-screenBounds[1][0]));
   status.hidden=true;root.querySelector('.mpc-process-content').hidden=false;render();schedule();
  }catch(error){data=null;status.textContent='Trajectories are taking longer to load. ';const b=document.createElement('button');b.textContent='Retry';b.onclick=initialize;status.append(b);}finally{loading=false;}
 }
 new IntersectionObserver(entries=>{visible=entries.at(-1).isIntersecting;if(visible){initialize();schedule();}else{cancelAnimationFrame(frame);frame=0;last=0;render();}},{rootMargin:'0px'}).observe(root);
 play.onclick=()=>{playing=!playing;if(playing&&elapsed>=playEnd)elapsed=0;render();schedule();};slider.oninput=()=>{elapsed=+slider.value*playEnd;render();};
 root.querySelector('#mpc-process-replay').onclick=()=>{elapsed=0;playing=true;last=0;render();schedule();};
 root.querySelectorAll('[data-mpc-view]').forEach(button=>button.onclick=()=>{mode=button.dataset.mpcView;if(mode==='2d'&&robotOverlay){robotOverlay=false;showContext();}root.querySelectorAll('[data-mpc-view]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();});
 root.querySelector('#mpc-robot-context').onclick=()=>{if(mode==='2d')root.querySelector('[data-mpc-view="3d"]').click();robotOverlay=!robotOverlay;showContext();};
 root.querySelector('.mpc-time-pin').onclick=()=>{elapsed=14;playing=false;render();};
 root.querySelector('#mpc-full-rollout').onchange=e=>{playEnd=e.target.checked?duration:15;elapsed=Math.min(elapsed,playEnd);if(elapsed>=playEnd)playing=false;render();};
 for(const canvas of root.querySelectorAll('canvas')){
  canvas.tabIndex=0;canvas.setAttribute('aria-label','Interactive bimanual trajectories. Drag to orbit, shift drag to pan, wheel or pinch to zoom. Arrow keys rotate, plus and minus zoom, Home resets.');
  const point=e=>[e.clientX,e.clientY];
  canvas.onpointerdown=e=>{if(mode!=='3d')return;pointers.set(e.pointerId,point(e));canvas.setPointerCapture(e.pointerId);};
  canvas.onpointermove=e=>{if(mode!=='3d'||!pointers.has(e.pointerId))return;const previous=pointers.get(e.pointerId),next=point(e),dx=(next[0]-previous[0])*W/canvas.clientWidth,dy=(next[1]-previous[1])*W/canvas.clientWidth;
   if(pointers.size>1){const other=[...pointers.entries()].find(([id])=>id!==e.pointerId)[1],oldDistance=Math.hypot(previous[0]-other[0],previous[1]-other[1]),distance=Math.hypot(next[0]-other[0],next[1]-other[1]);if(oldDistance>0)camera.zoom=Math.max(.6,Math.min(4,camera.zoom*distance/oldDistance));camera.pan[0]+=dx/2;camera.pan[1]+=dy/2;}
   else if(e.shiftKey||e.buttons===2){camera.pan[0]+=dx;camera.pan[1]+=dy;}
   else{camera.yaw-=dx*.008;camera.pitch=Math.max(.12,Math.min(1.4,camera.pitch+dy*.006));}
   pointers.set(e.pointerId,next);cameraChanged();};
  for(const event of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(event,e=>{pointers.delete(e.pointerId);});
  canvas.addEventListener('wheel',e=>{if(mode!=='3d')return;e.preventDefault();camera.zoom=Math.max(.6,Math.min(4,camera.zoom*Math.exp(-e.deltaY*.001)));cameraChanged();},{passive:false});
  canvas.ondblclick=()=>{if(mode==='3d')resetCamera();};canvas.oncontextmenu=e=>{if(mode==='3d')e.preventDefault();};
  canvas.onkeydown=e=>{if(mode!=='3d')return;const changes={ArrowLeft:()=>camera.yaw+=.12,ArrowRight:()=>camera.yaw-=.12,ArrowUp:()=>camera.pitch=Math.min(1.4,camera.pitch+.08),ArrowDown:()=>camera.pitch=Math.max(.12,camera.pitch-.08),'+':()=>camera.zoom=Math.min(4,camera.zoom*1.15),'=':()=>camera.zoom=Math.min(4,camera.zoom*1.15),'-':()=>camera.zoom=Math.max(.6,camera.zoom/1.15),Home:resetCamera};if(changes[e.key]){e.preventDefault();changes[e.key]();cameraChanged();}};
 }
 document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;last=0;render();}else schedule();});reduced.addEventListener('change',()=>{if(reduced.matches){playing=false;render();}});
})();
