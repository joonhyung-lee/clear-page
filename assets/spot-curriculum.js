/* From-scratch policy checkpoints and measured PPO traces for each body. */
(() => {
  const root = document.querySelector('#spot-curriculum');
  if (!root) return;
  const host = root.querySelector('[data-curriculum-view]');
  const status = root.querySelector('[data-curriculum-status]');
  const caption = root.querySelector('[data-curriculum-caption]');
  const explanations = {
    initialization: 'Random policy before the first optimizer update.',
    locomotion: 'Balance and velocity tracking on flat ground.',
    terrain: 'Progressive stair and slope traversal.',
    arm: 'Balance across arm postures during locomotion.'
  };
  let selected = 'initialization', currentScene, loading = false, near = false, body = root.closest('#controller-pretraining').dataset.body || 'g1';
  let requestedStage = null;
  const bodyName = () => ({g1:'G1',spot:'Spot',spot_arm:'Spot + arm'})[body];
  const checkpoints = data => data.checkpoints || data.stages.filter(stage=>stage.replay);
  const description = stage => stage.description || explanations[stage.id];
  let pendingReplayTime = null;
  const fmt = value => value.toLocaleString('en-US');
  let chartData, metricMode = 'optimization', inspectedStep = null, hoveredChart, highlightedPhase = null;
  const metricLabels = {value:'Value loss', policy:'Policy surrogate loss', entropy:'Policy entropy', return:'Episode return', terrain:'Mean terrain level', tracking:'Velocity tracking error', arm:'Arm curriculum level'};
  const metricNotes = {
    value:'Critic squared return error, with PPO value clipping when enabled. This is the unweighted loss.',
    policy:'Signed PPO clipped surrogate loss. Its sign or decrease alone does not measure task performance.',
    entropy:'Mean action-distribution entropy in nats, summed over action dimensions. This is exploration entropy, not the weighted entropy loss.',
    return:'Mean accumulated reward over the latest 100 completed training episodes, or fewer while the buffer fills.',
    terrain:'Mean terrain curriculum index. Flat-ground training does not log this metric.',
    tracking:'Planar velocity error accumulated over each episode, divided by the maximum command duration, then averaged at resets. Short episodes can produce small values; this is not per-step RMSE.',
    arm:'Recorded arm-posture curriculum level.'
  };
  // Preserve signed raw data while resolving normal values beside rare huge excursions.
  function metricScale(values) {
    const positive=values.map(Math.abs).filter(v=>v>0&&Number.isFinite(v)).sort((a,b)=>a-b);
    const median=positive[Math.floor(positive.length/2)]||1;
    const logarithmic=(positive.at(-1)||0)/median>10000;
    const threshold=Math.pow(10,Math.floor(Math.log10(median)));
    const transform=n=>logarithmic?Math.sign(n)*Math.log10(1+Math.abs(n)/threshold):n;
    const inverse=n=>logarithmic?Math.sign(n)*threshold*Math.expm1(Math.abs(n)*Math.LN10):n;
    const low=transform(Math.min(0,...values)),high=transform(Math.max(0,...values)),pad=(high-low||1)*.08;
    return {logarithmic,transform,inverse,minimum:low<0?low-pad:0,maximum:high+pad};
  }
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
        const scaleNote=document.createElement('small');scaleNote.className='curriculum-scale-note';scaleNote.hidden=true;
        figure.append(title,canvas,tip,comparison,scaleNote); container.append(figure);
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
    const legend=root.querySelector('[data-curriculum-phases]'); legend.replaceChildren();highlightedPhase=null;
    const explanation=root.querySelector('[data-curriculum-explanations]');
    const activePhase=data.stages.find(stage=>stage.state==='training')||data.stages.findLast(stage=>stage.updates>0&&stage.id!=='initialization');
    const defaultCaption=activePhase?description(activePhase):'Random initialization. Training has not started.';
    explanation.textContent=defaultCaption;
    let phaseStart=0;
    data.stages.filter(stage=>stage.id!=='initialization').forEach((stage,i)=>{
      const segment=document.createElement('div');segment.className='curriculum-phase';segment.tabIndex=0;
      segment.dataset.phase=stage.id;segment.dataset.state=stage.state;
      segment.style.setProperty('--phase',stageColors[stage.id]);segment.style.setProperty('--duration',stage.targetUpdates);
      segment.dataset.active=String(stage.id===activePhase?.id);
      segment.style.setProperty('--progress',`${Math.max(0,Math.min(1,stage.updates/stage.targetUpdates))*100}%`);
      const title=document.createElement('strong'),range=document.createElement('span'),track=document.createElement('span'),state=document.createElement('small');
      title.textContent=`${['I','II','III'][i]} · ${stage.label}`;
      range.className='curriculum-phase-range';range.textContent=`${fmt(phaseStart)}–${fmt(phaseStart+stage.targetUpdates)}`;
      track.className='curriculum-phase-track';track.setAttribute('aria-hidden','true');track.append(document.createElement('i'));
      state.textContent=stage.state==='pending'?'Not started':stage.state==='complete'?'Updates finished':`${fmt(stage.updates)} / ${fmt(stage.targetUpdates)} · ${{stopped:'Stopped',failed:'Stopped after error',unknown:'Awaiting update'}[stage.state]||'Training'}`;
      segment.setAttribute('aria-label',`${title.textContent}. Updates ${range.textContent}. ${state.textContent}. ${description(stage)}`);
      const highlight=()=>{highlightedPhase=stage.id;explanation.textContent=description(stage)+(stage.state==='pending'?' No recorded updates.':'');drawCurves();};
      const clear=()=>{highlightedPhase=null;explanation.textContent=defaultCaption;drawCurves();};
      segment.onpointerenter=highlight;segment.onfocus=highlight;
      segment.onpointerleave=()=>{if(document.activeElement!==segment)clear();};segment.onblur=clear;
      segment.append(track,title,range,state);legend.append(segment);phaseStart+=stage.targetUpdates;
    });
    drawCurves();
  }
  function drawCurves() {
    if(!chartData)return;
    const rows=chartData.curves||[];
    const keys=metricMode==='optimization'?['value','policy','entropy']:['return','terrain',body==='spot_arm'?'arm':'tracking'];
    root.querySelector('[data-curriculum-metric-note]').textContent=metricMode==='optimization'
      ? 'Entropy measures exploration. PPO losses need not decrease monotonically. Hover a plot title for its definition.'
      : 'Training returns use recent completed episodes. Accumulated velocity error depends on episode duration and command difficulty. Hover a plot title for its definition.';
    const phases=[]; let offset=0;
    chartData.stages.filter(s=>s.id!=='initialization').forEach(stage=>{phases.push({...stage,start:offset});offset+=stage.targetUpdates;});
    root.querySelectorAll('[data-curriculum-chart]').forEach((figure,i)=>{
      const key=keys[i], canvas=figure.querySelector('canvas'), w=canvas.clientWidth, h=128;
      figure.dataset.metric=key; figure.querySelector('figcaption').textContent=metricLabels[key];
      figure.querySelector('figcaption').title=metricNotes[key];
      canvas.setAttribute('aria-description',metricNotes[key]);
      canvas.setAttribute('aria-label', `${bodyName()} ${metricLabels[key]}. Use arrow keys, Home and End to inspect completed PPO updates.`);
      if(!w)return;
      const dpr=Math.min(devicePixelRatio||1,2);canvas.width=w*dpr;canvas.height=h*dpr;
      const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.font='10px Arial';
      const vals=rows.map(r=>r[key]).filter(Number.isFinite),scale=metricScale(vals);
      const {minimum,maximum:maximumY}=scale, left=43,right=w-12,top=23,bottom=h-32;
      // The ribbon carries the full schedule. Plots use only recorded updates,
      // so a future phase cannot compress the measured trace into a few pixels.
      const maximum=Math.max(1,rows.at(-1)?.update||1),x=n=>left+n/maximum*(right-left),y=n=>bottom-(scale.transform(n)-minimum)/(maximumY-minimum)*(bottom-top);
      figure.dataset.scale=scale.logarithmic?'symlog':'linear';
      const scaleNote=figure.querySelector('.curriculum-scale-note');scaleNote.hidden=!scale.logarithmic;
      scaleNote.textContent=scale.logarithmic?'Symmetric log axis · hover for raw values':'';
      figure._plot={left,right,maximum};
      for(let j=0;j<3;j++){const v=scale.inverse(minimum+(maximumY-minimum)*j/2);ctx.strokeStyle='#e9ece5';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(left,y(v));ctx.lineTo(right,y(v));ctx.stroke();ctx.fillStyle='#7a8472';ctx.textAlign='right';ctx.fillText(Number(v.toPrecision(2)).toString(),left-5,y(v)+3);}
      phases.forEach((phase,pi)=>{
        if(phase.start>=maximum)return;
        const a=x(phase.start),b=x(Math.min(maximum,phases[pi+1]?.start??maximum)),color=stageColors[phase.id];
        ctx.save();ctx.globalAlpha=(highlightedPhase&&highlightedPhase!==phase.id)?0.35:1;
        ctx.fillStyle=color+(highlightedPhase===phase.id?'20':phase.updates?'0d':'05');ctx.fillRect(a,top,b-a,bottom-top);
        if(!phase.updates)ctx.setLineDash([3,3]);
        ctx.strokeStyle=color;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(a+1,18);ctx.lineTo(a+1,11);ctx.lineTo(b-1,11);ctx.lineTo(b-1,18);ctx.stroke();
        ctx.setLineDash([]);
        const label=['I','II','III'][pi]+(phase.updates?'':' · planned'),tw=ctx.measureText(label).width;
        if(b-a>tw+10){ctx.fillStyle='#fff';ctx.fillRect((a+b-tw)/2-4,4,tw+8,14);ctx.fillStyle=color;ctx.textAlign='center';ctx.fillText(label,(a+b)/2,14);}
        ctx.save();ctx.beginPath();ctx.rect(left,top,right-left,bottom-top+1);ctx.clip();ctx.strokeStyle=color;ctx.lineWidth=highlightedPhase===phase.id?1.8:1.2;ctx.beginPath();let started=false;
        const isolated=[];
        for(let ri=0;ri<rows.length;ri++){
          const row=rows[ri];
          if(row.stage!==phase.id)continue;
          if(!Number.isFinite(row[key])){started=false;continue;}
          ctx[started?'lineTo':'moveTo'](x(row.update),y(row[key]));
          const next=rows[ri+1];
          if(!started&&!(next?.stage===phase.id&&Number.isFinite(next[key])))isolated.push(row);
          started=true;
        }
        ctx.stroke();
        // Episode-end metrics can be isolated measurements. A moveTo alone
        // draws nothing; show the recorded point without filling missing data.
        ctx.fillStyle=color;
        for(const row of isolated){ctx.beginPath();ctx.arc(x(row.update),y(row[key]),1.8,0,2*Math.PI);ctx.fill();}
        ctx.restore();
        if(pi){ctx.setLineDash([4,3]);ctx.beginPath();ctx.moveTo(a,top);ctx.lineTo(a,bottom);ctx.stroke();ctx.setLineDash([]);}
        ctx.restore();
      });
      ctx.fillStyle='#65715f';ctx.textAlign='left';ctx.fillText('0',left,h-5);ctx.textAlign='right';ctx.fillText(fmt(maximum)+' recorded updates',right,h-5);
      const replayUpdate=Number(root.dataset.replayUpdates||0);
      // Replay selection lives on the time axis, not in a second stage-card UI.
      if(i===0){
        const replayCheckpoints=checkpoints(chartData);
        const existing=new Map([...figure.querySelectorAll('[data-checkpoint-stage]')].map(button=>[button.dataset.checkpointStage,button]));
        replayCheckpoints.forEach((stage,index)=>{
          let button=existing.get(stage.id);
          if(!button){button=document.createElement('button');button.type='button';button.className='curriculum-checkpoint';button.dataset.checkpointStage=stage.id;figure.append(button);}
          const update=stage.replay.cumulativeUpdates;
          button.textContent=index+1;button.title=`${stage.label} · Update ${fmt(update)}`;
          button.setAttribute('aria-label',`Replay ${stage.label}, update ${fmt(update)}`);
          button.setAttribute('aria-pressed',String(stage.id===selected));
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
      const missing=key==='terrain'?'Not recorded · flat-ground phase':'Not recorded';
      if(!vals.length){ctx.fillStyle='#63705c';ctx.textAlign='center';ctx.fillText(missing,(left+right)/2,(top+bottom)/2);}
      const first=rows.find(r=>Number.isFinite(r[key]));
      const compared=hoveredChart&&row?row:rows.findLast(r=>Number.isFinite(r[key]));
      const comparison=figure.querySelector('.curriculum-comparison');
      const delta=first&&compared&&Number.isFinite(compared[key])?compared[key]-first[key]:null;
      // Signed surrogate objectives and zero baselines do not support useful percentage ratios.
      const percent=delta!==null&&!scale.logarithmic&&key==='value'&&first[key]>1e-12?100*delta/first[key]:null;
      figure.dataset.comparison=JSON.stringify({baselineUpdate:first?.update??null,baseline:first?.[key]??null,
        comparedUpdate:compared?.update??null,value:compared?.[key]??null,delta,percent});
      const signed=n=>(n>0?'+':'')+number(n);
      comparison.replaceChildren();
      if(first){
        const values=document.createElement('span'),change=document.createElement('span');
        values.textContent=`First ${number(first[key])} → ${hoveredChart?'Inspected':'Latest'} ${Number.isFinite(compared?.[key])?number(compared[key]):'Not recorded'}`;
        values.title=`First logged update ${fmt(first.update)}. ${hoveredChart?'Inspected':'Latest'} update ${fmt(compared?.update??first.update)}.`;
        change.textContent=delta===null?'Change unavailable':`Δ ${signed(delta)}${percent===null?'':` (${percent>0?'+':''}${percent.toFixed(1)}%)`}`;
        comparison.append(values,change);
        ctx.save();ctx.strokeStyle='#69736b';ctx.lineWidth=1;ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(left,y(first[key]));ctx.lineTo(right,y(first[key]));ctx.stroke();ctx.setLineDash([]);
        ctx.beginPath();ctx.arc(x(first.update),y(first[key]),3,0,2*Math.PI);ctx.fillStyle='#fff';ctx.fill();ctx.stroke();ctx.restore();
      }else comparison.textContent=key==='terrain'?'Terrain adaptation has not started.':'No logged baseline for this metric yet.';
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
    root.dataset.replayUpdates = stage.replay.cumulativeUpdates;
    caption.textContent = `${stage.label} · ${fmt(stage.replay.cumulativeUpdates)} cumulative PPO updates · Replay 0.0 s`;
    const seek=()=>{
      const frame=host.querySelector('iframe.scene-ready');
      if(!frame)return;
      pendingReplayTime=stage.replay.startTime||0;
      frame.contentWindow.postMessage({type:'clear-playback-command',time:pendingReplayTime+.001,playing:!matchMedia('(prefers-reduced-motion: reduce)').matches},'*');
    };
    if (currentScene === stage.replay.scene) {
      host.querySelector('.viewer')._checkpointSeek=seek;
      seek();drawCurves();return;
    }
    host.querySelector('.viewer')?.dispatchEvent(new Event('reset-viewer'));
    currentScene = stage.replay.scene;
    const viewer = document.createElement('div');
    viewer.className = 'viewer scratch-viewer';
    viewer.dataset.scene = currentScene;
    viewer.dataset.generation = 'true';
    viewer.dataset.title = bodyName() + ' ' + stage.label;
    viewer._checkpointSeek=seek;
    viewer.addEventListener('scene-settled',event=>{if(!event.detail?.failed)viewer._checkpointSeek();});
    const poster = document.createElement('img');
    poster.className = 'preview-image'; poster.src = `assets/media/${currentScene}.png`;
    poster.alt = bodyName() + ' policy evaluated on the common terrain bank';
    const launch = document.createElement('button'); launch.className = 'launch';
    launch.type = 'button'; launch.textContent = 'Play in 3D';
    viewer.append(poster, launch); host.replaceChildren(viewer);
    wireViewer(viewer);
    observeAutomaticScene(viewer);
    caption.textContent = `${stage.label} · ${fmt(stage.replay.cumulativeUpdates)} cumulative PPO updates · Replay 0.0 s`;
    root.dataset.replayUpdates = stage.replay.cumulativeUpdates;
    drawCurves();
  }
  function render(data) {
    if (data.body !== body) return;
    const initialScene=data.stages.find(stage=>stage.id==='initialization')?.replay?.scene;
    const previousInitial=chartData?.body===body?chartData.stages.find(stage=>stage.id==='initialization')?.replay?.scene:null;
    if(previousInitial&&initialScene!==previousInitial){
      host.querySelector('.viewer')?.dispatchEvent(new Event('reset-viewer'));
      currentScene=null;selected='initialization';
    }
    root.dataset.body = body;
    const stages = data.stages;
    curves(data);
    root.querySelector('[data-curriculum-intro]').textContent = data.intro || (body === 'g1'
      ? 'G1 starts from random initialization, with flat locomotion followed by planned terrain adaptation.'
      : body === 'spot_arm'
      ? 'Spot + arm starts from random initialization with the arm physically present. Its own policy learns locomotion, terrain traversal and arm posture adaptation.'
      : 'An arm-free Spot starts from random initialization, learns flat locomotion and then adapts to stairs and slopes. Its physics and policy are independent of Spot + arm.');
    const archived=data.source==='archived-controller';
    root.querySelector('[data-curriculum-reset]').textContent=archived?'Replay first checkpoint':'Replay from update 0';
    root.querySelector('[data-curriculum-reset]').nextElementSibling.textContent=data.replayNote || 'Update 0 shows the random policy before its first action, including the recorded loss of balance.';
    root.querySelector('.curriculum-baseline-note').textContent=data.baselineNote || 'Loss logging begins with PPO update 1. Dashed lines mark the first logged value.';
    const active = stages.find(stage => stage.state === 'training');
    const stopped=stages.find(stage=>['stopped','failed'].includes(stage.state));
    const unknown=stages.some(stage=>stage.state==='unknown');
    status.textContent = active ? `${active.label} in progress · ${fmt(data.numEnvironments)} parallel environments` : stopped ? `Training stopped at update ${fmt(stopped.cumulativeUpdates)}. Later phases have no recorded training.` : unknown ? 'Waiting for the next training status update.' : data.complete ? 'Training schedule complete.' : 'Recorded training progress.';
    if(archived)status.textContent='Recorded controller · 28,000 updates';
    if(stopped&&metricScale(data.curves.map(r=>r.value).filter(Number.isFinite)).logarithmic)
      status.textContent+=' Large recorded loss excursions remain visible on a symmetric log axis.';
    // New exports do not interrupt a camera interaction or an active replay.
    if (requestedStage) {
      const stage=checkpoints(data).find(stage=>stage.id===requestedStage);
      requestedStage=null;
      if(stage){select(stage);host.querySelector('.launch')?.click();}
    } else if (!currentScene) select(checkpoints(data).find(stage=>stage.id===(data.defaultCheckpoint||selected)) || checkpoints(data)[0] || stages[0]);
  }
  root.addEventListener('policy-select-checkpoint',event=>{
    requestedStage=event.detail.stage;
    if(chartData?.body===body)render(chartData);
    else refresh();
  });
  root.querySelector('[data-curriculum-reset]').onclick=()=>{
    const stage=chartData&&checkpoints(chartData)[0];if(!stage)return;
    select(stage);
    const frame=host.querySelector('iframe.scene-ready');
    if(frame)frame.contentWindow.postMessage({type:'clear-playback-command',time:stage.replay.startTime||0,playing:true},'*');
    else host.querySelector('.launch')?.click();
  };
  root.closest('#controller-pretraining').addEventListener('policy-body-change', event => {
    const changed = body !== event.detail.body;
    body = event.detail.body;
    if (changed) {
      host.querySelector('.viewer')?.dispatchEvent(new Event('reset-viewer'));
      host.replaceChildren();
      chartData=null; inspectedStep=null; hoveredChart=null;highlightedPhase=null;
      root.querySelector('[data-curriculum-curves]').replaceChildren();
      delete root.dataset.body;
      status.textContent = 'Loading this robot’s training record.';
      caption.textContent = '';
      selected = 'initialization'; currentScene = null;
      pendingReplayTime=null;
    }
    if (window.CLEAR_BODY_CURRICULA?.[body]) render(window.CLEAR_BODY_CURRICULA[body]);
    refresh();
  });
  function refresh() {
    if (!near || document.hidden || loading) return;
    loading = true;
    const requestedBody = body;
    const script = document.createElement('script');
    const filename=requestedBody==='spot_arm'?'spot_arm-restored-data.js':`${requestedBody}-curriculum-data.js`;
    script.src = `assets/${filename}?t=${Math.floor(Date.now()/30000)}`;
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
    if(pendingReplayTime!==null){
      if(Math.abs(event.data.time-pendingReplayTime)>.2)return;
      pendingReplayTime=null;
    }
    if(chartData?.checkpoints){
      const stage=checkpoints(chartData).findLast(s=>event.data.time+1e-6>=s.replay.startTime);
      if(!stage)return;
      if(selected!==stage.id){selected=stage.id;root.dataset.replayUpdates=stage.replay.cumulativeUpdates;drawCurves();}
      caption.textContent=`${stage.label} · ${fmt(stage.replay.cumulativeUpdates)} cumulative PPO updates · Replay ${(event.data.time-stage.replay.startTime).toFixed(1)} s`;
      return;
    }
    const label = explanations[selected] ? ({initialization:'Initialization',locomotion:'Locomotion',terrain:'Terrain adaptation',arm:'Arm adaptation'})[selected] : selected;
    caption.textContent = `${label} · ${fmt(Number(root.dataset.replayUpdates))} cumulative PPO updates · Replay ${event.data.time.toFixed(1)} s`;
  });
  new IntersectionObserver(entries => { near = entries[0].isIntersecting; if (near) refresh(); }, {rootMargin:'200px'}).observe(root);
  document.addEventListener('visibilitychange', refresh);
  setInterval(refresh, 30000);
})();
