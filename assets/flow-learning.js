/* One metric scene and one native replay clock for both views. */
(() => {
 const root=document.querySelector('#flow-learning');if(!root)return;
 const viewer=root.querySelector('.maze-flow-viewer'),canvas=root.querySelector('canvas'),ctx=canvas.getContext('2d');
 const range=root.querySelector('#flow-progress'),play=root.querySelector('#flow-play'),timeLabel=root.querySelector('#flow-time');
 const caption=root.querySelector('#maze-flow-caption'),tip=root.querySelector('.flow-map-tooltip');
 const colors=['#80a3af','#c99e7c','#91ae80','#ad9dc0','#bea973'];
 let data,loading=false,near=false,sample=0,time=0,playing=false,pending;
 const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 function lerp(a,b,u){return a.map((v,i)=>v*(1-u)+b[i]*u);}
 function elevation(p){let z=0;for(const t of data.scene.terrain){const b=t.bounds;if(p[0]<b[0]||p[0]>b[2]||p[1]<b[1]||p[1]>b[3])continue;const h=t.height_m??(t.start_height_m+(p[t.axis]-b[t.axis])/(b[t.axis+2]-b[t.axis])*(t.end_height_m-t.start_height_m));z=Math.max(z,h);}return z;}
 function center(i,p){return [p[0],p[1],elevation(p)+data.scene.objects[i].size[2]/2+data.anchorHeightOffset];}
 function paths(){const trace=data.referenceFlow[sample];const sampledTime=Math.floor(time*30+1e-6)/30;if(sampledTime>=6)return trace.states.at(-1);const k=clamp(sampledTime/6*30,0,30),lo=Math.floor(k),hi=Math.min(lo+1,30);return trace.states[lo].map((p,i)=>({object:p.object,poses:p.poses.map((v,j)=>lerp(v,trace.states[hi][i].poses[j],k-lo))}));}
 function along(poses,u){const k=clamp(u,0,1)*(poses.length-1),lo=Math.floor(k);return lerp(poses[lo],poses[Math.min(lo+1,poses.length-1)],k-lo);}
 function draw(){
  if(!data)return;const w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;
  const dpr=Math.min(devicePixelRatio||1,2);canvas.width=w*dpr;canvas.height=h*dpr;ctx.scale(dpr,dpr);
  const scale=Math.min((w-36)/14,(h-36)/24),xy=p=>[w/2+(p[0]-5)*scale,h/2-(p[1]-6.5)*scale];
  const rect=(b,color)=>{const p=xy([b[0],b[3]]);ctx.fillStyle=color;ctx.fillRect(p[0],p[1],(b[2]-b[0])*scale,(b[3]-b[1])*scale);};
  ctx.fillStyle='#fafbf8';ctx.fillRect(0,0,w,h);rect([0,0,...data.scene.world_size],'#eff3ef');
  for(const t of data.scene.terrain)rect(t.bounds,t.kind==='ramp'?'#d4eede':t.kind==='stair_tread'?(t.bounds[0]<4?'#fadcca':'#dedbf7'):'#e3ebe6');
  ctx.strokeStyle='#dfe6df';ctx.lineWidth=.5;
  for(let x=0;x<=10;x++){ctx.beginPath();ctx.moveTo(...xy([x,0]));ctx.lineTo(...xy([x,17]));ctx.stroke();}
  for(let y=0;y<=17;y++){ctx.beginPath();ctx.moveTo(...xy([0,y]));ctx.lineTo(...xy([10,y]));ctx.stroke();}
  for(const b of data.scene.walls)rect(b,'#b8c5bd');
  function box(i,p,alpha,corners){const v=xy(p),size=data.scene.objects[i].size;ctx.save();ctx.translate(...v);ctx.rotate(-p[2]);const a=size[0]*scale/2,b=size[1]*scale/2;ctx.fillStyle=colors[i];ctx.globalAlpha=alpha;ctx.fillRect(-a,-b,a*2,b*2);ctx.globalAlpha=1;ctx.strokeStyle=colors[i];ctx.lineWidth=corners?1.7:1;
   if(corners){ctx.beginPath();for(const sx of [-1,1])for(const sy of [-1,1]){ctx.moveTo(sx*a,sy*b*.45);ctx.lineTo(sx*a,sy*b);ctx.lineTo(sx*a*.45,sy*b);}ctx.stroke();}else ctx.strokeRect(-a,-b,a*2,b*2);ctx.restore();}
  for(const [i,o]of data.scene.objects.entries()){box(i,o.pose,.7,false);const p=xy(o.pose);ctx.fillStyle='#3e4b43';ctx.font='10px Arial';ctx.textAlign='center';ctx.fillText(String(i),p[0],p[1]-scale*.6);}
  const markers=[],state=[];
  for(const path of paths()){
   const i=path.object,poses=path.poses;ctx.strokeStyle=colors[i];ctx.lineWidth=1.8;ctx.beginPath();poses.forEach((p,j)=>ctx[j?'lineTo':'moveTo'](...xy(p)));ctx.stroke();
   poses.forEach((p,j)=>{const q=xy(p),world=center(i,p);ctx.beginPath();ctx.arc(...q,3.5,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();ctx.stroke();markers.push({x:q[0],y:q[1],object:i,waypoint:j,world});});
   const middle=time<=6?poses[Math.floor(poses.length/2)]:along(poses,(Math.floor(time*30+1e-6)/30-6)/3-data.conditionedOrder.indexOf(i));
   box(i,middle,.17,true);box(i,poses.at(-1),.24,true);state.push({object:i,anchors:poses.map(p=>center(i,p)),ghosts:[center(i,middle),center(i,poses.at(-1))]});
  }
  for(const [p,label,color]of[[data.scene.start,'Start','#527d95'],[data.scene.goal,'Goal','#658c6e']]){const q=xy(p);ctx.fillStyle=color;ctx.beginPath();ctx.arc(...q,4,0,Math.PI*2);ctx.fill();ctx.font='10px Arial';ctx.textAlign='left';ctx.fillText(label,q[0]+6,q[1]-4);}
  canvas._markers=markers;canvas._flowState=state;canvas.dataset.time=time.toFixed(4);canvas.dataset.sample=sample;
  const phase=time<=6?'flow':'sequence',rank=clamp(Math.floor((time-6)/3),0,data.conditionedOrder.length-1);
  root.dataset.phase=phase;root.dataset.activeObject=phase==='flow'?'all':data.conditionedOrder[rank];
  range.value=time;play.textContent=playing?'Pause':'Play';timeLabel.textContent=phase==='flow'?'Flow t = '+(time/6).toFixed(2):'Object '+data.conditionedOrder[rank]+' · path preview';
  root.querySelectorAll('[data-flow-object]').forEach(e=>e.setAttribute('aria-current',String(phase==='sequence'&&Number(e.dataset.flowObject)===data.conditionedOrder[rank])));
  const failed=data.referenceFlow[sample].refinement.filter(c=>!c.refined).map(c=>c.object);
  const audit=data.diagnostics?.conditionalDraws[sample];
  if(audit){
   const lengths=audit.paths.map(p=>`Object ${p.object}: ${p.lengthMeters.toFixed(1)} m`).join(' · ');
   const count=data.diagnostics.endToEndSelectedCounts[sample];
   root.querySelector('#flow-diagnostic').textContent=`Unsuccessful teaser transfer. OrderNet selected ${count} objects. Final raw path lengths with the supplied order: ${lengths}. Noise draws use the checkpoint’s prior standard deviation of ${data.settings.noiseStd}; they are not distinct valid plans.`;
  }
  caption.textContent='Supplied order: '+data.conditionedOrder.map(i=>'Object '+i).join(' → ')+'. '+(phase==='flow'?'Actual joint flow integration. ':'Ordered inspection of the generated paths. ')+(failed.length?'Geometry refinement fails for Object '+failed.join(', ')+'. These paths are not a feasible execution plan.':'Clearance checks passed. Physical execution has not been evaluated.');
 }
 function command(value){if(!data)return;const f=viewer.querySelector('iframe.scene-ready');if(f)f.contentWindow.postMessage({type:'clear-playback-command',...value},'*');else{pending={...pending,...value};if(!viewer.querySelector('.viewer-status,.scene-pending'))viewer.querySelector('.launch').click();}}
 function seek(value){time=clamp(value,0,data.timeline.durationSeconds);playing=false;draw();command({time,playing:false});}
 async function initialize(){if(data||loading)return;loading=true;try{await loadScript('assets/teaser-flow-data.js',()=>!!window.CLEAR_TEASER_FLOW);data=window.CLEAR_TEASER_FLOW;range.max=data.timeline.durationSeconds;const sequence=root.querySelector('.flow-sequence');data.conditionedOrder.forEach((i,j)=>{if(j)sequence.append(document.createTextNode(' → '));const node=document.createElement('span');node.dataset.flowObject=i;node.textContent='Object '+i;sequence.append(node);});draw();observeAutomaticScene(viewer);}catch{caption.textContent='The flow data could not load. Scroll back to retry.';}finally{loading=false;}}
 play.onclick=()=>command({playing:!playing});root.querySelector('#flow-replay').onclick=()=>command({time:0,playing:true});range.oninput=()=>seek(+range.value);
 root.querySelector('#maze-flow-sample').onchange=e=>{sample=+e.target.value;time=0;playing=false;const active=!!viewer.querySelector('iframe');viewer.dispatchEvent(new Event('reset-viewer'));viewer.dataset.scene='teaser-flow-'+sample;pending=null;draw();if(active)command({time:0,playing:true});};
 viewer.addEventListener('scene-settled',e=>{if(!e.detail?.failed&&pending&&viewer.querySelector('iframe.scene-ready')){const value=pending;pending=null;command(value);}});
 viewer.addEventListener('reset-viewer',()=>{playing=false;time=0;draw();});
 window.addEventListener('message',e=>{if(e.source!==viewer.querySelector('iframe')?.contentWindow||e.data?.type!=='clear-playback-time'||!data)return;if(pending){const value=pending;pending=null;command(value);return;}time=clamp(e.data.time,0,data.timeline.durationSeconds);playing=!!e.data.playing;draw();});
 canvas.onpointermove=e=>{const b=canvas.getBoundingClientRect(),x=e.clientX-b.left,y=e.clientY-b.top,p=canvas._markers?.find(p=>Math.hypot(x-p.x,y-p.y)<9);tip.hidden=!p;if(p){tip.textContent=`Object ${p.object} · waypoint ${p.waypoint} · (${p.world.map(v=>v.toFixed(2)).join(', ')}) m`;tip.style.left=Math.min(x+10,Math.max(0,b.width-260))+'px';tip.style.top=(y+32)+'px';}};
 canvas.onpointerleave=()=>tip.hidden=true;canvas.onkeydown=e=>{if(!data||!['Home','End','ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();seek(e.key==='Home'?0:e.key==='End'?data.timeline.durationSeconds:time+(e.key==='ArrowLeft'?-.2:.2));};
 new ResizeObserver(draw).observe(canvas);new IntersectionObserver(entries=>{near=entries[0].isIntersecting;if(near)initialize();},{rootMargin:'150px'}).observe(root);
})();
