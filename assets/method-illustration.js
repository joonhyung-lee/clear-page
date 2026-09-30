/* Explanatory geometry only. This deliberately does not impersonate a model output. */
(() => {
 const ordering=document.querySelector('#method-order .sequence-explanation');
 const generation=document.querySelector('#method-flow .sequence-explanation');if(!ordering||!generation)return;
 const objects=[{id:0,p:[2,3],selected:false,color:'#bdc7b8'},{id:1,p:[4,2],selected:true,color:'#d9a88c'},{id:2,p:[7,2],selected:true,color:'#9bb6cc'}];
 let time=0,view='2d',mask=false,rank=1;
 const controls=document.createElement('div');controls.className='illustration-controls';
 controls.innerHTML='<div role="group" aria-label="Generation view"><button type="button" data-illustration-view="2d" aria-pressed="true">2D map</button><button type="button" data-illustration-view="3d" aria-pressed="false">3D scene</button></div><label>Flow time <input type="range" min="0" max="1" step=".01" value="0" aria-label="Illustrative flow time"><output>0.00</output></label><button type="button" data-attention-mask aria-pressed="false">Show attention mask</button>';
 generation.querySelector('svg').before(controls);
 const attention=document.createElement('div');attention.className='illustration-attention';attention.hidden=true;
 attention.innerHTML='<label>Current interaction <select aria-label="Current interaction"><option value="1">Object 1</option><option value="2">Object 2</option></select></label><p></p>';
 generation.append(attention);
 const summary=document.createElement('div');summary.className='illustration-order-summary';
 summary.innerHTML='<span>Object 0 · Omit</span><span>Object 1 · Include · score −1.0</span><span>Object 2 · Include · score +0.8</span><strong>Object 1 → Object 2</strong><small>Illustrative scores. Lower scores precede higher scores.</small>';
 ordering.querySelector('svg').after(summary);
 const distribution=document.createElementNS('http://www.w3.org/2000/svg','svg');distribution.setAttribute('viewBox','0 0 800 160');distribution.setAttribute('role','img');distribution.setAttribute('aria-label','Illustrative Gaussian priority distributions for Objects 1 and 2');distribution.classList.add('illustration-priorities');summary.after(distribution);
 let curves='<path d="M70 115H730" stroke="#c5d1be"/><text x="400" y="154" text-anchor="middle">Illustrative priorities · Lower score comes first</text>';
 for(const [id,mu,sigma,color]of [[1,-1,.45,objects[1].color],[2,.8,.6,objects[2].color]]){
  const points=Array.from({length:121},(_,i)=>{const u=-3+i/20;return [70+(u+3)*110,115-70*Math.exp(-.5*((u-mu)/sigma)**2)].join(',');}).join(' ');
  curves+=`<polyline points="${points}" stroke="${color}" fill="none" stroke-width="2"/><circle cx="${70+(mu+3)*110}" cy="45" r="4" fill="${color}"/><text x="${70+(mu+3)*110}" y="25" text-anchor="middle">Object ${id}</text>`;
 }
 for(const u of [-3,-2,-1,0,1,2,3])curves+=`<text x="${70+(u+3)*110}" y="135" text-anchor="middle">${u}</text>`;
 distribution.innerHTML=curves;
 const project=(p,mode)=>mode==='2d'?[55+p[0]*65,230-p[1]*55]:[100+p[0]*54+p[1]*25,245+p[0]*3-p[1]*34-(p[2]||0)*55];
 function scene(mode,flow){
  const xy=p=>project(p,mode),points=ps=>ps.map(p=>xy(p).join(',')).join(' ');
  let svg=`<polygon points="${points([[0,0],[10,0],[10,4],[0,4]])}" fill="#f0f4ed" stroke="#dbe3d5"/>`;
  for(let x=0;x<=10;x++)svg+=`<polyline points="${points([[x,0],[x,4]])}" fill="none" stroke="#e1e7dc"/>`;
  for(let y=0;y<=4;y++)svg+=`<polyline points="${points([[0,y],[10,y]])}" fill="none" stroke="#e1e7dc"/>`;
  svg+=`<polyline points="${points([[.5,2],[9.5,2]])}" fill="none" stroke="#6c8165" stroke-dasharray="5 5"/>`;
  for(const [p,label]of [[[.5,2],'Start'],[[9.5,2],'Goal']]){const q=xy(p);svg+=`<circle cx="${q[0]}" cy="${q[1]}" r="6" fill="#52694b"/><text x="${q[0]}" y="${q[1]+24}" text-anchor="middle">${label}</text>`;}
  function box(p,color,ghost=false){
   const a=.32,bottom=[[-a,-a],[a,-a],[a,a],[-a,a]].map(([x,y])=>[p[0]+x,p[1]+y,0]);
   let result=`<polygon points="${points(bottom)}" fill="${color}" fill-opacity="${ghost?.18:.8}" stroke="${color}" ${ghost?'stroke-dasharray="4 3"':''}/>`;
   if(mode==='3d'){
    const top=bottom.map(([x,y])=>[x,y,.5]);result+=`<polygon points="${points(top)}" fill="${color}" fill-opacity="${ghost?.12:.65}" stroke="${color}"/>`;
    bottom.forEach((p,i)=>{result+=`<polyline points="${points([p,top[i]])}" fill="none" stroke="${color}"/>`;});
   }return result;
  }
  objects.forEach(o=>{
   const faded=mask&&flow&&o.id>rank;const color=faded?'#cbd0c8':o.color;
   svg+=box(o.p,color);const q=xy([...o.p,.7]);svg+=`<text x="${q[0]}" y="${q[1]-10}" text-anchor="middle">${o.id}</text>`;
   if(!o.selected)return;
   const end=[o.p[0],.5],reference=[o.p,[o.p[0],1.5],[o.p[0],1],end];
   const noise=o.id===1?[[3.6,2.2],[4.7,3.1],[3.8,.8],[5.1,1.7]]:[[7.5,1.6],[6.6,2.8],[8.1,1.8],[6.9,.9]];
   const path=flow?reference.map((p,i)=>p.map((v,j)=>noise[i][j]*(1-time)+v*time)):reference;
   svg+=`<polyline points="${points(path)}" fill="none" stroke="${color}" stroke-width="2.5" ${faded?'stroke-dasharray="4 4"':''}/>`;
   path.forEach((p,i)=>{const a=xy(p);svg+=`<circle cx="${a[0]}" cy="${a[1]}" r="4" fill="white" stroke="${color}"><title>Object ${o.id}, anchor ${i}: (${p[0].toFixed(2)}, ${p[1].toFixed(2)})</title></circle>`;});
   svg+=box(path.at(-1),color,true);
  });
  if(mode==='3d')for(const [p,label,color]of [[[1,0,0],'X','#b78778'],[[0,1,0],'Y','#7a9876'],[[0,0,1],'Z','#7a97b0']]){
   const q=xy(p);svg+=`<polyline points="${points([[0,0,0],p])}" stroke="${color}" stroke-width="2"/><text x="${q[0]}" y="${q[1]-5}" fill="${color}">${label}</text>`;
  }return svg;
 }
 function draw(){
  ordering.querySelector('svg').setAttribute('viewBox','0 0 800 300');ordering.querySelector('svg').innerHTML=scene('2d',false);
  generation.querySelector('svg').setAttribute('viewBox','0 0 800 300');generation.querySelector('svg').innerHTML=scene(view,true);
  generation.dataset.flowTime=time.toFixed(2);generation.dataset.view=view;
  controls.querySelector('output').textContent=time.toFixed(2);
  attention.querySelector('p').textContent=rank===1?'Object 1 reads the scene context. Object 2 is a later interaction and is masked.':'Object 2 reads the scene context and Object 1’s generated reference.';
 }
 controls.querySelector('input').oninput=e=>{time=Number(e.target.value);draw();};
 controls.querySelectorAll('[data-illustration-view]').forEach(button=>button.onclick=()=>{view=button.dataset.illustrationView;controls.querySelectorAll('[data-illustration-view]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));draw();});
 controls.querySelector('[data-attention-mask]').onclick=e=>{mask=!mask;e.currentTarget.setAttribute('aria-pressed',String(mask));attention.hidden=!mask;draw();};
 attention.querySelector('select').onchange=e=>{rank=Number(e.target.value);draw();};
 generation.querySelector('p').textContent='Hand-drawn paths explain noise-to-reference generation and rank dependencies. This is not a learned prediction. Flow time is distinct from physical execution time.';
 draw();
})();
