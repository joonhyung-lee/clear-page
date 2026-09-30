/* A new, continuous training run. Historical controller evidence stays separate. */
(() => {
  const root = document.querySelector('#spot-curriculum');
  if (!root) return;
  const host = root.querySelector('[data-curriculum-view]');
  const status = root.querySelector('[data-curriculum-status]');
  const caption = root.querySelector('[data-curriculum-caption]');
  const explanations = {
    initialization: 'Random policy before the first optimizer update.',
    locomotion: 'Learn velocity tracking and balance on flat ground.',
    terrain: 'Continue the same policy on progressively harder stairs and slopes.',
    arm: 'Continue locomotion training across an expanding range of arm postures.'
  };
  let selected = 'initialization', currentScene, loading = false, near = false, body = 'spot';
  const bodyName = () => ({g1:'G1',spot:'Spot',spot_arm:'Spot + arm'})[body];
  const fmt = value => value.toLocaleString('en-US');
  let chartData, metricMode = 'optimization', inspectedStep = null, hoveredChart;
  const metricLabels = {value:'Value loss', policy:'Policy surrogate loss', entropy:'Policy entropy', return:'Episode return', terrain:'Mean terrain level', tracking:'Velocity tracking error', arm:'Arm curriculum level'};
  const stageColors = {locomotion:'#306b91', terrain:'#ae632d', arm:'#6c5795'};
  const number = n => Number(n.toPrecision(5)).toString();
  const nearest = (rows, step) => rows.reduce((best, row, i) => Math.abs(row.update-step)<Math.abs(rows[best].update-step)?i:best, 0);
  function curves(data) {
    chartData = data;
    const container = root.querySelector('[data-curriculum-curves]');
    if (!container.children.length) {
      for (let i=0;i<3;i++) {
        const figure = document.createElement('figure'); figure.className='loco-chart';
        figure.dataset.curriculumChart=i;
        const title=document.createElement('figcaption'), canvas=document.createElement('canvas'), tip=document.createElement('div');
        canvas.tabIndex=0; canvas.setAttribute('role','img'); tip.className='loco-tooltip'; tip.hidden=true;
        const comparison=document.createElement('div'); comparison.className='curriculum-comparison';
        figure.append(title,canvas,tip,comparison); container.append(figure);
        const inspect = event => {
          const rows=chartData?.curves || []; if(!rows.length || !figure._plot)return;
          const box=canvas.getBoundingClientRect(), p=figure._plot;
          inspectedStep=rows[nearest(rows,(event.clientX-box.left-p.left)/(p.right-p.left)*p.maximum)].update;
          hoveredChart=figure; drawCurves();
        };
        canvas.onpointermove=inspect; canvas.onpointerdown=inspect;
        canvas.onpointerleave=()=>{if(document.activeElement!==canvas){hoveredChart=null;inspectedStep=null;drawCurves();}};
        canvas.onblur=()=>{hoveredChart=null;inspectedStep=null;drawCurves();};
        canvas.onkeydown=event=>{
          const rows=chartData?.curves || []; if(!rows.length || !['Home','End','ArrowLeft','ArrowRight'].includes(event.key))return;
          event.preventDefault();
          let index=nearest(rows,inspectedStep??Number(root.dataset.replayUpdates??0));
          index=event.key==='Home'?0:event.key==='End'?rows.length-1:Math.max(0,Math.min(rows.length-1,index+(event.key==='ArrowLeft'?-1:1)));
          inspectedStep=rows[index].update; hoveredChart=figure; drawCurves();
          root.querySelector('[data-curriculum-readout]').textContent=`Update ${fmt(inspectedStep)}. ${metricLabels[figure.dataset.metric]}: ${Number.isFinite(rows[index][figure.dataset.metric])?number(rows[index][figure.dataset.metric]):'Not recorded'}`;
        };
      }
    }
    const legend=root.querySelector('[data-curriculum-phases]'); legend.replaceChildren();
    data.stages.filter(stage=>stage.id!=='initialization').forEach((stage,i)=>{
      const span=document.createElement('span');span.style.setProperty('--phase',stageColors[stage.id]);span.textContent=`Phase ${['I','II','III'][i]} · ${stage.label}`;span.title=stage.updates ? `${fmt(stage.updates)} completed updates` : 'Not started';legend.append(span);
    });
    drawCurves();
  }
  function drawCurves() {
    if(!chartData)return;
    const rows=chartData.curves||[];
    const keys=metricMode==='optimization'?['value','policy','entropy']:['return','terrain',body==='spot_arm'?'arm':'tracking'];
    const phases=[]; let offset=0;
    chartData.stages.filter(s=>s.id!=='initialization').forEach(stage=>{phases.push({...stage,start:offset});offset+=stage.targetUpdates;});
    root.querySelectorAll('[data-curriculum-chart]').forEach((figure,i)=>{
      const key=keys[i], canvas=figure.querySelector('canvas'), w=canvas.clientWidth, h=148;
      figure.dataset.metric=key; figure.querySelector('figcaption').textContent=metricLabels[key];
      canvas.setAttribute('aria-label', `${bodyName()} ${metricLabels[key]}. Use arrow keys, Home and End to inspect completed PPO updates.`);
      if(!w)return;
      const dpr=Math.min(devicePixelRatio||1,2);canvas.width=w*dpr;canvas.height=h*dpr;
      const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.font='10px Arial';
      const vals=rows.map(r=>r[key]).filter(Number.isFinite), low=Math.min(0,...vals), high=Math.max(0,...vals), pad=(high-low||1)*.08;
      const minimum=low<0?low-pad:0, maximumY=high+pad, left=43,right=w-12,top=27,bottom=h-41;
      const maximum=Math.max(1,offset,rows.at(-1)?.update||1),x=n=>left+n/maximum*(right-left),y=n=>bottom-(n-minimum)/(maximumY-minimum)*(bottom-top);
      figure._plot={left,right,maximum};
      for(let j=0;j<3;j++){const v=minimum+(maximumY-minimum)*j/2;ctx.strokeStyle='#e9ece5';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(left,y(v));ctx.lineTo(right,y(v));ctx.stroke();ctx.fillStyle='#7a8472';ctx.textAlign='right';ctx.fillText(Number(v.toPrecision(2)).toString(),left-5,y(v)+3);}
      phases.forEach((phase,pi)=>{
        const a=x(phase.start),b=x(Math.min(maximum,phases[pi+1]?.start??maximum)),color=stageColors[phase.id];
        ctx.fillStyle=color+(phase.updates?'19':'09');ctx.fillRect(a,top,b-a,bottom-top);
        ctx.strokeStyle=color;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(a+1,18);ctx.lineTo(a+1,11);ctx.lineTo(b-1,11);ctx.lineTo(b-1,18);ctx.stroke();
        const label='Phase '+['I','II','III'][pi]+(phase.updates?'':' (planned)'),tw=ctx.measureText(label).width;
        if(b-a>tw+10){ctx.fillStyle='#fff';ctx.fillRect((a+b-tw)/2-4,4,tw+8,14);ctx.fillStyle=color;ctx.textAlign='center';ctx.fillText(label,(a+b)/2,14);}
        ctx.save();ctx.beginPath();ctx.rect(left,top,right-left,bottom-top+1);ctx.clip();ctx.strokeStyle=color;ctx.lineWidth=1.3;ctx.beginPath();let started=false;
        for(const row of rows){if(row.stage!==phase.id)continue;if(!Number.isFinite(row[key])){started=false;continue;}ctx[started?'lineTo':'moveTo'](x(row.update),y(row[key]));started=true;}ctx.stroke();ctx.restore();
        if(pi){ctx.setLineDash([4,3]);ctx.beginPath();ctx.moveTo(a,top);ctx.lineTo(a,bottom);ctx.stroke();ctx.setLineDash([]);}
      });
      ctx.fillStyle='#65715f';ctx.textAlign='left';ctx.fillText('0',left,h-5);ctx.textAlign='right';ctx.fillText(fmt(maximum)+' updates',right,h-5);
      const replayUpdate=Number(root.dataset.replayUpdates||0);
      // Replay selection lives on the time axis, not in a second stage-card UI.
      if(i===0){
        const checkpoints=chartData.stages.filter(stage=>stage.replay);
        const existing=new Map([...figure.querySelectorAll('[data-checkpoint-stage]')].map(button=>[button.dataset.checkpointStage,button]));
        checkpoints.forEach((stage,index)=>{
          let button=existing.get(stage.id);
          if(!button){button=document.createElement('button');button.type='button';button.className='curriculum-checkpoint';button.dataset.checkpointStage=stage.id;figure.append(button);}
          const update=stage.replay.cumulativeUpdates;
          button.textContent=index+1;button.title=`${stage.label} · Update ${fmt(update)}`;
          button.setAttribute('aria-label',`Replay ${stage.label}, update ${fmt(update)}`);
          button.setAttribute('aria-pressed',String(stage.replay.scene===currentScene));
          button.style.left=(x(update)-8)+'px';button.style.top=(canvas.offsetTop+bottom+5)+'px';
          button.onclick=()=>select(stage);
          existing.delete(stage.id);
        });
        existing.forEach(button=>button.remove());
      }
      ctx.strokeStyle='#abb3aa';ctx.beginPath();ctx.moveTo(x(Math.min(replayUpdate,maximum)),top);ctx.lineTo(x(Math.min(replayUpdate,maximum)),bottom+4);ctx.stroke();
      const row=rows.length?rows[nearest(rows,inspectedStep??replayUpdate)]:null;
      figure.dataset.inspected=JSON.stringify(row?{step:row.update,phase:row.stage,metric:key,value:Number.isFinite(row[key])?row[key]:null}:null);
      if(row){ctx.strokeStyle='#99a48e';ctx.setLineDash([2,3]);ctx.beginPath();ctx.moveTo(x(row.update),top);ctx.lineTo(x(row.update),bottom);ctx.stroke();ctx.setLineDash([]);if(Number.isFinite(row[key])){ctx.beginPath();ctx.arc(x(row.update),y(row[key]),3.5,0,2*Math.PI);ctx.fillStyle=stageColors[row.stage];ctx.fill();ctx.strokeStyle='#fff';ctx.stroke();}}
      if(!vals.length){ctx.fillStyle='#63705c';ctx.textAlign='center';ctx.fillText('Available when this metric is logged',(left+right)/2,(top+bottom)/2);}
      const first=rows.find(r=>Number.isFinite(r[key]));
      const compared=hoveredChart&&row?row:rows.findLast(r=>Number.isFinite(r[key]));
      const comparison=figure.querySelector('.curriculum-comparison');
      const delta=first&&compared&&Number.isFinite(compared[key])?compared[key]-first[key]:null;
      // Signed surrogate objectives and zero baselines do not support useful percentage ratios.
      const percent=delta!==null&&['value','entropy'].includes(key)&&first[key]>1e-12?100*delta/first[key]:null;
      figure.dataset.comparison=JSON.stringify({baselineUpdate:first?.update??null,baseline:first?.[key]??null,
        comparedUpdate:compared?.update??null,value:compared?.[key]??null,delta,percent});
      const signed=n=>(n>0?'+':'')+number(n);
      comparison.replaceChildren();
      if(first){
        const values=document.createElement('span'),change=document.createElement('span');
        values.textContent=`First · #${fmt(first.update)}: ${number(first[key])} → ${hoveredChart?'Inspected':'Latest'} · #${fmt(compared?.update??first.update)}: ${Number.isFinite(compared?.[key])?number(compared[key]):'Not recorded'}`;
        change.textContent=delta===null?'Change unavailable':`Δ ${signed(delta)}${percent===null?'':` (${percent>0?'+':''}${percent.toFixed(1)}%)`}`;
        comparison.append(values,change);
        ctx.save();ctx.strokeStyle='#69736b';ctx.lineWidth=1;ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(left,y(first[key]));ctx.lineTo(right,y(first[key]));ctx.stroke();ctx.setLineDash([]);
        ctx.beginPath();ctx.arc(x(first.update),y(first[key]),3,0,2*Math.PI);ctx.fillStyle='#fff';ctx.fill();ctx.stroke();ctx.restore();
      }else comparison.textContent='No logged baseline for this metric yet.';
      const tip=figure.querySelector('.loco-tooltip');tip.hidden=hoveredChart!==figure||!row;
      if(!tip.hidden){tip.replaceChildren();const title=document.createElement('strong'),phase=document.createElement('span'),value=document.createElement('div');title.textContent='Update '+fmt(row.update);phase.textContent=chartData.stages.find(s=>s.id===row.stage)?.label;value.textContent=metricLabels[key]+': '+(Number.isFinite(row[key])?number(row[key]):'Not recorded');tip.append(title,phase,value);tip.style.left=Math.max(0,Math.min(w-tip.offsetWidth,x(row.update)+8))+'px';tip.style.top='16px';}
    });
  }
  root.querySelectorAll('[data-curriculum-metrics]').forEach(button=>button.onclick=()=>{
    metricMode=button.dataset.curriculumMetrics;
    root.querySelectorAll('[data-curriculum-metrics]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
    hoveredChart=null;drawCurves();
  });
  new ResizeObserver(drawCurves).observe(root.querySelector('[data-curriculum-curves]'));
  function select(stage) {
    selected = stage.id;
    if (!stage.replay) {
      host.querySelector('.viewer')?.dispatchEvent(new Event('reset-viewer'));
      currentScene = null;
      const note = document.createElement('p'); note.className = 'scratch-pending';
      note.textContent = 'This body’s checkpoint replay is being prepared. It will appear here automatically.';
      host.replaceChildren(note); caption.textContent = 'Waiting for this body’s own checkpoint replay.';
      return;
    }
    if (currentScene === stage.replay.scene) { drawCurves(); return; }
    host.querySelector('.viewer')?.dispatchEvent(new Event('reset-viewer'));
    currentScene = stage.replay.scene;
    const viewer = document.createElement('div');
    viewer.className = 'viewer scratch-viewer';
    viewer.dataset.scene = currentScene;
    viewer.dataset.generation = 'true';
    viewer.dataset.title = bodyName() + ' ' + stage.label;
    const poster = document.createElement('img');
    poster.className = 'preview-image'; poster.src = `assets/media/${currentScene}.png`;
    poster.alt = bodyName() + ' policy evaluated on the common terrain bank';
    const launch = document.createElement('button'); launch.className = 'launch';
    launch.type = 'button'; launch.textContent = 'Play in 3D';
    viewer.append(poster, launch); host.replaceChildren(viewer);
    wireViewer(viewer); observeAutomaticScene(viewer);
    caption.textContent = `${stage.label} · ${fmt(stage.replay.cumulativeUpdates)} cumulative PPO updates · Replay 0.0 s`;
    root.dataset.replayUpdates = stage.replay.cumulativeUpdates;
    drawCurves();
  }
  function render(data) {
    if (data.body !== body) return;
    root.dataset.body = body;
    const stages = data.stages;
    curves(data);
    root.querySelector('[data-curriculum-intro]').textContent = body === 'g1'
      ? 'G1 starts from random initialization, learns flat locomotion and then adapts to terrain. This new training run is separate from the archived warm start controller.'
      : body === 'spot_arm'
      ? 'Spot + arm starts from random initialization with the arm physically present. Its own policy learns locomotion, terrain traversal and arm posture adaptation.'
      : 'An arm-free Spot starts from random initialization, learns flat locomotion and then adapts to stairs and slopes. Its physics and policy are independent of Spot + arm.';
    const active = stages.find(stage => stage.state === 'training');
    status.textContent = active ? `${active.label} in progress · ${fmt(data.numEnvironments)} parallel environments` : data.complete ? 'Scheduled training stages complete. Replay evaluation remains separate.' : 'Recorded progress from the new training run.';
    // New exports do not interrupt a camera interaction or an active replay.
    if (!currentScene) select(stages.find(stage => stage.id === selected && stage.replay) || stages.find(stage => stage.replay) || stages[0]);
  }
  root.closest('#controller-pretraining').addEventListener('policy-body-change', event => {
    const changed = body !== event.detail.body;
    body = event.detail.body;
    if (changed) {
      host.querySelector('.viewer')?.dispatchEvent(new Event('reset-viewer'));
      host.replaceChildren();
      chartData=null; inspectedStep=null; hoveredChart=null;
      root.querySelector('[data-curriculum-curves]').replaceChildren();
      delete root.dataset.body;
      status.textContent = 'Loading this robot’s training record.';
      caption.textContent = '';
      selected = 'initialization'; currentScene = null;
    }
    if (window.CLEAR_BODY_CURRICULA?.[body]) render(window.CLEAR_BODY_CURRICULA[body]);
    refresh();
  });
  function refresh() {
    if (!near || document.hidden || loading) return;
    loading = true;
    const requestedBody = body;
    const script = document.createElement('script');
    script.src = `assets/${requestedBody}-curriculum-data.js?t=${Math.floor(Date.now()/30000)}`;
    script.onload = () => {
      loading = false; script.remove();
      if (requestedBody !== body) { refresh(); return; }
      if (window.CLEAR_BODY_CURRICULA?.[body]) render(window.CLEAR_BODY_CURRICULA[body]);
    };
    script.onerror = () => {
      loading = false; script.remove();
      if (requestedBody !== body) { refresh(); return; }
      if (!currentScene) status.textContent = 'Training progress is temporarily unavailable.';
    };
    document.head.append(script);
  }
  window.addEventListener('message', event => {
    if (event.source !== host.querySelector('iframe')?.contentWindow || event.data?.type !== 'clear-playback-time' || !Number.isFinite(event.data.time)) return;
    const label = explanations[selected] ? ({initialization:'Initialization',locomotion:'Locomotion',terrain:'Terrain adaptation',arm:'Arm adaptation'})[selected] : selected;
    caption.textContent = `${label} · ${fmt(Number(root.dataset.replayUpdates))} cumulative PPO updates · Replay ${event.data.time.toFixed(1)} s`;
  });
  new IntersectionObserver(entries => { near = entries[0].isIntersecting; if (near) refresh(); }, {rootMargin:'200px'}).observe(root);
  document.addEventListener('visibilitychange', refresh);
  setInterval(refresh, 30000);
})();
