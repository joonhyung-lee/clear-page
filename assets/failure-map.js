/* Saved flow states and the archived planning rejection sequence. */
(() => {
 const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 for(const canvas of document.querySelectorAll('[data-failure-map],[data-planning-failure]')){
  const flow=canvas.hasAttribute('data-failure-map'),article=canvas.closest('article');
  const slider=article.querySelector('input'),play=article.querySelector('[data-failure-play]'),replay=article.querySelector('[data-failure-replay]'),output=article.querySelector('.failure-controls output'),status=article.querySelector('.failure-stage');
  let data=null,loading=false,visible=false,time=0,playing=!reduced,last=0,raf=0,bounds;
  function draw(){
   if(!data)return;
   const w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;
   const ratio=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(w*ratio);canvas.height=Math.round(h*ratio);
   const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);ctx.fillStyle='#f7f8f3';ctx.fillRect(0,0,w,h);
   const scene=flow?data.scene:data,g=window.CLEAR_FAILURE_GEOMETRY;
   const candidate=flow?null:data.candidates[Math.min(data.candidates.length-1,Math.floor(time*data.candidates.length))];
   const paths=flow?g.sample(data.referenceFlow[0],time):candidate.paths;
   const [low,high]=bounds,scale=Math.min((w-32)/(high[0]-low[0]),(h-42)/(high[1]-low[1]));
   const xy=p=>[w/2+(p[0]-(high[0]+low[0])/2)*scale,h/2+10-(p[1]-(high[1]+low[1])/2)*scale];
   const rect=(b,color)=>{const p=xy([b[0],b[3]]);ctx.fillStyle=color;ctx.fillRect(p[0],p[1],(b[2]-b[0])*scale,(b[3]-b[1])*scale);};
   for(const t of scene.terrain||[])rect(t.bounds,t.kind==='ramp'?'#deeee3':t.kind==='stair_tread'?'#f1e1d5':'#edf2e9');
   for(const b of scene.walls)rect(b,'#c0c9bd');
   const polygon=(points,fill,stroke,width=1.5)=>{ctx.beginPath();points.map(xy).forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath();ctx.fillStyle=fill;ctx.fill();ctx.strokeStyle=stroke;ctx.lineWidth=width;ctx.stroke();};
   const violations=[];
   paths.forEach((path,index)=>{
    const obj=scene.objects[path.object],color=['#568f9a','#ad805a','#7c83a6'][index%3];
    path.poses.slice(1).forEach((b,j)=>{
     const a=path.poses[j],bad=g.blocked(a,b,obj.size,scene.walls);
     if(bad)violations.push({object:path.object,segment:j});
     ctx.beginPath();ctx.moveTo(...xy(a));ctx.lineTo(...xy(b));ctx.strokeStyle=bad?'#b94732':color;ctx.lineWidth=bad?3:2;ctx.stroke();
     ctx.beginPath();ctx.arc(...xy(b),3.5,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();ctx.stroke();
    });
    for(const j of [Math.floor(path.poses.length/2),path.poses.length-1]){
     const pose=path.poses[j],bad=scene.walls.some(b=>g.overlap(pose,obj.size,b));
     polygon(g.footprint(pose,obj.size),bad?'#b9473240':color+'30',bad?'#b94732':color,2);
    }
   });
   scene.objects.forEach((o,i)=>{polygon(g.footprint(o.pose,o.size),'#d7b49a','#8c7059');const q=xy(o.pose);ctx.font='12px Arial';ctx.fillStyle='#374333';ctx.textAlign='center';ctx.fillText(String(i),q[0],q[1]+4);});
   for(const [p,label]of [[scene.start,'Start'],[scene.goal,'Goal']]){const q=xy(p);ctx.fillStyle='#486a48';ctx.beginPath();ctx.arc(...q,4.5,0,Math.PI*2);ctx.fill();ctx.font='13px Arial';ctx.textAlign='center';ctx.fillText(label,q[0],q[1]-10);}
   canvas.dataset.flowTime=time.toFixed(3);canvas.dataset.overlapSegments=JSON.stringify(violations);
   canvas.dataset.source=flow?'recorded-teaser-flow-draw-0':'archived-planning-decisions';
   slider.value=time;output.textContent=flow?'t = '+time.toFixed(2):(candidate.id+1)+' / '+data.candidates.length;
   status.textContent=flow?(time===0?'Gaussian initialization':time<1?'Generating box waypoints. Red segments intersect obstacles.':'t = 1 · Generated paths intersect obstacles. Clearance failed.'):(time===1?'All 8 candidates rejected. No valid plan returned.':`Candidate ${candidate.id+1}: ${candidate.invalidDecode?'invalid generated path':candidate.rejection==='INTERACTION_REJECTED'?'interaction rejected':'no route to the goal'}`);
   play.textContent=playing?'Pause':'Play';
  }
  function tick(now){raf=0;if(!visible||!playing||!data||document.hidden){last=0;return;}if(last)time=Math.min(1,time+(now-last)/(flow?8000:16000));last=now;if(time===1)playing=false;draw();if(playing)raf=requestAnimationFrame(tick);}
  function schedule(){if(visible&&playing&&data&&!raf&&!document.hidden)raf=requestAnimationFrame(tick);}
  async function load(){
   if(data||loading)return;loading=true;
   try{
    await loadScript('assets/failure-geometry.js',()=>!!window.CLEAR_FAILURE_GEOMETRY);
    await loadScript(flow?'assets/teaser-flow-data.js':'assets/failure-planning-data.js',()=>flow?!!window.CLEAR_TEASER_FLOW:!!window.CLEAR_FAILURE_PLANNING);
    data=flow?window.CLEAR_TEASER_FLOW:window.CLEAR_FAILURE_PLANNING;
    const points=flow?data.referenceFlow[0].states.flatMap(s=>s.flatMap(p=>p.poses)):data.walls.flatMap(b=>[[b[0],b[1]],[b[2],b[3]]]);
    const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
    bounds=[[Math.min(-1,...xs)-.5,Math.min(-1,...ys)-.5],[Math.max(flow?11:12,...xs)+.5,Math.max(flow?18:12,...ys)+.5]];
    draw();schedule();
   }catch(error){status.textContent='Could not load recorded states. Select Replay to retry.';data=null;}finally{loading=false;}
  }
  play.onclick=()=>{playing=!playing;if(playing&&time===1)time=0;last=0;draw();schedule();};
  replay.onclick=()=>{time=0;playing=true;last=0;if(!data)load();else{draw();schedule();}};
  slider.oninput=()=>{time=Number(slider.value);playing=false;last=0;draw();};
  document.addEventListener('visibilitychange',()=>{last=0;if(document.hidden){cancelAnimationFrame(raf);raf=0;}else schedule();});
  new ResizeObserver(draw).observe(canvas);
  new IntersectionObserver(entries=>{visible=entries.at(-1).isIntersecting;last=0;if(!visible){cancelAnimationFrame(raf);raf=0;return;}load();schedule();},{threshold:.1}).observe(canvas);
 }
})();
