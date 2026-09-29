/* Scalar priority distributions and saved draws. No object motion is implied. */
(() => {
 const colors=['#80a3af','#c99e7c','#91ae80','#ad9dc0'];
 const ns='http://www.w3.org/2000/svg';
 function node(name,attributes={},text){const n=document.createElementNS(ns,name);for(const[k,v]of Object.entries(attributes))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n;}
 window.clearOrderingPlot=function(host,d,trace=null){
  host.replaceChildren();host.classList.add('ordering-distribution');
  const n=d.mu.length,width=560,height=86+n*76,svg=node('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':trace?'Predicted priority distributions and recorded sampled priorities':'Predicted priority distributions and reference ranks'});
  const values=d.mu.flatMap((v,i)=>[v-3*d.sigma[i],v+3*d.sigma[i],trace?.priority[i]??v]);
  const low=Math.floor(Math.min(...values)),high=Math.ceil(Math.max(...values)),span=high-low||1,x=v=>170+(v-low)/span*260;
  svg.append(node('text',{x:16,y:24},'Object selection'),node('text',{x:170,y:24},'Priority distribution'),node('text',{x:460,y:24},trace?'Rank':'Target'));
  d.mu.forEach((mu,i)=>{
   const y=78+i*76,color=colors[i%colors.length],rank=trace?trace.rank[i]:d.rank[i];
   const row=node('g',{'data-object':i,tabindex:0,'aria-label':'Inspect Object '+i});row.append(node('rect',{x:16,y:y-28,width:9,height:33,fill:color}),node('text',{x:34,y:y-12},'Object '+i),node('text',{x:34,y:y+8,class:'ordering-small'},(d.selection[i]<.001?'<0.1':d.selection[i]>.999?'>99.9':(d.selection[i]*100).toFixed(1))+'% selected'));
   const points=Array.from({length:101},(_,j)=>{const value=low+span*j/100;return[x(value),y-33*Math.exp(-.5*((value-mu)/d.sigma[i])**2)];});
   row.append(node('path',{d:`M ${x(low)} ${y} `+points.map(p=>'L '+p.join(' ')).join(' ')+` L ${x(high)} ${y} Z`,fill:color,'fill-opacity':.18,stroke:color,'stroke-width':1.5}));
   const p=trace?trace.priority[i]:mu;
   row.append(node('line',{x1:x(p),x2:x(p),y1:y-39,y2:y+6,stroke:color,'stroke-width':1.7,'stroke-dasharray':trace?'':'3 3'}));
   if(trace)row.append(node('circle',{cx:x(p),cy:y-39,r:5,fill:'#fff',stroke:color,'stroke-width':2}));
   row.append(node('text',{x:460,y:y-9},rank<0?'Omit':String(rank+1)),node('text',{x:460,y:y+12,class:'ordering-small'},trace?'u = '+p.toFixed(2):'reference'));svg.append(row);
  });
  const baseline=height-30;
  for(let i=0;i<=4;i++){const v=low+span*i/4;svg.append(node('text',{x:x(v),y:baseline,'text-anchor':'middle',class:'ordering-small'},v.toFixed(1)));}
  svg.append(node('text',{x:300,y:height-7,'text-anchor':'middle',class:'ordering-small'},'Lower priority comes first'));host.append(svg);
  const ranks=trace?trace.rank:d.rank,order=ranks.map((rank,i)=>({rank,i})).filter(x=>x.rank>=0).sort((a,b)=>a.rank-b.rank);
  const sequence=document.createElement('div');sequence.className='ordering-sequence';sequence.setAttribute('aria-label',trace?'Sampled interaction order':'Reference interaction order');
  const label=document.createElement('span');label.textContent=trace?'Sampled order':'Reference order';sequence.append(label);
  if(!order.length){const empty=document.createElement('strong');empty.textContent='No interaction';sequence.append(empty);}
  order.forEach((o,k)=>{if(k){const arrow=document.createElement('span');arrow.textContent='→';sequence.append(arrow);}const token=document.createElement('strong');token.style.borderColor=colors[o.i%colors.length];token.textContent='Object '+o.i;sequence.append(token);});host.append(sequence);
 };
 const layout=document.querySelector('.maze-order-layout'),d=window.CLEAR_MAZE_TRACE;if(!layout||!d)return;
 const chart=document.createElement('div');chart.className='ordering-main';chart.innerHTML='<h4>Sample priorities, then sort the selected objects</h4><div class="ordering-plot"></div><p class="figure-caption">Curves show the learned Gaussian priorities. Dots mark one saved draw. All four saved draws produce the same order.</p>';
 const context=layout.querySelector('#context-formation');if(context)context.after(chart);else layout.prepend(chart);
 const readout=layout.querySelector('.maze-order-readout'),result=readout.querySelector('#maze-order-result');result.hidden=true;
 chart.append(readout.querySelector('.control-row'));
 const details=document.createElement('details');details.className='ordering-spatial method-details';const summary=document.createElement('summary');summary.textContent='Inspect the spatial context and numeric predictions';details.append(summary);const columns=document.createElement('div');columns.className='ordering-spatial-columns';columns.append(layout.querySelector('.viewer'),readout);details.append(columns);layout.append(details);
 function draw(){const sample=Number(layout.querySelector('.viewer').dataset.orderSample||0);window.clearOrderingPlot(chart.querySelector('.ordering-plot'),d,d.traces[sample]);chart.dataset.sample=sample;}
 document.addEventListener('clear-order-draw',draw);draw();
 const play=document.createElement('button');play.type='button';play.className='order-draw-play';play.textContent='Play saved draws';play.setAttribute('aria-pressed','false');chart.querySelector('.control-row').prepend(play);
 let enabled=false,visible=false,last=0;
 play.onclick=()=>{enabled=!enabled;last=performance.now();play.textContent=enabled?'Pause saved draws':'Play saved draws';play.setAttribute('aria-pressed',String(enabled));};
 new IntersectionObserver(e=>{visible=e[0].isIntersecting;last=performance.now();}).observe(chart);
 const timer=setInterval(()=>{if(enabled&&visible&&!document.hidden&&performance.now()-last>2200){document.querySelector('#maze-order-next').click();last=performance.now();}},200);
 window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
})();
