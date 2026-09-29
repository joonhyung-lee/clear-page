/* Explanatory timing over recorded optimizer populations, never simulated evidence. */
(() => {
 const root=document.querySelector('#mpc-process');if(!root)return;
 const play=root.querySelector('#mpc-process-play'),slider=root.querySelector('#mpc-process-update');
 let data=null,loading=false,visible=false,playing=!reduced.matches,progress=.2,phase=0,last=0,frame=0,readoutKey='';
 const stages=['Sample futures','Score and select','Apply command','Observe again'];
 const panels=[...root.querySelectorAll('[data-process]')];
 function render(){
  if(!data)return;const stage=Math.min(3,Math.floor(phase)),fraction=phase-stage;
  root.querySelectorAll('.mpc-stages span').forEach((el,i)=>el.classList.toggle('active',i===stage));
  play.textContent=playing?'Pause':'Play';slider.value=progress;root.querySelector('#mpc-process-counter').textContent=Math.round(progress*100)+'% of each replay';
  const key=stage+'|'+progress;
  for(const panel of panels){
   const name=panel.dataset.process,record=data[name],idx=Math.round(progress*(record.updates.length-1)),update=record.updates[idx],next=record.updates[Math.min(idx+1,record.updates.length-1)];
   const canvas=panel.querySelector('canvas'),ctx=canvas.getContext('2d'),color=name==='optimized'?'#84a77f':'#bd8583';
   const futureTimes=record.futureTimes||update.paths[0].map((_,j)=>j*record.step),horizon=futureTimes.at(-1),appliedRatio=Math.min(1,record.step/(futureTimes[1]||record.step));
   const push=record.reference.at(-1).map((v,i)=>v-record.reference[0][i]),norm=Math.hypot(push[0],push[1])||1;
   const displacement=(p,origin)=>(p[0]-origin[0])*push[0]/norm+(p[1]-origin[1])*push[1]/norm;
   // Both panels use the same displacement scale at the selected replay progress.
   let extent=.03;
   for(const other of Object.values(data)){
    const u=other.updates[Math.round(progress*(other.updates.length-1))],d=other.reference.at(-1).map((v,i)=>v-other.reference[0][i]),length=Math.hypot(d[0],d[1])||1;
    for(const path of u.paths)for(let hand=0;hand<2;hand++)for(const p of path)extent=Math.max(extent,Math.abs((p[hand][0]-path[0][hand][0])*d[0]/length+(p[hand][1]-path[0][hand][1])*d[1]/length));
   }
   extent=Math.ceil(extent*100)/100;
   const font=Math.max(12,12*560/(canvas.clientWidth||560));
   if(canvas.height!==570)canvas.height=570;
   ctx.clearRect(0,0,560,570);ctx.fillStyle='#fbfcfa';ctx.fillRect(0,0,560,570);ctx.font=font+'px Arial';
   function line(points,color,width=1){ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=width;points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();}
   function reveal(points,amount){const end=Math.max(0,Math.min(points.length-1,amount*(points.length-1))),k=Math.floor(end),out=points.slice(0,k+1);if(k<points.length-1)out.push(points[k].map((v,i)=>v+(end-k)*(points[k+1][i]-v)));return out;}
   function dot(point,r,fill){ctx.beginPath();ctx.arc(...point,r,0,2*Math.PI);ctx.fillStyle=fill;ctx.strokeStyle='#3c4740';ctx.lineWidth=1;ctx.fill();ctx.stroke();}
   const count=stage===0?Math.max(1,Math.ceil(fraction*record.population)):record.population;
   for(let hand=0;hand<2;hand++){
    const center=hand===0?108:242,point=(path,j)=>[64+futureTimes[j]/horizon*464,center-displacement(path[j][hand],path[0][hand])*48/extent];
    ctx.fillStyle='#53634f';ctx.fillText(hand===0?'Left palm (cm)':'Right palm (cm)',16,center-60);
    ctx.fillStyle='#7b8378';ctx.fillText('+'+Math.round(extent*100),16,center-40);ctx.fillText('0',16,center+5);ctx.fillText('−'+Math.round(extent*100),16,center+48);
    for(let j=0;j<7;j++){const x=64+j/6*464;line([[x,center-48],[x,center+48]],'#e9ede6');}
    line([[64,center],[528,center]],'#cfd7ca');
    if(stage>=2){ctx.fillStyle=name==='optimized'?'#e4ede0':'#f0e4e2';ctx.fillRect(64,center-48,464*record.step/horizon,96);}
    // This envelope is measured from selected candidates, not a fabricated
    // trust-region bound or a smoothing pass over the recorded trajectories.
    if(stage>=1){
     const selected=update.elites.map(n=>update.paths[n]),upper=[],lower=[];
     for(let j=0;j<update.paths[0].length;j++){const p=selected.map(path=>point(path,j));upper.push([p[0][0],Math.min(...p.map(v=>v[1]))]);lower.push([p[0][0],Math.max(...p.map(v=>v[1]))]);}
     ctx.beginPath();[...upper,...lower.reverse()].forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath();ctx.fillStyle=name==='optimized'?'#dce9d9':'#eeddd9';ctx.fill();
    }
    for(let n=0;n<count;n++){
     const points=update.paths[n].map((_,j)=>point(update.paths[n],j));
     line(stage===0?reveal(points,Math.max(0,(fraction-n/record.population*.4)/.6)):points,stage>=1&&update.elites.includes(n)?color:stage>=1?'#e1e5de':'#c1cec0',stage>=1&&update.elites.includes(n)?2:1);
    }
    if(stage>=2){
     const applied=update.paths[update.applied],points=applied.map((_,j)=>point(applied,j));line(points,color,3);
     points.forEach(p=>dot(p,4,color));const amount=stage===2?fraction:1;
     const current=points[0].map((v,i)=>v+amount*appliedRatio*(points[1][i]-v));dot(current,6,'#fff');
     const inset=[hand===0?34:310,433,216,110],box=[current[0]-12,current[1]-12,24,24];
     ctx.strokeStyle=color;ctx.lineWidth=1;ctx.setLineDash([4,4]);ctx.strokeRect(...box);
     line([[box[0]+12,box[1]+24],[inset[0]+inset[2]/2,inset[1]]],color);ctx.setLineDash([]);
     ctx.fillStyle='#fff';ctx.fillRect(...inset);ctx.strokeStyle=color;ctx.strokeRect(...inset);
     const origin=applied[0][hand],detail=applied.slice(0,2).map(p=>[displacement(p[hand],origin)*appliedRatio,(p[hand][2]-origin[2])*appliedRatio]);
     let zoom=.003;for(const p of detail)zoom=Math.max(zoom,Math.abs(p[0]),Math.abs(p[1]));
     const project=p=>[inset[0]+inset[2]/2+p[0]/zoom*72,inset[1]+inset[3]/2-p[1]/zoom*34];
     ctx.save();ctx.beginPath();ctx.rect(...inset);ctx.clip();
     line([[inset[0]+14,inset[1]+inset[3]/2],[inset[0]+inset[2]-14,inset[1]+inset[3]/2]],'#e4e9e1');
     for(let n=0;n<count;n++){const candidate=update.paths[n],pts=candidate.slice(0,2).map(p=>project([displacement(p[hand],candidate[0][hand])*appliedRatio,(p[hand][2]-candidate[0][hand][2])*appliedRatio]));line(pts,update.elites.includes(n)?color:'#dce2d8',update.elites.includes(n)?1.5:1);}
     const focus=detail[0].map((v,i)=>v+amount*(detail[1][i]-v));line(detail.map(project),color,3);dot(project(focus),5,'#fff');ctx.restore();
     ctx.fillStyle='#566350';ctx.fillText((hand===0?'Left':'Right')+' applied segment',inset[0],inset[1]-8);ctx.fillText('±'+(zoom*100).toFixed(1)+' cm',inset[0]+10,inset[1]+inset[3]-8);
    }
    if(hand===1){ctx.fillStyle='#687361';for(let j=0;j<7;j++)ctx.fillText((j*horizon/6).toFixed(2),53+j/6*464,308);}
   }
   ctx.fillStyle='#687361';ctx.fillText('Future time (s)',225,330);
   ctx.fillText('Object reference anchors',16,360);
   line([[64,382],[528,382]],'#c6cec0');
   for(let i=0;i<5;i++)dot([64+i/4*464,382],4,color);
   const refLength=Math.hypot(push[0],push[1])||1,targetProgress=Math.max(0,Math.min(1,displacement(update.object,record.reference[0])/refLength));dot([64+targetProgress*464,382],6,'#fff');
   if(stage<2){ctx.fillStyle='#6b7766';ctx.fillText('The applied segment expands here after selection.',64,475);}
   if(key!==readoutKey){
    const finite=update.costs.slice(0,record.population).filter(Number.isFinite),appliedCost=update.costs[update.applied];
    const values=[`Recorded update ${update.sourceIndex||idx+1} / ${record.sourceUpdates||record.updates.length} · ${update.time.toFixed(2)} s`,`${stages[stage]} · ${stage===0?record.population+' candidates':update.elites.length+' recorded elites'}`,`${record.horizon.toFixed(1)} s horizon · ${record.step.toFixed(2)} s applied`,
     stage>=1?`Lowest sampled cost: ${Math.min(...finite).toFixed(2)}`:'Costs are evaluated over the prediction horizon.',
     stage>=2?`${name==='optimized'?'Applied candidate '+(update.applied+1):'Applied elite mean'} · cost ${Number.isFinite(appliedCost)?appliedCost.toFixed(2):'invalid'}`:''];
    panel.querySelector('.mpc-process-readout').replaceChildren(...values.filter(Boolean).map(value=>{const p=document.createElement('p');p.textContent=value;return p;}));
   }
  }
  readoutKey=key;
 }
 function tick(now){frame=0;if(!visible||!playing||!data||document.hidden)return;if(last)phase+=(now-last)/1700;last=now;if(phase>=4){phase=0;progress=(progress+1/(Math.min(...Object.values(data).map(r=>r.updates.length))-1))%1;}render();frame=requestAnimationFrame(tick);}
 function schedule(){if(!frame&&visible&&playing&&data&&!document.hidden){last=0;frame=requestAnimationFrame(tick);}}
 async function initialize(){
  if(data||loading)return;loading=true;const status=root.querySelector('.mpc-process-loading');status.textContent='Preparing recorded optimization updates…';
  try{await loadScript('assets/mpc-process-data.js',()=>!!window.CLEAR_MPC_PROCESS);data=window.CLEAR_MPC_PROCESS;status.hidden=true;root.querySelector('.mpc-process-content').hidden=false;render();schedule();}
  catch{status.textContent='Optimization replay is taking longer to load. ';const button=document.createElement('button');button.type='button';button.textContent='Retry replay';button.onclick=initialize;status.append(button);}finally{loading=false;}
 }
 new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible){initialize();schedule();}else{cancelAnimationFrame(frame);frame=0;last=0;}},{rootMargin:'120px'}).observe(root);
 play.onclick=()=>{playing=!playing;render();schedule();};root.querySelector('#mpc-process-replay').onclick=()=>{phase=0;playing=true;render();schedule();};slider.oninput=()=>{progress=+slider.value;phase=0;render();};
 document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;}else schedule();});
 reduced.addEventListener('change',()=>{if(reduced.matches){playing=false;render();}});
})();
