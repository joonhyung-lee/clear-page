/* Numeric training traces are loaded per embodiment, only when the section is nearby. */
(() => {
  const root = document.querySelector('#controller-pretraining'); if (!root) return;
  const charts = [...root.querySelectorAll('[data-loco-chart]')], viewers = [...root.querySelectorAll('[data-loco-viewer]')];
  const colors = ['#306b91', '#ae632d', '#6c5795'];
  const roman = ['I', 'II', 'III', 'IV'];
  const labels = {value:'Value loss', policy:'Policy surrogate loss', entropy:'Policy entropy', reward:'Episode return', terrain:'Mean terrain level', tracking:'Velocity tracking error', arm:'Arm curriculum level'};
  const notes = {g1:'Warm start → terrain adaptation → action rate regularization.', spot:'Nominal arm training → torso control on mixed terrain.', spot_arm:'Continued training with an expanding arm pose curriculum.'};
  const stages={g1:[0,5000,17000,22800],spot:[0,7000,8400,13200],spot_arm:[13200,18000,22600,28000]};
  const stageNames={g1:['Warm start','Terrain adaptation','Terrain adaptation','Action rate regularization'],spot:['Early training','Torso control','Mixed terrain','Final checkpoint'],spot_arm:['Arm curriculum begins','Arm curriculum','Arm curriculum','Final checkpoint']};
  let stageIndex=0, pendingStage=null;
  let source = 'new';
  let body = 'g1', mode = 'optimization', data = null, step = null, hovered = null, near = false, onscreen = false, frame;
  const number = n => Number(n.toPrecision(5)).toString();
  function keys() { return mode === 'optimization' ? ['value','policy','entropy'] : ['reward','terrain',body === 'spot_arm' ? 'arm' : 'tracking']; }
  function activeViewer(){return viewers.find(v=>v.dataset.locoViewer===body);}
  function media(){viewers.forEach(v=>v.hidden=v.dataset.locoViewer!==body);root.querySelector('[data-terrain="random_rough"]').hidden=body!=='g1';}
  function showStage(index,seek=false){
    stageIndex=index;root.dataset.checkpoint=String(stages[body][index]);
    root.querySelector('.loco-checkpoint').textContent='Iteration '+stages[body][index].toLocaleString('en-US')+' · '+stageNames[body][index];
    root.querySelectorAll('[data-loco-stage]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.locoStage)===index)));
    if(seek){const f=activeViewer().querySelector('iframe.scene-ready');if(f){pendingStage=null;f.contentWindow.postMessage({type:'clear-playback-command',time:index*8+.001,playing:!reduced.matches},'*');}else{pendingStage=index;if(!activeViewer().querySelector('.viewer-status'))activeViewer().querySelector('.launch').click();}}
    schedule();
  }
  function stageButtons(){const host=root.querySelector('.loco-stages');host.replaceChildren();stages[body].forEach((iteration,i)=>{const button=document.createElement('button');button.type='button';button.dataset.locoStage=i;button.textContent=(i+1)+' · '+iteration.toLocaleString('en-US');button.setAttribute('aria-label','Checkpoint '+(i+1)+', iteration '+iteration);button.onclick=()=>showStage(i,true);host.append(button);});showStage(0);}
  viewers.forEach(v=>{observeAutomaticScene(v);v.addEventListener('scene-settled',e=>{if(v===activeViewer()&&!e.detail?.failed&&pendingStage!==null)showStage(pendingStage,true);});});
  window.addEventListener('message',e=>{if(e.data?.type!=='clear-playback-time'||e.source!==activeViewer()?.querySelector('iframe')?.contentWindow||!Number.isFinite(e.data.time))return;const index=Math.min(3,Math.floor(e.data.time/8));if(index!==stageIndex)showStage(index);});
  function nearest(rows, x) {
    let lo = 0, hi = rows.length - 1;
    while (lo < hi) { const m = (lo + hi) >> 1; if (rows[m][0] < x) lo = m + 1; else hi = m; }
    return lo && Math.abs(rows[lo-1][0]-x) < Math.abs(rows[lo][0]-x) ? lo-1 : lo;
  }
  function render() {
    frame = null; if (!data) return;
    const metrics = keys();
    charts.forEach((chart,i) => {
      const key = metrics[i], col = data.columns.indexOf(key), canvas = chart.querySelector('canvas'), w = canvas.clientWidth, h = 148;
      if (!w) return;
      const dpr = Math.min(devicePixelRatio || 1,2); canvas.width = w*dpr; canvas.height = h*dpr;
      const ctx = canvas.getContext('2d'); ctx.scale(dpr,dpr);
      chart.dataset.metric = key; chart.querySelector('figcaption').textContent = labels[key];
      canvas.setAttribute('aria-label', labels[key] + '. Dashed lines separate training phases. Numbered ticks match the four replay checkpoints. Use arrow keys, Home and End to inspect iterations.');
      const vals = data.samples.map(r=>r[col]).filter(Number.isFinite);
      const low = Math.min(0,...vals), high = Math.max(...vals,0), pad = (high-low||1)*.08;
      const min = low<0 ? low-pad : 0, max = high+pad, left = 43, right = w-12, top = 27, bottom = h-41;
      const x = n => left+n/data.checkpointIteration*(right-left), y = n => bottom-(n-min)/(max-min)*(bottom-top);
      chart._plot = {left,right};
      ctx.font = '10px Arial'; ctx.lineWidth = 1;
      for (let j=0;j<=2;j++) {
        const v=min+(max-min)*j/2; ctx.strokeStyle='#e9ece5'; ctx.beginPath(); ctx.moveTo(left,y(v)); ctx.lineTo(right,y(v)); ctx.stroke();
        ctx.fillStyle='#7a8472'; ctx.textAlign='right'; ctx.fillText(Number(v.toPrecision(2)).toString(),left-5,y(v)+3);
      }
      // Phase spans describe actual training ancestry, not the four replay samples.
      data.phases.forEach((phase,pi)=>{
        const a=x(phase.start), b=x(data.phases[pi+1]?.start??data.checkpointIteration), middle=(a+b)/2;
        ctx.strokeStyle=colors[pi];ctx.fillStyle=colors[pi];ctx.lineWidth=1;
        ctx.beginPath();ctx.moveTo(a+1,18);ctx.lineTo(a+1,11);ctx.lineTo(b-1,11);ctx.lineTo(b-1,18);ctx.stroke();
        const label='Phase '+roman[pi], width=ctx.measureText(label).width;
        ctx.fillStyle='#fff';ctx.fillRect(middle-width/2-4,4,width+8,14);
        ctx.fillStyle=colors[pi];ctx.textAlign='center';ctx.fillText(label,middle,14);
      });
      ctx.save();ctx.beginPath();ctx.rect(left,top,right-left,bottom-top+1);ctx.clip();
      data.phases.forEach((phase,pi) => {
        ctx.fillStyle=colors[pi]+'19';ctx.fillRect(x(phase.start),top,x(data.phases[pi+1]?.start??data.checkpointIteration)-x(phase.start),bottom-top);
        ctx.strokeStyle=colors[pi];ctx.lineWidth=1.3;ctx.beginPath();let started=false;
        for(const row of data.samples) {
          if(row[1]!==pi)continue;
          if(!Number.isFinite(row[col])){started=false;continue;}
          ctx[started?'lineTo':'moveTo'](x(row[0]),y(row[col]));started=true;
        }
        ctx.stroke();
      });
      data.phases.slice(1).forEach((phase,pi)=>{
        ctx.strokeStyle=colors[pi+1];ctx.lineWidth=1.4;ctx.setLineDash([4,3]);ctx.beginPath();ctx.moveTo(x(phase.start),top);ctx.lineTo(x(phase.start),bottom);ctx.stroke();
      });ctx.restore();ctx.setLineDash([]);
      stages[body].forEach((iteration,index)=>{
        const px=x(iteration),selected=index===stageIndex;
        ctx.strokeStyle=selected?'#35443d':'#abb3aa';ctx.lineWidth=selected?1.2:.7;
        ctx.beginPath();ctx.moveTo(px,selected?top:bottom);ctx.lineTo(px,bottom+4);ctx.stroke();
        ctx.beginPath();ctx.arc(px,bottom+13,7,0,2*Math.PI);ctx.fillStyle=selected?'#35443d':'#e8ece7';ctx.fill();
        ctx.fillStyle=selected?'#fff':'#495548';ctx.textAlign='center';ctx.fillText(String(index+1),px,bottom+16);
        ctx.fillStyle='#65715f';ctx.textAlign=index===0&&iteration===0?'left':index===3?'right':'center';ctx.fillText(iteration===0?'0':number(iteration/1000)+'k',px,h-5);
      });
      if(stages[body][0]!==0){ctx.fillStyle='#65715f';ctx.textAlign='left';ctx.fillText('0',left,h-5);}
      const row = data.samples[nearest(data.samples,step??stages[body][stageIndex])];
      const inspected = row ? {step:row[0],phase:row[1],metric:key,value:row[col]} : null;
      chart.dataset.inspected = JSON.stringify(inspected);
      if(row) {
        ctx.strokeStyle='#99a48e';ctx.setLineDash([2,3]);ctx.beginPath();ctx.moveTo(x(row[0]),top);ctx.lineTo(x(row[0]),bottom);ctx.stroke();ctx.setLineDash([]);
        if(Number.isFinite(row[col])){ctx.beginPath();ctx.arc(x(row[0]),y(row[col]),3.5,0,2*Math.PI);ctx.fillStyle=colors[row[1]];ctx.fill();ctx.strokeStyle='#fff';ctx.stroke();}
      }
      const tip = chart.querySelector('.loco-tooltip');tip.hidden=hovered!==chart||!row;
      if(!tip.hidden) {
        tip.replaceChildren();const title=document.createElement('strong'),phase=document.createElement('span'),val=document.createElement('div');
        title.textContent='Iteration '+row[0].toLocaleString('en-US');phase.textContent='Phase '+roman[row[1]]+' · '+data.phases[row[1]].label;val.textContent=labels[key]+': '+(Number.isFinite(row[col])?number(row[col]):'Not recorded');tip.append(title,phase,val);
        tip.style.left=Math.max(0,Math.min(w-tip.offsetWidth,x(row[0])+8))+'px';tip.style.top='16px';
      }
    });
  }
  function schedule() { if (!frame) frame=requestAnimationFrame(render); }
  async function load() {
    const requested=body;
    const recorded = (body === 'g1' || body === 'spot_arm') && source === 'recorded';
    root.querySelector('[data-policy-recorded]').hidden = !recorded;
    root.querySelector('#spot-curriculum').hidden = recorded;
    root.querySelector('.policy-sources').hidden = body === 'spot';
    root.dataset.body = body;
    root.dataset.source = recorded ? 'recorded' : 'new';
    root.dispatchEvent(new CustomEvent('policy-body-change', {detail:{body, recorded}}));
    if (!recorded) return;
    root.querySelector('.loco-body-note').textContent=notes[body];
    stageButtons();media();
    root.querySelector('.loco-loading').hidden=false;root.querySelector('.loco-charts').hidden=true;
    try {
      await loadScript('assets/locomotion-training-'+requested+'.js',()=>!!window.CLEAR_LOCOMOTION_DATA?.[requested]);
      if(body!==requested)return;
      data=window.CLEAR_LOCOMOTION_DATA[body];step=null;hovered=null;
      showStage(stageIndex);
      root.querySelector('.loco-loading').hidden=true;root.querySelector('.loco-charts').hidden=false;
      const legend=root.querySelector('.loco-phases');legend.replaceChildren();data.phases.forEach((p,i)=>{const label=document.createElement('span');label.style.setProperty('--phase',colors[i]);label.textContent='Phase '+roman[i]+' · '+p.label;legend.append(label);});
      root.dataset.body=body;render();
    } catch {
      if(body!==requested)return;
      const node=root.querySelector('.loco-loading');node.replaceChildren(document.createTextNode('Training curves could not load. '));const button=document.createElement('button');button.textContent='Retry';button.onclick=load;node.append(button);
    }
  }
  root.querySelectorAll('[data-loco-body]').forEach(button=>button.onclick=()=>{if(body===button.dataset.locoBody)return;body=button.dataset.locoBody;source='new';data=null;pendingStage=null;root.querySelectorAll('[data-loco-body]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));root.querySelectorAll('[data-loco-source]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.locoSource===source)));load();});
  root.querySelectorAll('[data-loco-source]').forEach(button=>button.onclick=()=>{source=button.dataset.locoSource;data=null;root.querySelectorAll('[data-loco-source]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));load();});
  if(location.hash==='#spot-curriculum')root.querySelector('[data-loco-body="spot"]').click();
  root.querySelectorAll('[data-loco-metrics]').forEach(button=>button.onclick=()=>{mode=button.dataset.locoMetrics;root.querySelectorAll('[data-loco-metrics]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();});
  for(const chart of charts) {
    const canvas=chart.querySelector('canvas');
    const inspect=e=>{if(!data||!chart._plot)return;const r=canvas.getBoundingClientRect(),p=chart._plot;step=data.samples[nearest(data.samples,(e.clientX-r.left-p.left)/(p.right-p.left)*data.checkpointIteration)][0];hovered=chart;schedule();};
    canvas.addEventListener('pointermove',inspect);canvas.addEventListener('pointerdown',inspect);
    canvas.addEventListener('pointerleave',()=>{if(document.activeElement!==canvas){step=null;hovered=null;schedule();}});
    canvas.addEventListener('focus',()=>{if(data){step??=data.samples[0][0];hovered=chart;schedule();}});
    canvas.addEventListener('blur',()=>{step=null;hovered=null;schedule();});
    canvas.addEventListener('keydown',e=>{
      if(!data||!['ArrowLeft','ArrowRight','Home','End','Escape'].includes(e.key))return;e.preventDefault();
      if(e.key==='Escape'){canvas.blur();return;}
      let i=nearest(data.samples,step??0);i=e.key==='Home'?0:e.key==='End'?data.samples.length-1:Math.max(0,Math.min(data.samples.length-1,i+(e.key==='ArrowRight'?1:-1)));
      step=data.samples[i][0];hovered=chart;render();const point=JSON.parse(chart.dataset.inspected);
      root.querySelector('.loco-status').textContent=labels[point.metric]+', iteration '+point.step+', '+(point.value===null?'not recorded':number(point.value));
    });
  }
  new IntersectionObserver(entries=>{near=entries[0].isIntersecting;if(near&&!data)load();media();},{rootMargin:'0px'}).observe(root);
  new IntersectionObserver(entries=>{onscreen=entries[0].isIntersecting;media();},{threshold:0}).observe(root);
  document.addEventListener('visibilitychange',media);new ResizeObserver(schedule).observe(root);
})();
