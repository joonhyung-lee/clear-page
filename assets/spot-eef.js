/* Measured single-gripper trajectories. No generated candidate forecasts. */
(() => {
 const root=document.querySelector('#spot-process');if(!root)return;
 const panels=[...root.querySelectorAll('[data-spot-process]')],play=root.querySelector('[data-spot-play]'),slider=root.querySelector('input'),counter=root.querySelector('[data-spot-time]'),status=root.querySelector('.spot-loading');
 let data=null,loading=false,visible=false,playing=!reduced.matches,elapsed=0,end=0,last=0,frame=0,mode='3d',bounds=null;
 const camera={yaw:Math.PI/6,pitch:.6,zoom:1,pan:[0,0]},W=560,colors={eef:'#b85c5b',object:'#1a7369',reference:'#3964a3'};
 function at(rows,t){let lo=0,hi=rows.length-1;while(lo<hi){const m=Math.ceil((lo+hi)/2);if(rows[m][0]<=t)lo=m;else hi=m-1;}const a=rows[lo],b=rows[Math.min(lo+1,rows.length-1)],u=b[0]>a[0]?Math.max(0,Math.min(1,(t-a[0])/(b[0]-a[0]))):0;return a.map((v,i)=>i?v+(b[i]-v)*u:t);}
 function local(p,r){return [p[0]-r.reference[0][0],p[1]-r.reference[0][1],p[2]];}
 function rotate(p){return [Math.cos(camera.yaw)*p[0]+Math.sin(camera.yaw)*p[1],Math.sin(camera.pitch)*(Math.sin(camera.yaw)*p[0]-Math.cos(camera.yaw)*p[1])-Math.cos(camera.pitch)*p[2]];}
 function project(p){const q=rotate(p.map((v,a)=>v-(bounds[a][0]+bounds[a][1])/2)),span=Math.hypot(...bounds.map(b=>b[1]-b[0])),scale=330/span*camera.zoom;return [280+q[0]*scale+camera.pan[0],212+q[1]*scale+camera.pan[1]];}
 const tx=t=>58+t/end*470,ty=(v,a)=>157+a*155-(v-bounds[a][0])/(bounds[a][1]-bounds[a][0])*100;
 function stroke(ctx,points,color,width=2,dash=[]){if(!points.length)return;ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();ctx.setLineDash([]);}
 function dot(ctx,p,color,r=5){ctx.beginPath();ctx.arc(...p,r,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.stroke();}
 function path(ctx,rows,r,offset,color,width){const points=rows.map(row=>local(row.slice(offset,offset+3),r));if(mode==='3d')stroke(ctx,points.map(project),color,width);else for(let a=0;a<3;a++)stroke(ctx,points.map((p,i)=>[tx(rows[i][0]),ty(p[a],a)]),color,width);}
 function render(){
  if(!data)return;
  root.dataset.elapsed=elapsed.toFixed(4);root.dataset.view=mode;slider.value=elapsed/end;play.textContent=playing?'Pause':'Play';counter.textContent=`${elapsed.toFixed(1)} / ${end.toFixed(1)} s`;
  for(const panel of panels){
   const r=data[panel.dataset.spotProcess],time=Math.min(elapsed,r.duration),now=at(r.observed,time),rows=r.observed.filter(row=>row[0]<time).concat([now]),c=panel.querySelector('canvas');c.width=W;c.height=mode==='3d'?420:560;
   const ctx=c.getContext('2d');ctx.fillStyle='#fbfcfa';ctx.fillRect(0,0,W,c.height);ctx.font=Math.max(14,11*W/(c.clientWidth||W))+'px Arial';ctx.fillStyle='#647269';
   if(mode==='3d'){
    const [x,y,z]=bounds;
    for(let i=Math.ceil(x[0]);i<=x[1];i++)stroke(ctx,[project([i,y[0],0]),project([i,y[1],0])],'#e1e6df',1);
    for(let i=Math.ceil(y[0]);i<=y[1];i++)stroke(ctx,[project([x[0],i,0]),project([x[1],i,0])],'#e1e6df',1);
    const origin=[x[0],y[0],0];[[x[1],y[0],0],[x[0],y[1],0],[x[0],y[0],z[1]]].forEach((p,a)=>{stroke(ctx,[project(origin),project(p)],'#85917f',1.5);const q=project(p);ctx.fillText(['X','Y','Z'][a],q[0]+5,q[1]-5);});
    stroke(ctx,r.reference.map(p=>project(local(p,r))),colors.reference,3,[7,5]);
    for(const p of [r.reference[0],r.reference.at(-1)])dot(ctx,project(local(p,r)),colors.reference,5);
    ctx.fillText('Drag to rotate · scroll to zoom',16,405);
   }else{
    for(let a=0;a<3;a++){ctx.fillText(['X (m)','Y (m)','Z (m)'][a],12,29+a*155);for(const value of [bounds[a][0],(bounds[a][0]+bounds[a][1])/2,bounds[a][1]]){const y=ty(value,a);stroke(ctx,[[58,y],[528,y]],'#e1e6df',1);ctx.fillText(value.toFixed(1),12,y+4);}for(const t of [0,end/2,end]){stroke(ctx,[[tx(t),57+a*155],[tx(t),157+a*155]],'#e1e6df',1);if(a===2)ctx.fillText(t.toFixed(1),tx(t)-12,491);}}
    ctx.fillText('Recorded time (s) · fixed scales',16,535);
   }
   path(ctx,r.observed,r,1,'#d4d7d2',1.3);path(ctx,rows,r,4,colors.object,3);path(ctx,rows,r,1,colors.eef,3);
   for(const [offset,color] of [[1,colors.eef],[4,colors.object]]){const p=local(now.slice(offset,offset+3),r);if(mode==='3d')dot(ctx,project(p),color,6);else for(let a=0;a<3;a++)dot(ctx,[tx(time),ty(p[a],a)],color,5);}
   panel.querySelector('.mpc-recording-status').textContent=r.toppleTime!==null&&time>=r.toppleTime?'Toppled':elapsed>=r.duration?'Recording ended':'';
   c.dataset.time=String(time);c.dataset.eef=JSON.stringify(now.slice(1,4));c.dataset.object=JSON.stringify(now.slice(4,7));c.dataset.coordinateBounds=JSON.stringify(bounds);c.dataset.source=r.scene;c.dataset.hands='1';
  }
  root.dispatchEvent(new CustomEvent('clear-mpc-clock',{bubbles:true,detail:{group:'spot',time:elapsed,playing:playing&&visible&&!document.hidden,speed:2}}));
 }
 function tick(now){frame=0;if(!data||!visible||!playing||document.hidden)return;if(last)elapsed=Math.min(end,elapsed+2*(now-last)/1000);last=now;if(elapsed>=end)playing=false;render();schedule();}
 function schedule(){if(data&&visible&&playing&&!document.hidden&&!frame){frame=requestAnimationFrame(tick);}}
 async function initialize(){if(data||loading)return;loading=true;status.textContent='Loading recorded EEF motion…';try{
  await loadScript('assets/spot-eef-data.js',()=>!!window.CLEAR_SPOT_EEF);data=window.CLEAR_SPOT_EEF;end=Math.max(...Object.values(data).map(r=>r.duration));
  const ext=[[0,0],[0,0],[0,0]];for(const r of Object.values(data)){const include=p=>local(p,r).forEach((v,a)=>{ext[a][0]=Math.min(ext[a][0],v);ext[a][1]=Math.max(ext[a][1],v);});r.reference.forEach(include);r.observed.forEach(row=>{include(row.slice(1,4));include(row.slice(4,7));});}
  bounds=ext.map(([lo,hi])=>[Math.floor(lo*5)/5-.15,Math.ceil(hi*5)/5+.15]);status.hidden=true;render();schedule();
 }catch(error){data=null;status.textContent='Could not load recorded paths. ';const retry=document.createElement('button');retry.textContent='Retry';retry.onclick=initialize;status.append(retry);}finally{loading=false;}}
 function stopFrame(){cancelAnimationFrame(frame);frame=0;last=0;}
 new IntersectionObserver(entries=>{visible=entries.at(-1).isIntersecting;if(visible){initialize();last=0;render();schedule();}else{stopFrame();render();}},{rootMargin:'0px'}).observe(root);
 play.onclick=()=>{if(!data){playing=true;initialize();return;}playing=!playing;if(playing&&elapsed>=end)elapsed=0;last=0;render();schedule();};
 root.querySelector('[data-spot-replay]').onclick=()=>{elapsed=0;playing=true;last=0;render();schedule();};slider.oninput=()=>{elapsed=+slider.value*end;last=0;render();};
 root.querySelectorAll('[data-spot-view]').forEach(button=>button.onclick=()=>{mode=button.dataset.spotView;root.querySelectorAll('[data-spot-view]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();});
 function reset(){Object.assign(camera,{yaw:Math.PI/6,pitch:.6,zoom:1,pan:[0,0]});render();}
 for(const panel of panels){const c=panel.querySelector('canvas');let pointer=null;
  c.onpointerdown=e=>{if(mode!=='3d')return;pointer=[e.pointerId,e.clientX,e.clientY];c.setPointerCapture(e.pointerId);};
  c.onpointermove=e=>{if(!pointer||e.pointerId!==pointer[0])return;const dx=(e.clientX-pointer[1])*W/c.clientWidth,dy=(e.clientY-pointer[2])*W/c.clientWidth;pointer=[e.pointerId,e.clientX,e.clientY];if(e.shiftKey){camera.pan[0]+=dx;camera.pan[1]+=dy;}else{camera.yaw-=dx*.008;camera.pitch=Math.max(.12,Math.min(1.4,camera.pitch+dy*.006));}render();};
  for(const type of ['pointerup','pointercancel','lostpointercapture'])c.addEventListener(type,()=>{pointer=null;});
  c.addEventListener('wheel',e=>{if(mode!=='3d')return;e.preventDefault();camera.zoom=Math.max(.6,Math.min(4,camera.zoom*Math.exp(-e.deltaY*.001)));render();},{passive:false});c.ondblclick=reset;
  c.onkeydown=e=>{const actions={Home:reset,ArrowLeft:()=>camera.yaw+=.12,ArrowRight:()=>camera.yaw-=.12,ArrowUp:()=>camera.pitch=Math.min(1.4,camera.pitch+.08),ArrowDown:()=>camera.pitch=Math.max(.12,camera.pitch-.08),'+':()=>camera.zoom=Math.min(4,camera.zoom*1.15),'-':()=>camera.zoom=Math.max(.6,camera.zoom/1.15)};if(mode==='3d'&&actions[e.key]){e.preventDefault();actions[e.key]();render();}};
 }
 document.addEventListener('visibilitychange',()=>{stopFrame();render();schedule();});reduced.addEventListener('change',()=>{if(reduced.matches){playing=false;stopFrame();render();}});
})();
