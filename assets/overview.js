(() => {
  const root = document.querySelector('#clear-overview');
  if (!root) return;
  const stages = {
    grounding: ['Ground the scene in the robot’s body.', 'Structure, object states, and scene geometry form a planning context that represents the robot’s capabilities and accessible interactions.', 'method-grounding'],
    ordering: ['Choose what to move, then in which order.', 'OrderNet uses the planning context to select objects and sample interaction priorities. Sorting the selected priorities gives a candidate order.', 'method-order'],
    generation: ['Generate motion conditioned on the context and order.', 'CausalFlowNet generates continuous object targets. Rank causal attention allows each interaction to depend on its own rank and earlier ranks.', 'method-flow'],
    execution: ['Observe the consequences and update the plan.', 'Maze plans are checked for feasibility before execution. When replanning is enabled, updated observations condition the next plan.', 'method-execution']
  };
  const flow = root.querySelector('.overview-flow');
  const svg = root.querySelector('.overview-wires');
  const edges = root.querySelector('.overview-edges');
  const ns = 'http://www.w3.org/2000/svg';
  const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
  function draw() {
    const bounds = flow.getBoundingClientRect();
    if (!bounds.width) return;
    const mobile = window.matchMedia('(max-width: 700px)').matches;
    svg.setAttribute('viewBox', `0 0 ${bounds.width} ${bounds.height}`);
    const nodes = ['inputs','grounding','ordering','generation','execution'].map(key => {
      const b = root.querySelector('#overview-'+key).getBoundingClientRect();
      return {x:b.x-bounds.x,y:b.y-bounds.y,w:b.width,h:b.height};
    });
    edges.replaceChildren();
    function path(d, stage, dashed=false) {
      const p=document.createElementNS(ns,'path');
      p.setAttribute('d',d);p.dataset.stage=stage;
      p.setAttribute('marker-end','url(#overview-arrow)');
      if(dashed)p.setAttribute('stroke-dasharray','4 5');
      edges.append(p);
      if(!reducedMotion.matches){
        const dot=document.createElementNS(ns,'circle');dot.setAttribute('r','2.7');dot.dataset.stage=stage;dot.classList.add('overview-flow-dot');
        const motion=document.createElementNS(ns,'animateMotion');motion.setAttribute('path',d);motion.setAttribute('dur',dashed?'7s':'3.5s');motion.setAttribute('repeatCount','indefinite');motion.setAttribute('calcMode','paced');
        dot.append(motion);edges.append(dot);
      }
    }
    function label(text,x,y) {
      const t=document.createElementNS(ns,'text');
      t.setAttribute('x',x);t.setAttribute('y',y);t.setAttribute('text-anchor','middle');
      t.textContent=text;edges.append(t);
    }
    nodes.slice(0,-1).forEach((a,i)=>{
      const b=nodes[i+1],stage=Object.keys(stages)[i];
      path(mobile ? `M ${a.x+a.w/2} ${a.y+a.h} V ${b.y-5}` : `M ${a.x+a.w} ${a.y+a.h/2} H ${b.x-5}`,stage);
    });
    const [input,context,,generation,execution]=nodes;
    if(mobile) {
      const right=bounds.width-7,left=7;
      path(`M ${context.x+context.w} ${context.y+context.h/2} H ${right} V ${generation.y+generation.h/2} H ${generation.x+generation.w+5}`,'generation');
      path(`M ${execution.x} ${execution.y+execution.h/2} H ${left} V ${input.y+input.h/2} H ${input.x-5}`,'execution',true);
      label('Updated observation when replanning',bounds.width/2,bounds.height-8);
    } else {
      const cx=context.x+context.w/2,gx=generation.x+generation.w/2;
      path(`M ${cx} ${context.y} V 24 H ${gx} V ${generation.y-5}`,'generation');
      label('Planning context conditions generation',(cx+gx)/2,14);
      const bottom=bounds.height-30,ex=execution.x+execution.w/2,ix=input.x+input.w/2;
      path(`M ${ex} ${execution.y+execution.h} V ${bottom} H ${ix} V ${input.y+input.h+5}`,'execution',true);
      label('Updated observation when replanning',(ix+ex)/2,bottom+20);
    }
  }
  const buttons=[...root.querySelectorAll('[data-overview-stage]')];
  buttons.forEach(button => button.addEventListener('click', () => {
    const stage = button.dataset.overviewStage, [title,copy,target] = stages[stage];
    root.dataset.active = stage;
    buttons.forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    root.querySelector('.overview-explanation strong').textContent = title;
    root.querySelector('.overview-explanation p').textContent = copy;
    const link=root.querySelector('.overview-explanation a');
    link.href = '#'+target;link.textContent='Explore '+stage;
  }));
  const examples={
    grounding:[['structure-g1','G1'],['structure-spot','Spot'],['structure-spot_arm','Spot + arm'],['structure-husky','Husky']],
    ordering:[['method-order-maze','Objects in a shared maze context']],
    generation:[['method-flow-0-refined','Object motion within scene geometry']],
    execution:[['mpc-optimized','Recorded interaction and candidate motions']]
  };
  // Inline inspection keeps the complete pipeline visible above the example.
  const preview=document.createElement('div');preview.id='overview-preview';preview.className='overview-preview-inline';preview.setAttribute('role','region');preview.setAttribute('aria-label','Component example');flow.after(preview);
  const leaders=document.createElementNS(ns,'svg');leaders.classList.add('overview-detail-leaders');leaders.setAttribute('aria-hidden','true');root.append(leaders);
  let previewOwner=null;
  function drawPreview(){
    if(!previewOwner)return;
    const r=root.getBoundingClientRect(),a=previewOwner.getBoundingClientRect(),b=preview.getBoundingClientRect();
    leaders.setAttribute('viewBox',`0 0 ${r.width} ${r.height}`);leaders.replaceChildren();
    const top=b.top-r.top,ay=a.bottom-r.top;
    for(const [sx,dx] of [[a.left-r.left,b.left-r.left],[a.right-r.left,b.right-r.left]]){
      const p=document.createElementNS(ns,'path');p.setAttribute('d',`M ${sx} ${ay} C ${sx} ${top-28}, ${dx} ${top-28}, ${dx} ${top}`);leaders.append(p);
    }
  }
  function hidePreview(){root.querySelectorAll('.overview-inspectable').forEach(n=>n.classList.remove('inspecting'));}
  function showPreview(node,items){
    previewOwner=node;preview.replaceChildren();hidePreview();node.classList.add('inspecting');
    const stage=node.id.replace('overview-','');
    if(stages[stage]){
      const [title,copy,target]=stages[stage];root.dataset.active=stage;
      buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.overviewStage===stage)));
      root.querySelector('.overview-explanation strong').textContent=title;root.querySelector('.overview-explanation p').textContent=copy;
      const link=root.querySelector('.overview-explanation a');link.href='#'+target;link.textContent='Explore '+stage;
    }
    const gallery=document.createElement('div');gallery.className=items.length>1?'overview-preview-grid':'';
    items.forEach(([file,caption])=>{
      const figure=document.createElement('figure'),img=document.createElement('img'),label=document.createElement('figcaption');
      img.src=clearAssetURL('assets/media/'+file+'.png');img.alt=caption;label.textContent=caption;figure.append(img,label);gallery.append(figure);
    });
    preview.append(gallery);drawPreview();
  }
  function addPreview(node,items,label){
    node.tabIndex=0;node.setAttribute('aria-controls',preview.id);node.classList.add('overview-inspectable');
    node.addEventListener('pointerenter',event=>{if(event.pointerType!=='touch')showPreview(node,items);});
    node.addEventListener('focus',()=>showPreview(node,items));
    node.addEventListener('click',()=>showPreview(node,items));
  }
  document.addEventListener('keydown',event=>{if(event.key==='Escape')hidePreview();});
  new ResizeObserver(drawPreview).observe(preview);
  Object.entries(examples).forEach(([stage,items])=>{
    const node=root.querySelector('#overview-'+stage);addPreview(node,items,stage);node.setAttribute('role','button');node.setAttribute('aria-label','Explore '+stage);
    node.addEventListener('click',()=>buttons.find(b=>b.dataset.overviewStage===stage).click());
    node.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();node.click();}if(event.key==='Escape')node.blur();});
  });
  buttons.forEach(button=>button.addEventListener('click',()=>showPreview(root.querySelector('#overview-'+button.dataset.overviewStage),examples[button.dataset.overviewStage])));
  const inputExamples=[['structure-g1','Robot structure'],['objects','Object states and next states'],['scene-maze','Scene geometry']];
  root.querySelectorAll('#overview-inputs>div').forEach((node,i)=>addPreview(node,[inputExamples[i]],'input-'+i));
  reducedMotion.addEventListener('change',draw);
  new ResizeObserver(()=>{draw();drawPreview();}).observe(flow);
  showPreview(root.querySelector('#overview-grounding'),examples.grounding);
  document.fonts.ready.then(draw);
})();
