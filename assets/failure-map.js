/* Actual failed flow output. Overlap is computed from object footprints and walls. */
(() => {
 const canvas=document.querySelector('[data-failure-map]');if(!canvas)return;let data,loading=false;
 function overlap(pose,size,wall){
  const c=Math.cos(pose[2]),s=Math.sin(pose[2]),a=size[0]/2,b=size[1]/2;
  const box=[[-a,-b],[a,-b],[a,b],[-a,b]].map(([x,y])=>[pose[0]+x*c-y*s,pose[1]+x*s+y*c]);
  const rect=[[wall[0],wall[1]],[wall[2],wall[1]],[wall[2],wall[3]],[wall[0],wall[3]]];
  for(const [x,y]of [[1,0],[0,1],[c,s],[-s,c]]){const u=box.map(p=>p[0]*x+p[1]*y),v=rect.map(p=>p[0]*x+p[1]*y);if(Math.max(...u)<=Math.min(...v)||Math.max(...v)<=Math.min(...u))return false;}return true;
 }
 function draw(){if(!data)return;const w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;const dpr=Math.min(devicePixelRatio||1,2);canvas.width=w*dpr;canvas.height=h*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
  const scene=data.scene,scale=Math.min((w-34)/12,(h-50)/19),xy=p=>[w/2+(p[0]-5)*scale,h-14-(p[1]+.5)*scale];ctx.fillStyle='#f7f8f3';ctx.fillRect(0,0,w,h);
  const rect=(b,color)=>{const p=xy([b[0],b[3]]);ctx.fillStyle=color;ctx.fillRect(p[0],p[1],(b[2]-b[0])*scale,(b[3]-b[1])*scale);};
  for(const t of scene.terrain)rect(t.bounds,t.kind==='ramp'?'#deeee3':t.kind==='stair_tread'?'#f1e1d5':'#edf2e9');for(const b of scene.walls)rect(b,'#bdc7bd');
  const paths=data.referenceFlow[0].states.at(-1),violations=[];
  for(const path of paths){const object=scene.objects[path.object];
   for(let i=1;i<path.poses.length;i++){const a=path.poses[i-1],b=path.poses[i],count=Math.max(2,Math.ceil(Math.hypot(b[0]-a[0],b[1]-a[1])/.05));let blocked=false;
    for(let j=0;j<=count&&!blocked;j++){const t=j/count,p=a.map((v,k)=>v+(b[k]-v)*t);blocked=scene.walls.some(wall=>overlap(p,object.size,wall));}
    if(blocked)violations.push({object:path.object,segment:i-1});ctx.strokeStyle=blocked?'#bd4b36':'#7894a0';ctx.lineWidth=blocked?3:1.5;ctx.beginPath();ctx.moveTo(...xy(a));ctx.lineTo(...xy(b));ctx.stroke();
   }
  }
  for(const [i,o]of scene.objects.entries()){const p=xy(o.pose);ctx.fillStyle='#d0a285';ctx.fillRect(p[0]-o.size[0]*scale/2,p[1]-o.size[1]*scale/2,o.size[0]*scale,o.size[1]*scale);ctx.font='9px Arial';ctx.fillStyle='#4c5e4d';ctx.textAlign='center';ctx.fillText('OBJ '+i,p[0],p[1]-7);}
  for(const [p,label]of [[scene.start,'Start'],[scene.goal,'Goal']]){const q=xy(p);ctx.fillStyle='#526e47';ctx.beginPath();ctx.arc(...q,3,0,Math.PI*2);ctx.fill();ctx.textAlign='left';ctx.fillText(label,q[0]+5,q[1]+3);}
  canvas.dataset.overlapSegments=JSON.stringify(violations);canvas.dataset.source='recorded-teaser-flow-draw-0-final';
 }
 new ResizeObserver(draw).observe(canvas);new IntersectionObserver(async entries=>{if(!entries.at(-1).isIntersecting||data||loading)return;loading=true;try{await loadScript('assets/teaser-flow-data.js',()=>!!window.CLEAR_TEASER_FLOW);data=window.CLEAR_TEASER_FLOW;draw();}finally{loading=false;}},{rootMargin:'200px'}).observe(canvas);
})();
