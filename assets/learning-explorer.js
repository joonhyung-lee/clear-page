/* Recorded samples and checkpoint features, loaded once for both explorers. */
(() => {
 const colors={g1:'#347b92',spot_arm:'#a76c38'},objects=['#adcfd5','#e8c5ad','#bfd5b1','#d0bfda'];
 const ns='http://www.w3.org/2000/svg';
 const terrainColors={flat:'#728f9e',stairs:'#bf8c69',mixed:'#8e81aa',ramp:'#769a7d',slalom:'#a48b67',branch:'#6f9b86'};
 const terrainLabel={flat:'Flat maze',stairs:'Stair terrain',mixed:'Mixed terrain',ramp:'Ramp terrain',slalom:'Alternating passages',branch:'Branching maze'};
 function terrainGroup(sample){if(sample.layout==='Alternating passages')return 'slalom';if(sample.layout==='Branching maze')return 'branch';const kinds=new Set(sample.scene.terrain.map(t=>t.kind).filter(k=>k!=='flat'));return kinds.size>1?'mixed':kinds.has('ramp')?'ramp':kinds.size?'stairs':'flat';}

 const splitLabel=sample=>sample.queryOnly?'Scene query':sample.split==='train'?'Training':sample.split==='evaluation'?'Evaluation replay':'Validation';
 function element(name,attrs){const el=document.createElementNS(ns,name);for(const [key,value]of Object.entries(attrs))el.setAttribute(key,value);return el;}
 for(const root of document.querySelectorAll('.learning-explorer')){
  let initialized=false,visible=false,playing=false,index=0,progress=0,last=0,frame=0,samples=[],dots=[],filter='all',colorBy='terrain';
  const canvas=root.querySelector('canvas'),ctx=canvas.getContext('2d'),range=root.querySelector('.sample-progress'),play=root.querySelector('.sample-play');
  const grid=root.querySelector('.sample-explorer-grid');
  let mediaTimer, movieVisible=false;
  const movie=root.dataset.kind==='grounding'?document.createElement('video'):null;
  if(movie){movie.className='sample-video';movie.muted=true;movie.loop=true;movie.playsInline=true;movie.preload='metadata';movie.setAttribute('aria-label','Recorded physical robot attempt');canvas.before(movie);movie.after(root.querySelector('.sample-controls'));const map=document.createElement('div');map.className='sample-map-details';const title=document.createElement('h5');title.textContent='Trajectory map';map.append(title);canvas.after(map);map.append(canvas);movie.addEventListener('loadeddata',()=>{if(movieVisible&&playing&&!document.hidden)movie.play().catch(()=>{});});}

  const factors=document.createElement('div');factors.className='sample-factors';factors.setAttribute('role','group');factors.setAttribute('aria-label','Match observed inputs to dataset points');
  const factorNote=document.createElement('p');factorNote.className='sample-factor-note';
  root.querySelector('.sample-scatter').before(factors,factorNote);
  const signature=(sample,key)=>JSON.stringify(key==='body'?[sample.body,sample.links]:key==='objects'?sample.scene.objects:key==='scene'?[sample.scene.walls,sample.scene.terrain]:sample.query||[sample.scene.start,sample.scene.goal]);
  function highlightFactor(key){
   const sample=samples[index];if(!sample)return;
   root.dataset.factor=key||'';let count=0;
   dots.forEach((dot,i)=>{const same=!!key&&signature(samples[i],key)===signature(sample,key);if(same)count++;dot.classList.toggle('factor-match',same);dot.classList.toggle('factor-unmatched',!!key&&!same);});
   root.dataset.factorMatches=String(count);
   factorNote.textContent=key?count+' points share this '+({body:'body structure',objects:'object configuration',scene:'scene geometry',query:'query'}[key])+'.': 'Hover or focus an input to outline matching samples. Each point encodes the combined inputs. The t-SNE axes do not represent individual factors.';
  }
  function inputFactors(sample){
   factors.replaceChildren();
   const point=p=>p?`(${p.slice(0,2).map(v=>v.toFixed(1)).join(', ')})`:'Recorded start';
   const query=sample.query||[sample.scene.start,sample.scene.goal];
   const items=[['body','Body',`${sample.body==='g1'?'G1':'Spot + arm'} · ${sample.links} links`],['objects','Objects',`${sample.scene.objects.length} objects`],['scene','Scene',`${sample.scene.terrain.length} terrain patches · ${sample.scene.walls.length} walls`],['query',sample.query?'Query':'Start → goal',`${point(query[0])} → ${point(query[1])}`]];
   for(const [key,label,value] of items){const button=document.createElement('button');button.type='button';button.dataset.factor=key;const name=document.createElement('span'),detail=document.createElement('strong');name.textContent=label;detail.textContent=value;button.append(name,detail);button.onpointerenter=button.onfocus=()=>highlightFactor(key);button.onpointerleave=()=>{if(document.activeElement!==button)highlightFactor(null);};button.onblur=()=>highlightFactor(null);button.onclick=()=>highlightFactor(key);factors.append(button);}
   highlightFactor(null);
  }

  if(movie)new IntersectionObserver(entries=>{movieVisible=entries.at(-1).isIntersecting;if(movieVisible&&playing&&!document.hidden)movie.play().catch(()=>{});else movie.pause();}).observe(movie.closest('.sample-inspector'));
  let objectFocus=null;
  if(root.dataset.kind==='ordering'){
   const legend=document.createElement('p');legend.className='sample-map-legend';legend.textContent='Dashed green: recorded route · Colored objects: reference interactions';canvas.after(legend);
   canvas.addEventListener('pointermove',event=>{const r=canvas.getBoundingClientRect(),x=(event.clientX-r.left)*canvas.width/r.width,y=(event.clientY-r.top)*canvas.height/r.height;const hit=(canvas._objectHits||[]).find(p=>Math.hypot(x-p.x,y-p.y)<24);objectFocus=hit?.i??null;render();});
   canvas.addEventListener('pointerleave',()=>{objectFocus=null;render();});
  }
  const connector=element('svg',{'class':'sample-connector','aria-hidden':'true'}),leader=element('path',{'class':'sample-leader',fill:'none'}),outline=element('path',{'class':'sample-view-outline',fill:'none'});
  const defs=element('defs',{}),mask=element('mask',{id:'sample-reveal-'+root.dataset.kind}),reveal=element('path',{fill:'none',stroke:'white','stroke-width':7,pathLength:1});
  const arrow=element('marker',{id:'sample-arrow-'+root.dataset.kind,viewBox:'0 0 8 8',refX:7,refY:4,markerWidth:6,markerHeight:6,orient:'auto'});arrow.append(element('path',{d:'M 1 1 L 7 4 L 1 7',fill:'none',stroke:'#748d80','stroke-width':1.2}));
  mask.append(reveal);defs.append(mask,arrow);connector.append(defs,leader,outline);leader.setAttribute('mask','url(#sample-reveal-'+root.dataset.kind+')');leader.setAttribute('marker-end','url(#sample-arrow-'+root.dataset.kind+')');grid.append(connector);
  const phaseLabel=document.createElement('p');phaseLabel.className='sample-phase';canvas.after(phaseLabel);
  function connect(animate=false){
   if(!dots[index]||!visible)return;
   const bounds=grid.getBoundingClientRect(),a=dots[index].getBoundingClientRect(),b=(movie||canvas).getBoundingClientRect();
   connector.setAttribute('viewBox',`0 0 ${bounds.width} ${bounds.height}`);
   const x=a.x+a.width/2-bounds.x,y=a.y+a.height/2-bounds.y,l=b.x-bounds.x,t=b.y-bounds.y,r=l+b.width,bottom=t+b.height;
   const stacked=b.y>a.bottom+30,tx=stacked?r-24:l,ty=stacked?t:t+Math.min(70,b.height/3),lane=bounds.width+8;
   const path=stacked?`M ${x} ${y} C ${lane} ${y} ${lane} ${y+24} ${lane} ${y+48} L ${lane} ${ty-20} Q ${lane} ${ty-8} ${tx} ${ty}`:`M ${x} ${y} C ${x+40} ${y} ${tx-32} ${ty} ${tx} ${ty}`;
   leader.setAttribute('d',path);reveal.setAttribute('d',path);reveal.style.strokeDasharray='1';reveal.style.strokeDashoffset='0';
   const n=14;outline.setAttribute('d',`M ${l} ${t+n} V ${t} H ${l+n} M ${r-n} ${t} H ${r} V ${t+n} M ${r} ${bottom-n} V ${bottom} H ${r-n} M ${l+n} ${bottom} H ${l} V ${bottom-n}`);
   if(animate&&!reduced.matches)reveal.animate([{strokeDashoffset:1},{strokeDashoffset:0}],{duration:650,easing:'ease-out'});
  }
  new ResizeObserver(()=>{connect();if(root.dataset.kind==='ordering')render();}).observe(grid);
  function matches(sample){return filter==='all'||sample.body===filter||(filter==='query'&&sample.queryOnly)||(filter==='evaluation'&&sample.split==='evaluation')||(filter==='stairs'&&sample.scene.terrain.length>0)||(filter==='flat'&&!sample.scene.terrain.length)||(filter==='safe'&&sample.target===1)||(filter==='blocked'&&sample.target===0)||(filter==='interaction'&&sample.paths?.length>0);}
  function path(points,color,width=2,dash=[]){if(!points.length)return;ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();ctx.setLineDash([]);}
  function dot(x,y,r,color){ctx.beginPath();ctx.arc(x,y,r,0,2*Math.PI);ctx.fillStyle=color;ctx.fill();ctx.strokeStyle='#3d4746';ctx.lineWidth=1;ctx.stroke();}
  function render(){
   if(!samples.length)return;const sample=samples[index],scene=sample.scene,frames=sample.rollout;
   if(root.dataset.kind==='ordering'){
    const state=window.clearOrderingMap(canvas,sample,progress,objectFocus);range.value=progress;root.querySelector('.sample-time').textContent=sample.queryOnly?'Not executed':state.time.toFixed(1)+' s';play.textContent=sample.queryOnly?'Static query':playing?'Pause route':'Play route';phaseLabel.textContent=sample.queryOnly?'Predicted object paths. No execution outcome is available.':'';return;
   }
   const minT=frames[0][0],maxT=frames.at(-1)[0],time=minT+progress*(maxT-minT);
   let k=frames.findIndex(f=>f[0]>=time);if(k<0)k=frames.length-1;
   const a=frames[Math.max(0,k-1)],b=frames[k],t=b[0]===a[0]?0:(time-a[0])/(b[0]-a[0]);
   const mix=(x,y)=>x+(y-x)*t,angle=(x,y)=>x+Math.atan2(Math.sin(y-x),Math.cos(y-x))*t;
   const isProbe=!!sample.query;
   const points=isProbe?[...frames.map(f=>f.slice(1,3)),...sample.query]:[[0,0],scene.world_size];
   let left=Math.min(...points.map(p=>p[0])),right=Math.max(...points.map(p=>p[0])),bottom=Math.min(...points.map(p=>p[1])),top=Math.max(...points.map(p=>p[1]));
   if(isProbe){left-=.65;right+=.65;bottom-=.65;top+=.65;}
   const viewHeight=isProbe?272:390,scale=Math.min(490/(right-left), (viewHeight-42)/(top-bottom)),ox=(560-(right-left)*scale)/2-left*scale,oy=(viewHeight+(top-bottom)*scale)/2+bottom*scale;
   const xy=p=>[ox+p[0]*scale,oy-p[1]*scale];ctx.clearRect(0,0,560,390);ctx.fillStyle='#fafbf9';ctx.fillRect(0,0,560,390);ctx.save();ctx.beginPath();ctx.rect(0,0,560,viewHeight);ctx.clip();
   for(const tile of scene.terrain){const [l,b,r,t]=tile.bounds;ctx.fillStyle=tile.kind==='ramp'?'#e3eadd':'#eee9df';ctx.fillRect(ox+l*scale,oy-t*scale,(r-l)*scale,(t-b)*scale);ctx.strokeStyle='#d2cec3';ctx.lineWidth=.8;ctx.strokeRect(ox+l*scale,oy-t*scale,(r-l)*scale,(t-b)*scale);if(isProbe&&(r-l)*scale>30){ctx.fillStyle='#827b6c';ctx.font='11px Arial';const height=tile.height_m??tile.end_height_m??0;ctx.fillText(height.toFixed(2)+' m',ox+l*scale+3,Math.max(18,oy-(t+b)/2*scale));}}
   for(const [l,b,r,t]of scene.walls){ctx.fillStyle='#c9cdca';ctx.fillRect(ox+l*scale,oy-t*scale,(r-l)*scale,(t-b)*scale);}
   if(sample.paths)for(const p of sample.paths){const points=p.poses.map(xy);path(points,objects[p.object%4],3,[5,4]);for(let j=0;j<5;j++){const v=points[Math.round(j*(points.length-1)/4)];dot(...v,3.1,objects[p.object%4]);}}
   path(frames.map(f=>xy(f.slice(1,3))),'#dce4df',2,[4,4]);path(frames.slice(0,k+1).map(f=>xy(f.slice(1,3))),colors[sample.body],3);
   if(sample.query){path(sample.query.map(xy),'#566360',2,[4,4]);sample.query.forEach(p=>dot(...xy(p),4,'#fff'));}
   dot(...xy(scene.goal),5,'#fff');ctx.fillStyle='#59615c';ctx.font='12px Arial';ctx.fillText('Goal',xy(scene.goal)[0]+8,xy(scene.goal)[1]+4);
   scene.objects.forEach((obj,j)=>{const pose=a[4][j].map((v,d)=>d===2?angle(v,b[4][j][d]):mix(v,b[4][j][d])),pos=xy(pose);ctx.save();ctx.translate(...pos);ctx.rotate(-pose[2]);ctx.fillStyle=objects[j%4];ctx.strokeStyle='#606b65';ctx.lineWidth=1;ctx.fillRect(-obj.size[0]*scale/2,-obj.size[1]*scale/2,obj.size[0]*scale,obj.size[1]*scale);ctx.strokeRect(-obj.size[0]*scale/2,-obj.size[1]*scale/2,obj.size[0]*scale,obj.size[1]*scale);ctx.restore();});
   const robot=xy([mix(a[1],b[1]),mix(a[2],b[2])]);ctx.save();ctx.translate(...robot);ctx.rotate(-angle(a[3],b[3]));ctx.fillStyle=colors[sample.body];ctx.strokeStyle='#354740';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(9,0);ctx.lineTo(-6,-5);ctx.lineTo(-6,5);ctx.closePath();ctx.fill();ctx.stroke();ctx.restore();
   ctx.restore();
   if(isProbe){
    ctx.fillStyle='#f3f5f0';ctx.fillRect(0,282,560,108);ctx.fillStyle='#56635b';ctx.font='12px Arial';ctx.fillText('Recorded base height',16,302);
    const minZ=Math.min(...frames.map(f=>f[5]??0)),maxZ=Math.max(...frames.map(f=>f[5]??0)),zspan=Math.max(.3,maxZ-minZ);
    const hx=f=>42+(f[0]-minT)/(maxT-minT||1)*476,hy=f=>371-((f[5]??0)-minZ)/zspan*54;
    if(sample.evidenceInterval){const [begin,end]=sample.evidenceInterval;ctx.fillStyle='#dce9de';ctx.fillRect(hx([Math.max(begin,minT)]),310,(Math.min(end,maxT)-Math.max(begin,minT))/(maxT-minT||1)*476,70);}
    path(frames.map(f=>[hx(f),hy(f)]),'#aab8ae',1.5);path(frames.slice(0,k+1).map(f=>[hx(f),hy(f)]),colors[sample.body],2.5);dot(hx([time]),hy([time,0,0,0,[],mix(a[5]??0,b[5]??0)]),4,'#fff');
    ctx.fillStyle='#56635b';ctx.fillText(minZ.toFixed(2)+' m',16,386);ctx.fillText(maxZ.toFixed(2)+' m',16,321);
   }
   const interval=sample.evidenceInterval,phase=interval?(time<interval[0]?'Recorded approach':time<=interval[1]?'Labeled crossing':'Recorded continuation'):'Recorded reference rollout';
   phaseLabel.textContent=phase+(interval?` · label interval ${interval[0].toFixed(1)}–${interval[1].toFixed(1)} s`:'');
   range.value=progress;root.querySelector('.sample-time').textContent=time.toFixed(1)+' s';play.textContent=playing?'Pause rollout':'Play rollout';
  }
  function tick(now){frame=0;if(!visible||!playing||!initialized||document.hidden||samples[index]?.queryOnly)return;const f=samples[index]?.rollout;if(!f)return;const duration=Math.max(3,Math.min(22,f.at(-1)[0]-f[0][0]));if(movie){if(movie.readyState>=2)progress=Math.min(1,movie.currentTime/(f.at(-1)[0]-f[0][0]||1));}else if(last)progress=(progress+(now-last)/(duration*1000))%1;last=now;render();frame=requestAnimationFrame(tick);}
  function schedule(){if(!frame&&visible&&!document.hidden&&playing&&initialized&&!samples[index]?.queryOnly){last=0;frame=requestAnimationFrame(tick);}}
  function select(i){
   index=(i+samples.length)%samples.length;progress=0;const sample=samples[index];play.disabled=range.disabled=!!sample.queryOnly;
   if(root.dataset.kind==='ordering')root.querySelector('.sample-map-legend').textContent=sample.queryOnly?'Colored paths: model predictions · Objects remain at their observed positions':'Dashed green: recorded route · Colored objects: reference interactions';
   if(movie){clearTimeout(mediaTimer);movie.pause();movie.removeAttribute('src');movie.load();const file='assets/media/attempts/attempt-'+String(index).padStart(3,'0');movie.poster=clearAssetURL(file+'.png');mediaTimer=setTimeout(()=>{movie.src=clearAssetURL(file+'.mp4');movie.load();},150);}

   dots.forEach((dot,j)=>{dot.classList.toggle('selected',j===index);dot.setAttribute('tabindex',j===index?'0':'-1');dot.setAttribute('aria-pressed',String(j===index));});
   root.querySelector('.sample-title').textContent=`Sample ${index+1} · ${sample.body==='g1'?'G1':'Spot + arm'} · ${splitLabel(sample)}`;
   root.querySelector('.sample-inputs').textContent=`${terrainLabel[terrainGroup(sample)]} · ${sample.links} body links · ${sample.scene.objects.length} objects`+(sample.scope?' · '+sample.scope:'');
   inputFactors(sample);
   const target=root.querySelector('.sample-target');target.replaceChildren();
   if(root.dataset.kind==='grounding'){
    const p=document.createElement('p');p.textContent=`Predicted safe crossing: ${(100*sample.prediction).toFixed(1)}%`;target.append(p);
    if(sample.outcome){const outcome=document.createElement('p');outcome.textContent='Observed: '+(sample.outcome.fell?'Fall':sample.outcome.collision?'Collision':sample.outcome.success?'Safe crossing':'Incomplete');target.append(outcome);}
   }else{
    const sequence=document.createElement('div');sequence.className='sample-route-order';
    const label=document.createElement('span');label.textContent=sample.queryOnly?(sample.paths.length?'Predicted interaction order':'No interaction sampled'):sample.paths.length?'Move along the route':'Route needs no object interaction';sequence.append(label);
    sample.paths.forEach((path,j)=>{const button=document.createElement('button');button.type='button';button.textContent=(j+1)+'. Object '+path.object;button.onclick=()=>{objectFocus=path.object;if(sample.queryOnly){render();return;}let k=1;while(k<sample.rollout.length&&Math.hypot(sample.rollout[k][4][path.object][0]-sample.rollout[0][4][path.object][0],sample.rollout[k][4][path.object][1]-sample.rollout[0][4][path.object][1])<.025)k++;k=Math.min(k,sample.rollout.length-1);progress=(sample.rollout[k][0]-sample.rollout[0][0])/(sample.rollout.at(-1)[0]-sample.rollout[0][0]);playing=false;render();};sequence.append(button);});target.append(sequence);
    const table=document.createElement('table');table.innerHTML='<thead><tr><th>Object</th><th>Selection probability</th><th>Priority μ ± σ</th></tr></thead>';const body=document.createElement('tbody');
    sample.rank.forEach((rank,j)=>{const row=document.createElement('tr');for(const value of [sample.scene.objects[j].object_id,(sample.selection[j]<.001?'<0.1':sample.selection[j]>.999?'>99.9':(100*sample.selection[j]).toFixed(1))+'%',sample.mu[j].toFixed(2)+' ± '+sample.sigma[j].toFixed(2)]){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}body.append(row);});table.append(body);const details=document.createElement('div'),summary=document.createElement('h5');summary.textContent='Model predictions';details.append(summary,table);target.append(details);

   }
   render();connect(true);schedule();
  }
  async function initialize(){
   if(initialized)return;initialized=true;
   const status=root.querySelector('.learning-loading');status.textContent='Preparing scene samples…';
   try{
    if(root.dataset.kind==='ordering')await loadScript('assets/ordering-map.js',()=>!!window.clearOrderingMap);
    await loadScript('assets/learning-samples.js',()=>!!window.CLEAR_LEARNING_SAMPLES);
    const data=window.CLEAR_LEARNING_SAMPLES;samples=data[root.dataset.kind];
    const xs=samples.map(s=>s.xy[0]),ys=samples.map(s=>s.xy[1]),lo=[Math.min(...xs),Math.min(...ys)],hi=[Math.max(...xs),Math.max(...ys)];
    const svg=root.querySelector('.sample-scatter');
    const colorControls=document.createElement('div');colorControls.className='sample-color-controls';
    const colorLabel=document.createElement('label');colorLabel.textContent='Color by ';
    const colorSelect=document.createElement('select');colorSelect.setAttribute('aria-label','Color embedding points by');
    for(const [key,label]of [['terrain','Scene type'],['body','Robot body']]){const option=document.createElement('option');option.value=key;option.textContent=label;colorSelect.append(option);}
    colorLabel.append(colorSelect);const legend=document.createElement('div');legend.className='sample-color-legend';
    const meaning=document.createElement('p');meaning.className='sample-embedding-note';meaning.textContent='Each point is one '+(root.dataset.kind==='grounding'?'recorded crossing query':'planning query')+'. Nearby points have similar learned features. Filled: training. Outlined: validation. Dashed: evaluation.'+(root.dataset.kind==='ordering'?' Dotted: new scene query without execution.':'');
    colorControls.append(colorLabel,legend);svg.before(colorControls);svg.after(meaning);
    function recolor(){
     const palette=colorBy==='terrain'?terrainColors:colors;
     const key=sample=>colorBy==='terrain'?terrainGroup(sample):sample.body;
     dots.forEach((dot,i)=>{const color=palette[key(samples[i])];dot.setAttribute('stroke',color);dot.setAttribute('fill',samples[i].split==='train'?color:'#fff');});
     legend.replaceChildren();
     for(const group of [...new Set(samples.map(key))]){const item=document.createElement('span'),swatch=document.createElement('i');swatch.style.backgroundColor=palette[group];item.append(swatch,document.createTextNode((colorBy==='terrain'?terrainLabel[group]:group==='g1'?'G1':'Spot + arm')+' · '+samples.filter(s=>key(s)===group).length));legend.append(item);}
    }
    colorSelect.onchange=()=>{colorBy=colorSelect.value;recolor();};
    svg.setAttribute('viewBox','0 0 480 350');
    const axis=element('g',{'aria-hidden':'true','pointer-events':'none'});
    for(let i=0;i<=4;i++){
     const x=52+i*98,y=300-i*67;
     axis.append(element('line',{x1:x,x2:x,y1:32,y2:300,class:'sample-axis-grid'}),element('line',{x1:52,x2:444,y1:y,y2:y,class:'sample-axis-grid'}));
     const tx=element('text',{x,y:317,'text-anchor':'middle',class:'sample-axis-tick'}),ty=element('text',{x:43,y:y+3,'text-anchor':'end',class:'sample-axis-tick'});
     tx.textContent=(lo[0]+i*(hi[0]-lo[0])/4).toFixed(1);ty.textContent=(lo[1]+i*(hi[1]-lo[1])/4).toFixed(1);axis.append(tx,ty);
    }
    const xlabel=element('text',{x:248,y:340,'text-anchor':'middle',class:'sample-axis-label'}),ylabel=element('text',{x:16,y:166,transform:'rotate(-90 16 166)','text-anchor':'middle',class:'sample-axis-label'});
    xlabel.textContent='t-SNE dimension 1';ylabel.textContent='t-SNE dimension 2';axis.append(xlabel,ylabel);svg.append(axis);
    dots=samples.map((sample,i)=>{const dot=element('circle',{cx:52+(sample.xy[0]-lo[0])/(hi[0]-lo[0]||1)*392,cy:300-(sample.xy[1]-lo[1])/(hi[1]-lo[1]||1)*268,r:5.5,fill:sample.split==='train'?colors[sample.body]:'#fff',stroke:colors[sample.body],'stroke-width':2,'stroke-dasharray':sample.queryOnly?'1 3':sample.split==='evaluation'?'2 2':'none',role:'button','aria-label':`Sample ${i+1}, ${sample.body==='g1'?'G1':'Spot plus arm'}, ${splitLabel(sample).toLowerCase()}`});
     const title=element('title',{});title.textContent=`Sample ${i+1} · ${sample.layout||terrainLabel[terrainGroup(sample)]} · ${sample.body==='g1'?'G1':'Spot + arm'} · ${sample.scene.objects.length} objects · ${splitLabel(sample)}`;dot.append(title);dot.setAttribute('aria-label',title.textContent);dot.addEventListener('focus',()=>select(i));dot.addEventListener('click',()=>select(i));dot.addEventListener('keydown',e=>{if(['ArrowRight','ArrowDown','ArrowLeft','ArrowUp'].includes(e.key)){e.preventDefault();advance(e.key==='ArrowRight'||e.key==='ArrowDown'?1:-1);dots[index].focus();}if(e.key==='Enter'||e.key===' '){e.preventDefault();select(i);}});svg.append(dot);return dot;});
    recolor();
    svg.addEventListener('pointermove',event=>{
     const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(svg.getScreenCTM().inverse());
     let closest=-1,distance=18;
     dots.forEach((dot,i)=>{if(!matches(samples[i]))return;const d=Math.hypot(point.x-dot.cx.baseVal.value,point.y-dot.cy.baseVal.value);if(d<distance){distance=d;closest=i;}});
     if(closest>=0&&closest!==index)select(closest);
    });
    const layouts=new Set(samples.map(s=>JSON.stringify([s.scene.walls,s.scene.terrain,s.scene.objects]))).size,heights=samples.flatMap(s=>s.scene.terrain.map(t=>t.height_m??t.end_height_m??0));
    const queryCount=samples.filter(s=>s.queryOnly).length;root.querySelector('.sample-count').textContent=queryCount?`${samples.length-queryCount} recorded samples + ${queryCount} scene queries · ${layouts} scene layouts`:`${samples.length} samples · ${layouts} scene layouts`;
    const filters=document.createElement('div');filters.className='sample-filters';filters.setAttribute('role','group');filters.setAttribute('aria-label','Filter scene samples');
    const options=[['all','All samples'],['g1','G1'],['spot_arm','Spot + arm'],['stairs','Terrain scenes'],['flat','Flat scenes'],...(root.dataset.kind==='grounding'?[['safe','Safe'],['blocked','Failed crossing']]:[['interaction','Object interaction'],['evaluation','Evaluation replay'],['query','Scene queries']])];
    for(const [key,label]of options){const button=document.createElement('button');button.type='button';button.textContent=label;button.setAttribute('aria-pressed',String(key===filter));button.onclick=()=>{filter=key;filters.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));dots.forEach((dot,i)=>{dot.classList.toggle('filtered',!matches(samples[i]));dot.setAttribute('aria-disabled',String(!matches(samples[i])));});const next=samples.findIndex(matches);if(next>=0)select(next);};filters.append(button);}
    svg.before(filters);
    status.hidden=true;root.querySelector('.learning-content').hidden=false;const preferred=samples.findIndex(s=>s.split==='train'&&(root.dataset.kind==='ordering'?s.paths.length>1:s.target===1&&Math.max(...s.rollout.map(f=>f[5]))-Math.min(...s.rollout.map(f=>f[5]))>.3));select(preferred<0?0:preferred);
   }catch{initialized=false;status.textContent='Samples are taking longer to load. ';const button=document.createElement('button');button.type='button';button.textContent='Retry samples';button.onclick=initialize;status.append(button);}
  }
  const observer=new IntersectionObserver(entries=>{visible=entries.at(-1).isIntersecting;root.classList.toggle('is-visible',visible);if(visible){initialize();connect();schedule();if(movie&&movieVisible&&playing&&movie.readyState>=2)movie.play().catch(()=>{});}else{cancelAnimationFrame(frame);frame=0;last=0;movie?.pause();}},{rootMargin:'0px'});observer.observe(root);
  document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;movie?.pause();}else{schedule();if(movie&&movieVisible&&playing)movie.play().catch(()=>{});}});
  play.addEventListener('click',()=>{playing=!playing;if(movie){if(playing&&movieVisible)movie.play().catch(()=>{});else movie.pause();}render();schedule();});range.addEventListener('input',()=>{progress=+range.value;playing=false;if(movie){movie.pause();const f=samples[index].rollout;if(movie.readyState)movie.currentTime=progress*(f.at(-1)[0]-f[0][0]);}render();});
  function advance(direction){for(let step=1;step<=samples.length;step++){const i=(index+direction*step+samples.length)%samples.length;if(matches(samples[i])){select(i);break;}}}
  root.querySelector('.sample-prev').onclick=()=>advance(-1);root.querySelector('.sample-next').onclick=()=>advance(1);
  reduced.addEventListener('change',()=>{if(reduced.matches){playing=false;movie?.pause();render();}});
 }
})();
