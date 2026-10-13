(() => {
  const root = document.querySelector('#clear-overview');
  if (!root) return;
  const stages = {
    grounding: ['Embodiment-aware scene grounding.', 'Structure, object states, and scene geometry form a planning context that represents the robot’s capabilities and accessible interactions.', 'method-grounding'],
    ordering: ['Object selection and interaction ordering.', 'OrderNet uses the planning context to select objects and sample interaction priorities. Sorting the selected priorities gives a candidate order.', 'method-order'],
    generation: ['Rank-causal generation of object references.', 'CausalFlowNet jointly updates object parameters over flow time. Rank causal attention permits each generated row to read its own and earlier ranks, while the planning context remains fixed.', 'method-flow'],
    execution: ['Execution with observation-conditioned replanning.', 'Candidate validation accounts for earlier object motions. Policy-guided MPC executes interactions, and updated observations guide replanning.', 'method-execution']
  };
  const flow = root.querySelector('.overview-flow');
  const svg = root.querySelector('.overview-wires');
  const edges = root.querySelector('.overview-edges');
  const ns = 'http://www.w3.org/2000/svg';
  const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
  // A fixed-size arrowhead ends at the path endpoint, just outside the box.
  const marker=svg.querySelector('#overview-arrow');
  for(const [key,value] of Object.entries({viewBox:'0 0 8 8',refX:'8',refY:'4',markerWidth:'8',markerHeight:'8',markerUnits:'userSpaceOnUse',orient:'auto'}))marker.setAttribute(key,value);
  marker.querySelector('path').setAttribute('d','M 0 0 L 8 4 L 0 8 Z');
  function draw() {
    const bounds=flow.getBoundingClientRect();if(!bounds.width)return;
    const mobile=matchMedia('(max-width: 1000px)').matches;
    svg.setAttribute('viewBox',`0 0 ${bounds.width} ${bounds.height}`);
    const nodes=['inputs','grounding','ordering','generation','execution'].map(key=>{
      const b=root.querySelector('#overview-'+key).getBoundingClientRect();
      return {x:b.x-bounds.x,y:b.y-bounds.y,w:b.width,h:b.height};
    });
    edges.replaceChildren();
    function path(points,stage,dashed=false){
      let d=`M ${points[0].join(' ')}`;
      for(let i=1;i<points.length-1;i++){
        const a=points[i-1],b=points[i],c=points[i+1];
        const ab=Math.hypot(b[0]-a[0],b[1]-a[1]),bc=Math.hypot(c[0]-b[0],c[1]-b[1]);
        const r=Math.min(6,ab/2,bc/2);
        if(!ab||!bc)continue;
        const entry=b.map((v,j)=>v+(a[j]-v)*r/ab),exit=b.map((v,j)=>v+(c[j]-v)*r/bc);
        d+=` L ${entry.join(' ')} Q ${b.join(' ')} ${exit.join(' ')}`;
      }
      d+=` L ${points.at(-1).join(' ')}`;
      const p=document.createElementNS(ns,'path');p.setAttribute('d',d);p.dataset.stage=stage;
      p.setAttribute('marker-end','url(#overview-arrow)');
      if(dashed)p.setAttribute('stroke-dasharray','4 5');
      edges.append(p);
    }
    function label(text,x,y){
      const t=document.createElementNS(ns,'text');t.setAttribute('x',x);t.setAttribute('y',y);t.setAttribute('text-anchor','middle');t.textContent=text;edges.append(t);
    }
    nodes.slice(0,-1).forEach((a,i)=>{
      const b=nodes[i+1],stage=Object.keys(stages)[i],ay=a.y+a.h/2,by=b.y+b.h/2;
      if(mobile){
        // Route beside the following title/model rows, never through them.
        const sx=a.x+a.w/2,lane=18;
        path([[sx,a.y+a.h+1],[sx,a.y+a.h+14],[lane,a.y+a.h+14],[lane,by],[b.x-2,by]],stage);
      }else{
        const sx=a.x+a.w+1,ex=b.x-2,mid=(sx+ex)/2;
        path(Math.abs(ay-by)<.5?[[sx,ay],[ex,by]]:[[sx,ay],[mid,ay],[mid,by],[ex,by]],stage);
      }
    });
    const [input,context,,generation,execution]=nodes;
    if(mobile){
      const right=bounds.width-8,left=5;
      path([[context.x+context.w+1,context.y+context.h*.3],[right,context.y+context.h*.3],[right,generation.y+generation.h*.3],[generation.x+generation.w+2,generation.y+generation.h*.3]],'generation');
      path([[execution.x-1,execution.y+execution.h*.75],[left,execution.y+execution.h*.75],[left,input.y+input.h*.3],[input.x-2,input.y+input.h*.3]],'execution',true);
      label('Updated observation when replanning',bounds.width/2,bounds.height-8);
    }else{
      const cx=context.x+context.w/2,gx=generation.x+generation.w/2;
      const lane=Math.max(...nodes.map(n=>n.y+n.h))+28;
      path([[cx,context.y+context.h+1],[cx,lane],[gx,lane],[gx,generation.y+generation.h+2]],'generation');
      label('Planning context H → Generation',(cx+gx)/2,lane-8);
      const bottom=bounds.height-26,ex=execution.x+execution.w/2,ix=input.x+input.w/2;
      path([[ex,execution.y+execution.h+1],[ex,bottom],[ix,bottom],[ix,input.y+input.h+2]],'execution',true);
      label('Updated observation when replanning',(ix+ex)/2,bottom+18);
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
    ordering:[['illustration-order','Object selection and ordering']],
    generation:[['illustration-flow','Motion references']],
    execution:[['mpc-optimized','Recorded interaction and candidate motions']]
  };
  // Inline inspection keeps the complete pipeline visible above the example.
  const preview=document.createElement('div');preview.id='overview-preview';preview.className='overview-preview-inline';preview.setAttribute('role','region');preview.setAttribute('aria-label','Component preview');flow.after(preview);
  const notation=root.querySelector('.overview-notation');if(notation)preview.append(notation);
  const leaders=document.createElementNS(ns,'svg');leaders.classList.add('overview-detail-leaders');leaders.setAttribute('aria-hidden','true');root.append(leaders);
  let previewOwner=null,launchTimer,hoverTimer,pinned=false;
  const pinButton=document.createElement('button');pinButton.type='button';pinButton.className='overview-pin';preview.append(pinButton);
  function setPinned(value){pinned=value;preview.dataset.pinned=String(value);pinButton.textContent=value?'Unpin preview':'Pin preview';pinButton.setAttribute('aria-pressed',String(value));}
  pinButton.onclick=()=>setPinned(!pinned);setPinned(false);
  preview.addEventListener('play',()=>setPinned(true),true);
  function requestPreview(node,items,lock=false){clearTimeout(hoverTimer);if(lock){showPreview(node,items);setPinned(true);}else if(!pinned)hoverTimer=setTimeout(()=>{if(!pinned)showPreview(node,items);},240);} const onScreen=()=>{const r=preview.getBoundingClientRect();return !document.hidden&&r.bottom>0&&r.top<innerHeight;};const galleries=new Map();
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
    if(previewOwner===node&&galleries.has(node))return;
    clearTimeout(launchTimer);preview.querySelectorAll('video').forEach(v=>v.pause());preview.querySelectorAll('iframe').forEach(f=>f.contentWindow?.postMessage({type:'clear-scene-visible',visible:false},'*'));
    previewOwner=node;preview.querySelectorAll(':scope > div:not(.overview-notation)').forEach(g=>g.hidden=true);hidePreview();node.classList.add('inspecting');
    const stage=node.id.replace('overview-','');
    if(notation){
      notation.dataset.active=stage;
      notation.querySelectorAll('[data-overview-detail]').forEach(panel=>panel.hidden=panel.dataset.overviewDetail!==stage);
    }
    if(stages[stage]){
      const [title,copy,target]=stages[stage];root.dataset.active=stage;
      buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.overviewStage===stage)));
      root.querySelector('.overview-explanation strong').textContent=title;root.querySelector('.overview-explanation p').textContent=copy;
      const link=root.querySelector('.overview-explanation a');link.href='#'+target;link.textContent='Explore '+stage;
    }
    let gallery=galleries.get(node);
    if(!gallery){
      gallery=document.createElement('div');gallery.className=items.length>1?'overview-preview-grid':'';galleries.set(node,gallery);preview.append(gallery);
      items.forEach(([file,caption])=>{
        const figure=document.createElement('figure'),label=document.createElement('figcaption');figure.dataset.example=file;label.textContent=caption;
        if(file.startsWith('illustration-')){
          const kind=file==='illustration-order'?'ordering':file==='illustration-scene'?'scene':'flow';
          const diagram=window.CLEAR_METHOD_SCHEMATIC?.createPreview(kind);
          if(diagram){diagram.style.width='100%';diagram.style.maxHeight='360px';figure.append(diagram);}
          figure.append(label);gallery.append(figure);
        }else if(file.startsWith('method-')||file==='mpc-optimized'){
          const v=document.createElement('div');v.className='viewer overview-live-viewer';v.dataset.scene=file;v.dataset.title=caption;v.dataset.generation='true';if(file==='mpc-optimized')v.dataset.ego='true';
          if(file==='method-order-maze'){v.dataset.orderStage='supervision';label.textContent='Designated teaser reference interaction';}
          const poster=document.createElement(file==='mpc-optimized'?'video':'img');poster.className='preview-image';
          if(poster.tagName==='VIDEO'){poster.muted=true;poster.loop=true;poster.playsInline=true;prepareManualVideo(poster);const media=file==='mpc-optimized'?'mpc-optimized-contact':file;poster.poster=clearAssetURL('assets/media/'+media+'.png');poster.src=clearAssetURL('assets/media/'+media+'.mp4');v.dataset.contactSide='true';}
          else{poster.src=clearAssetURL('assets/media/'+file+'.png');poster.alt=caption;}
          const button=document.createElement('button');button.className='launch';button.textContent='Play example';button.type='button';v.append(poster,button);if(file==='mpc-optimized')attachEgoVideo(v,file);figure.append(v,label);gallery.append(figure);wireViewer(v);
        }else{
          const movie=document.createElement('video');movie.muted=true;movie.loop=true;movie.playsInline=true;prepareManualVideo(movie);movie.poster=clearAssetURL('assets/media/'+file+'.png');movie.src=clearAssetURL('assets/media/'+file+'.mp4');figure.append(movie,label);gallery.append(figure);
        }
      });
    }
    gallery.hidden=false;
    preview.dataset.stage=stage;
    let description=preview.querySelector('.overview-preview-description');
    if(!description){description=document.createElement('div');description.className='overview-preview-description';preview.prepend(description);}
    description.hidden=false;description.replaceChildren();
    const heading=document.createElement('strong'),copy=document.createElement('p');
    const info=stages[stage]||({'input-0':['Robot structure','G1, Spot, Spot + arm, and Husky.'],'input-1':['Object states','Object configurations and their changes.'],'input-2':['Scene geometry','Terrain views include stairs, slopes, and a plank connecting two raised blocks.']})[stage];heading.textContent=info?info[0]:'Observe the planning inputs.';copy.textContent=info?info[1]:'Robot structure, object states, and scene geometry describe the planning query.';description.append(heading,copy);
    const phrases={grounding:'capabilities and accessible interactions',ordering:'select objects and sample interaction priorities',generation:'its own and earlier ranks',execution:'updated observations guide replanning','input-0':'G1, Spot, Spot + arm, and Husky','input-1':'Object configurations','input-2':'stairs, slopes, and a plank'};
    const phrase=phrases[stage],text=copy.textContent;
    if(phrase&&text.includes(phrase)){const index=text.indexOf(phrase),mark=document.createElement('mark');mark.textContent=phrase;copy.replaceChildren(document.createTextNode(text.slice(0,index)),mark,document.createTextNode(text.slice(index+phrase.length)));}
    launchTimer=setTimeout(()=>{if(previewOwner!==node||!onScreen())return;gallery.querySelectorAll('.viewer').forEach(v=>{const frame=v.querySelector('iframe');if(frame)frame.contentWindow.postMessage({type:'clear-scene-visible',visible:true},'*');});},220);
    drawPreview();
  }

  function addPreview(node,items,label){
    node.tabIndex=0;node.setAttribute('aria-controls',preview.id);node.classList.add('overview-inspectable');
    node.setAttribute('role','button');node.setAttribute('aria-label',label);
    node.addEventListener('pointerenter',event=>{if(event.pointerType!=='touch')requestPreview(node,items);});
    node.addEventListener('pointerleave',()=>clearTimeout(hoverTimer));
    node.addEventListener('focus',()=>requestPreview(node,items));
    node.addEventListener('click',()=>requestPreview(node,items,true));
    node.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();requestPreview(node,items,true);}});
  }
  document.addEventListener('keydown',event=>{if(event.key==='Escape'){clearTimeout(hoverTimer);setPinned(false);}});
  new ResizeObserver(drawPreview).observe(preview);
  new IntersectionObserver(entries=>{const visible=entries[0].isIntersecting;preview.querySelectorAll('video').forEach(v=>{if(!visible)v.pause();});},{threshold:.01}).observe(preview);
  document.addEventListener('visibilitychange',()=>{const flowBox=flow.getBoundingClientRect();if(document.hidden||flowBox.bottom<=0||flowBox.top>=innerHeight)svg.pauseAnimations?.();else svg.unpauseAnimations?.();const box=preview.getBoundingClientRect();preview.querySelectorAll('video').forEach(v=>{if(document.hidden){v.pause();svg.pauseAnimations?.();}});});

  Object.entries(examples).forEach(([stage,items])=>{
    const node=root.querySelector('#overview-'+stage);addPreview(node,items,stage);node.setAttribute('role','button');node.setAttribute('aria-label','Explore '+stage);

  });
  buttons.forEach(button=>{
    const node=root.querySelector('#overview-'+button.dataset.overviewStage),items=examples[button.dataset.overviewStage];
    button.addEventListener('click',()=>requestPreview(node,items,true));button.addEventListener('focus',()=>requestPreview(node,items));
    button.parentElement.addEventListener('pointerenter',event=>{if(event.pointerType!=='touch')requestPreview(node,items);});
    button.parentElement.addEventListener('pointerleave',()=>clearTimeout(hoverTimer));
  });
  const inputExamples=[examples.grounding,[['objects','Object states']],
    [['illustration-scene','Scene geometry'],['scene-stairs','Stairs'],['scene-steps','Stepped bridge'],['scene-slope','Slope'],['scene-maze','Mixed terrain']]];
  root.querySelectorAll('#overview-inputs>div').forEach((node,i)=>{node.id='overview-input-'+i;addPreview(node,inputExamples[i],['Robot structure','Object states','Scene geometry'][i]);});
  reducedMotion.addEventListener('change',draw);
  new ResizeObserver(()=>{draw();drawPreview();}).observe(flow);
  // Prepare the initial gallery without starting media until it actually enters view.
  new IntersectionObserver(entries=>{if(entries[0].isIntersecting&&!previewOwner)showPreview(root.querySelector('#overview-grounding'),examples.grounding);}).observe(root);
  svg.pauseAnimations?.();
  new IntersectionObserver(entries=>{if(entries[0].isIntersecting&&!document.hidden)svg.unpauseAnimations?.();else svg.pauseAnimations?.();}).observe(flow);
  document.fonts.ready.then(draw);
})();
