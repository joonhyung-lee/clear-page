/* Numeric training traces are loaded per embodiment, only when the section is nearby. */
(() => {
  const root = document.querySelector('#controller-pretraining'); if (!root) return;
  const charts = [...root.querySelectorAll('[data-loco-chart]')], videos = [...root.querySelectorAll('video')];
  const colors = ['#64879b', '#9d8760', '#708963'];
  const labels = {value:'Value loss', policy:'Policy surrogate loss', entropy:'Policy entropy', reward:'Episode return', terrain:'Mean terrain level', tracking:'Velocity tracking error', arm:'Arm curriculum level'};
  const notes = {g1:'Terrain adapted G1 policy with action rate regularization.', spot:'Nominal arm pretraining transferred to the arm free body.', spot_arm:'Arm pose curriculum with the deployed folded pose.'};
  let body = 'g1', mode = 'optimization', data = null, step = null, hovered = null, near = false, onscreen = false, frame;
  const number = n => Number(n.toPrecision(5)).toString();
  function keys() { return mode === 'optimization' ? ['value','policy','entropy'] : ['reward','terrain',body === 'spot_arm' ? 'arm' : 'tracking']; }
  function media() {
    for (const video of videos) {
      const selected = video.dataset.locoVideo === body; video.hidden = !selected;
      if (selected && near && !video.getAttribute('src')) { video.src = clearAssetURL(video.dataset.src); video.load(); }
      if ((!selected || !onscreen || document.hidden) && !video.paused) video.pause();
      if (selected && onscreen && !document.hidden && video.readyState >= 2 && !video.dataset.started && !reduced.matches) { video.dataset.started='true'; video.play().catch(() => { delete video.dataset.started; }); }
    }
  }
  videos.forEach(video => video.addEventListener('loadeddata',media));
  function nearest(rows, x) {
    let lo = 0, hi = rows.length - 1;
    while (lo < hi) { const m = (lo + hi) >> 1; if (rows[m][0] < x) lo = m + 1; else hi = m; }
    return lo && Math.abs(rows[lo-1][0]-x) < Math.abs(rows[lo][0]-x) ? lo-1 : lo;
  }
  function render() {
    frame = null; if (!data) return;
    const metrics = keys();
    charts.forEach((chart,i) => {
      const key = metrics[i], col = data.columns.indexOf(key), canvas = chart.querySelector('canvas'), w = canvas.clientWidth, h = 104;
      if (!w) return;
      const dpr = Math.min(devicePixelRatio || 1,2); canvas.width = w*dpr; canvas.height = h*dpr;
      const ctx = canvas.getContext('2d'); ctx.scale(dpr,dpr);
      chart.dataset.metric = key; chart.querySelector('figcaption').textContent = labels[key];
      canvas.setAttribute('aria-label', labels[key] + '. Use arrow keys, Home and End to inspect iterations.');
      const vals = data.samples.map(r=>r[col]).filter(Number.isFinite);
      const low = Math.min(0,...vals), high = Math.max(...vals,0), pad = (high-low||1)*.08;
      const min = low<0 ? low-pad : 0, max = high+pad, left = 43, right = w-10, top = 6, bottom = h-23;
      const x = n => left+n/data.checkpointIteration*(right-left), y = n => bottom-(n-min)/(max-min)*(bottom-top);
      chart._plot = {left,right};
      ctx.font = '10px Arial'; ctx.lineWidth = 1;
      for (let j=0;j<=2;j++) {
        const v=min+(max-min)*j/2; ctx.strokeStyle='#e9ece5'; ctx.beginPath(); ctx.moveTo(left,y(v)); ctx.lineTo(right,y(v)); ctx.stroke();
        ctx.fillStyle='#7a8472'; ctx.textAlign='right'; ctx.fillText(Number(v.toPrecision(2)).toString(),left-5,y(v)+3);
        const t=data.checkpointIteration*j/2; ctx.textAlign=j===0?'left':j===2?'right':'center'; ctx.fillText(Number((t/1000).toFixed(1))+'k',x(t),h-8);
      }
      ctx.save();ctx.beginPath();ctx.rect(left,top,right-left,bottom-top+1);ctx.clip();
      data.phases.forEach((phase,pi) => {
        ctx.fillStyle=colors[pi]+'0a';ctx.fillRect(x(phase.start),top,x(phase.end)-x(phase.start),bottom-top);
        ctx.strokeStyle=colors[pi];ctx.lineWidth=1.3;ctx.beginPath();let started=false;
        for(const row of data.samples) {
          if(row[1]!==pi)continue;
          if(!Number.isFinite(row[col])){started=false;continue;}
          ctx[started?'lineTo':'moveTo'](x(row[0]),y(row[col]));started=true;
        }
        ctx.stroke();
      });ctx.restore();
      const row = step===null ? null : data.samples[nearest(data.samples,step)];
      const inspected = row ? {step:row[0],phase:row[1],metric:key,value:row[col]} : null;
      chart.dataset.inspected = JSON.stringify(inspected);
      if(row) {
        ctx.strokeStyle='#99a48e';ctx.setLineDash([2,3]);ctx.beginPath();ctx.moveTo(x(row[0]),top);ctx.lineTo(x(row[0]),bottom);ctx.stroke();ctx.setLineDash([]);
        if(Number.isFinite(row[col])){ctx.beginPath();ctx.arc(x(row[0]),y(row[col]),3.5,0,2*Math.PI);ctx.fillStyle=colors[row[1]];ctx.fill();ctx.strokeStyle='#fff';ctx.stroke();}
      }
      const tip = chart.querySelector('.loco-tooltip');tip.hidden=hovered!==chart||!row;
      if(!tip.hidden) {
        tip.replaceChildren();const title=document.createElement('strong'),phase=document.createElement('span'),val=document.createElement('div');
        title.textContent='Iteration '+row[0].toLocaleString('en-US');phase.textContent=data.phases[row[1]].label;val.textContent=labels[key]+': '+(Number.isFinite(row[col])?number(row[col]):'Not recorded');tip.append(title,phase,val);
        tip.style.left=Math.max(0,Math.min(w-tip.offsetWidth,x(row[0])+8))+'px';tip.style.top='16px';
      }
    });
  }
  function schedule() { if (!frame) frame=requestAnimationFrame(render); }
  async function load() {
    const requested=body;
    root.querySelector('.loco-body-note').textContent=notes[body];
    root.querySelector('.loco-checkpoint').textContent='';media();
    root.querySelector('.loco-loading').hidden=false;root.querySelector('.loco-charts').hidden=true;
    try {
      await loadScript('assets/locomotion-training-'+requested+'.js',()=>!!window.CLEAR_LOCOMOTION_DATA?.[requested]);
      if(body!==requested)return;
      data=window.CLEAR_LOCOMOTION_DATA[body];step=null;hovered=null;
      root.querySelector('.loco-checkpoint').textContent='Checkpoint · iteration '+data.checkpointIteration.toLocaleString('en-US');
      root.querySelector('.loco-loading').hidden=true;root.querySelector('.loco-charts').hidden=false;
      const legend=root.querySelector('.loco-phases');legend.replaceChildren();data.phases.forEach((p,i)=>{const label=document.createElement('span');label.style.setProperty('--phase',colors[i]);label.textContent=p.label;legend.append(label);});
      root.dataset.body=body;render();
    } catch {
      if(body!==requested)return;
      const node=root.querySelector('.loco-loading');node.replaceChildren(document.createTextNode('Training curves could not load. '));const button=document.createElement('button');button.textContent='Retry';button.onclick=load;node.append(button);
    }
  }
  root.querySelectorAll('[data-loco-body]').forEach(button=>button.onclick=()=>{if(body===button.dataset.locoBody)return;body=button.dataset.locoBody;data=null;root.querySelectorAll('[data-loco-body]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));load();});
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
  new IntersectionObserver(entries=>{near=entries[0].isIntersecting;if(near&&!data)load();media();},{rootMargin:'180px'}).observe(root);
  new IntersectionObserver(entries=>{onscreen=entries[0].isIntersecting;media();},{threshold:0}).observe(root);
  document.addEventListener('visibilitychange',media);new ResizeObserver(schedule).observe(root);
})();
