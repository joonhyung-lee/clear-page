/* Recorded samples and checkpoint features, loaded once for both explorers. */
(() => {
 const colors={g1:'#83aeb8',spot_arm:'#c8ab8d'},objects=['#adcfd5','#e8c5ad','#bfd5b1','#d0bfda'];
 const ns='http://www.w3.org/2000/svg';
 function element(name,attrs){const el=document.createElementNS(ns,name);for(const [key,value]of Object.entries(attrs))el.setAttribute(key,value);return el;}
 for(const root of document.querySelectorAll('.learning-explorer')){
  let initialized=false,visible=false,playing=!reduced.matches,index=0,progress=0,last=0,frame=0,samples=[],dots=[];
  const canvas=root.querySelector('canvas'),ctx=canvas.getContext('2d'),range=root.querySelector('.sample-progress'),play=root.querySelector('.sample-play');
  function path(points,color,width=2,dash=[]){if(!points.length)return;ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();ctx.setLineDash([]);}
  function dot(x,y,r,color){ctx.beginPath();ctx.arc(x,y,r,0,2*Math.PI);ctx.fillStyle=color;ctx.fill();ctx.strokeStyle='#3d4746';ctx.lineWidth=1;ctx.stroke();}
  function render(){
   if(!samples.length)return;const sample=samples[index],scene=sample.scene,frames=sample.rollout;
   const minT=frames[0][0],maxT=frames.at(-1)[0],time=minT+progress*(maxT-minT);
   let k=frames.findIndex(f=>f[0]>=time);if(k<0)k=frames.length-1;
   const a=frames[Math.max(0,k-1)],b=frames[k],t=b[0]===a[0]?0:(time-a[0])/(b[0]-a[0]);
   const mix=(x,y)=>x+(y-x)*t;
   const scale=Math.min(490/scene.world_size[0],330/scene.world_size[1]),ox=(560-scene.world_size[0]*scale)/2,oy=(390+scene.world_size[1]*scale)/2;
   const xy=p=>[ox+p[0]*scale,oy-p[1]*scale];ctx.clearRect(0,0,560,390);ctx.fillStyle='#fafbf9';ctx.fillRect(ox,oy-scene.world_size[1]*scale,scene.world_size[0]*scale,scene.world_size[1]*scale);
   for(const tile of scene.terrain){const [l,b,r,t]=tile.bounds;ctx.fillStyle=tile.kind==='ramp'?'#e3eadd':'#eee9df';ctx.fillRect(ox+l*scale,oy-t*scale,(r-l)*scale,(t-b)*scale);}
   for(const [l,b,r,t]of scene.walls){ctx.fillStyle='#c9cdca';ctx.fillRect(ox+l*scale,oy-t*scale,(r-l)*scale,(t-b)*scale);}
   if(sample.paths)for(const p of sample.paths){const points=p.poses.map(xy);path(points,objects[p.object%4],3,[5,4]);for(let j=0;j<5;j++){const v=points[Math.round(j*(points.length-1)/4)];dot(...v,3.1,objects[p.object%4]);}}
   path(frames.slice(0,k+1).map(f=>xy(f.slice(1,3))),colors[sample.body],2);
   if(sample.query){path(sample.query.map(xy),'#566360',2,[4,4]);sample.query.forEach(p=>dot(...xy(p),4,'#fff'));}
   dot(...xy(scene.goal),5,'#fff');ctx.fillStyle='#59615c';ctx.font='12px Arial';ctx.fillText('Goal',xy(scene.goal)[0]+8,xy(scene.goal)[1]+4);
   scene.objects.forEach((obj,j)=>{const pose=a[4][j].map((v,d)=>mix(v,b[4][j][d])),pos=xy(pose);ctx.save();ctx.translate(...pos);ctx.rotate(-pose[2]);ctx.fillStyle=objects[j%4];ctx.strokeStyle='#606b65';ctx.lineWidth=1;ctx.fillRect(-obj.size[0]*scale/2,-obj.size[1]*scale/2,obj.size[0]*scale,obj.size[1]*scale);ctx.strokeRect(-obj.size[0]*scale/2,-obj.size[1]*scale/2,obj.size[0]*scale,obj.size[1]*scale);ctx.restore();});
   const robot=xy([mix(a[1],b[1]),mix(a[2],b[2])]);ctx.save();ctx.translate(...robot);ctx.rotate(-mix(a[3],b[3]));ctx.fillStyle=colors[sample.body];ctx.strokeStyle='#354740';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(9,0);ctx.lineTo(-6,-5);ctx.lineTo(-6,5);ctx.closePath();ctx.fill();ctx.stroke();ctx.restore();
   range.value=progress;root.querySelector('.sample-time').textContent=time.toFixed(1)+' s';play.textContent=playing?'Pause rollout':'Play rollout';
  }
  function tick(now){frame=0;if(!visible||!playing||!initialized)return;if(last)progress=(progress+(now-last)/10000)%1;last=now;render();frame=requestAnimationFrame(tick);}
  function schedule(){if(!frame&&visible&&!document.hidden&&playing&&initialized){last=0;frame=requestAnimationFrame(tick);}}
  function select(i){
   index=(i+samples.length)%samples.length;progress=0;const sample=samples[index];
   dots.forEach((dot,j)=>{dot.classList.toggle('selected',j===index);dot.setAttribute('tabindex',j===index?'0':'-1');dot.setAttribute('aria-pressed',String(j===index));});
   root.querySelector('.sample-title').textContent=`Sample ${index+1} · ${sample.body==='g1'?'G1':'Spot + arm'} · ${sample.split==='train'?'Training':'Validation'}`;
   root.querySelector('.sample-inputs').textContent=`Inputs: ${sample.links} structural rows, ${sample.scene.objects.length} object ${sample.scene.objects.length===1?'state':'states'}, scene geometry${sample.query?', and one directed query':''}.`;
   const target=root.querySelector('.sample-target');target.replaceChildren();
   if(root.dataset.kind==='grounding'){
    const p=document.createElement('p');p.textContent=`Safe crossing target: ${sample.target}. Predicted probability: ${(100*sample.prediction).toFixed(1)}%.`;target.append(p);
   }else{
    const p=document.createElement('p');p.textContent='Reference order: '+(sample.paths.length?sample.paths.map(p=>'Object '+p.object).join(' → '):'No object interaction');target.append(p);
    const table=document.createElement('table');table.innerHTML='<thead><tr><th>Object</th><th>Target rank</th><th>Selection</th><th>Priority μ</th></tr></thead>';const body=document.createElement('tbody');
    sample.rank.forEach((rank,j)=>{const row=document.createElement('tr');for(const value of [sample.scene.objects[j].object_id,rank<0?'Not selected':rank,(100*sample.selection[j]).toFixed(1)+'%',sample.mu[j].toFixed(2)]){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}body.append(row);});table.append(body);target.append(table);
    const loss=document.createElement('p');loss.className='sample-loss-values';loss.textContent=`Checkpoint losses on this sample: selection ${sample.losses.selection.toFixed(3)}, rank ${sample.losses.order.toFixed(3)}, Gaussian regularization ${sample.losses.kl.toFixed(3)}.`;target.append(loss);
   }
   render();schedule();
  }
  async function initialize(){
   if(initialized)return;initialized=true;
   const status=root.querySelector('.learning-loading');status.textContent='Preparing recorded samples…';
   try{
    await loadScript('assets/learning-samples.js',()=>!!window.CLEAR_LEARNING_SAMPLES);
    const data=window.CLEAR_LEARNING_SAMPLES;samples=data[root.dataset.kind];
    const xs=samples.map(s=>s.xy[0]),ys=samples.map(s=>s.xy[1]),lo=[Math.min(...xs),Math.min(...ys)],hi=[Math.max(...xs),Math.max(...ys)];
    const svg=root.querySelector('svg');
    dots=samples.map((sample,i)=>{const dot=element('circle',{cx:28+(sample.xy[0]-lo[0])/(hi[0]-lo[0]||1)*424,cy:28+(sample.xy[1]-lo[1])/(hi[1]-lo[1]||1)*294,r:5.5,fill:sample.split==='train'?colors[sample.body]:'#fff',stroke:colors[sample.body],'stroke-width':2,role:'button','aria-label':`Sample ${i+1}, ${sample.body==='g1'?'G1':'Spot plus arm'}, ${sample.split==='train'?'training':'validation'}`});
     dot.addEventListener('focus',()=>select(i));dot.addEventListener('click',()=>select(i));dot.addEventListener('keydown',e=>{if(['ArrowRight','ArrowDown','ArrowLeft','ArrowUp'].includes(e.key)){e.preventDefault();dots[(i+(e.key==='ArrowRight'||e.key==='ArrowDown'?1:samples.length-1))%samples.length].focus();}if(e.key==='Enter'||e.key===' '){e.preventDefault();select(i);}});svg.append(dot);return dot;});
    svg.addEventListener('pointermove',event=>{
     const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(svg.getScreenCTM().inverse());
     let closest=-1,distance=18;
     dots.forEach((dot,i)=>{const d=Math.hypot(point.x-dot.cx.baseVal.value,point.y-dot.cy.baseVal.value);if(d<distance){distance=d;closest=i;}});
     if(closest>=0&&closest!==index)select(closest);
    });
    root.querySelector('.sample-count').textContent=`${samples.filter(s=>s.split==='train').length} training samples and ${samples.filter(s=>s.split==='val').length} validation samples from the inspected maze dataset.`;
    root.querySelector('.sample-projection-note').textContent=`t-SNE of ${data.projection[root.dataset.kind].toLowerCase()}. Each point is an actual dataset sample. The projection shows one checkpoint and does not establish generalization. Rollouts use recorded poses with display interpolation.`;
    root.querySelector('.learning-loss').textContent=root.dataset.kind==='grounding'?'The crossing label is 1 only when the attempt succeeds without collision or a fall. Binary cross entropy compares this target with the predicted probability. Affordance warmup precedes joint updates with plan supervision.':'Binary cross entropy supervises participation. A pairwise ranking loss supervises relative priorities, with Gaussian regularization. The same shared representation also receives motion generation gradients. The displayed losses are checkpoint evaluations, not an optimization history.';
    status.hidden=true;root.querySelector('.learning-content').hidden=false;const preferred=samples.findIndex(s=>s.split==='train'&&(root.dataset.kind==='ordering'?s.paths.length>1:s.target===0));select(preferred<0?0:preferred);
   }catch{initialized=false;status.textContent='Samples are taking longer to load. ';const button=document.createElement('button');button.type='button';button.textContent='Retry samples';button.onclick=initialize;status.append(button);}
  }
  const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible){initialize();schedule();}else{cancelAnimationFrame(frame);frame=0;last=0;}},{rootMargin:'160px'});observer.observe(root);
  document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;}else schedule();});
  play.addEventListener('click',()=>{playing=!playing;render();schedule();});range.addEventListener('input',()=>{progress=+range.value;playing=false;render();});
  root.querySelector('.sample-prev').onclick=()=>select(index-1);root.querySelector('.sample-next').onclick=()=>select(index+1);
  reduced.addEventListener('change',()=>{if(reduced.matches){playing=false;render();}});
 }
})();
