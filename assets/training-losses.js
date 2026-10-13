/* One original CLEAR run. Shading is local step variation, never seed uncertainty. */
(() => {
  const root = document.querySelector('#training-losses');
  if (!root) return;
  const charts = [...root.querySelectorAll('[data-loss]')], series = new Map();
  let data, pendingLoad, index = null, hovered = null, scheduled = false, selectedRole = null;
  let pointerPreview = null, focusPreview = null;
  const roleKeys={order:['selection','order','kl'],flow:['flow'],affordance:['affordance'],availability:[]};
  const palette=window.CLEAR_DESIGN.colors;
  const termColors={selection:palette.blue[600],order:palette.purple[600],kl:palette.gray[600],flow:palette.green[600],affordance:palette.mint[600],availability:palette.red[600]};
  const roleHelp={order:'Object selection, pairwise ranking, and Gaussian score regularization.',flow:'Flow matching for continuous object references under a fixed interaction order.',affordance:'Binary supervision of interaction availability and terrain-transition feasibility.',availability:'Weight 0: this term contributes zero to the displayed objective. No loss curve was logged.'};
  const termHelp=document.createElement('div');termHelp.id='loss-term-help';termHelp.className='loss-term-help';termHelp.setAttribute('role','tooltip');termHelp.hidden=true;root.append(termHelp);
  root.querySelectorAll('.objective-term').forEach(term=>term.setAttribute('aria-describedby',termHelp.id));
  const value = n => Number(n.toPrecision(6)).toString();
  function nearest(target) {
    let lo = 0, hi = data.samples.length - 1;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (data.samples[mid].step < target) lo = mid + 1; else hi = mid; }
    return lo && Math.abs(data.samples[lo - 1].step - target) < Math.abs(data.samples[lo].step - target) ? lo - 1 : lo;
  }
  function renderChart(chart) {
    const key = chart.dataset.loss, canvas = chart.querySelector('canvas'), rows = series.get(key);
    const w = canvas.clientWidth, h = key === 'loss' ? 320 : 200, dpr = Math.min(devicePixelRatio || 1, 2);
    if (!w) return;
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); canvas.style.height = h + 'px';
    const ctx = canvas.getContext('2d'); ctx.scale(dpr, dpr);
    const left = 50, right = w - 12, top = 14, bottom = h - 40;
    const maximum = Math.max(...rows.map(row => Math.max(row.raw, row.mean + row.std)));
    const unit = 10 ** Math.floor(Math.log10(maximum || 1));
    const ymax = Math.ceil(maximum / unit * 2) / 2 * unit || 1;
    const x = n => left + n / data.maxStep * (right - left), y = n => bottom - n / ymax * (bottom - top);
    chart._plot = {left, right};
    ctx.font = '13px B612 Mono'; ctx.fillStyle = '#6a7282'; ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const v = ymax * i / 4;
      ctx.strokeStyle = '#e5e7eb'; ctx.beginPath(); ctx.moveTo(left, y(v)); ctx.lineTo(right, y(v)); ctx.stroke();
      ctx.textAlign = 'right'; ctx.fillText(Number(v.toPrecision(3)).toString(), left - 6, y(v) + 4);
    }
    const ticks = w < 300 ? 2 : 4;
    for (let i = 0; i <= ticks; i++) {
      const t = data.maxStep * i / ticks;
      ctx.textAlign = i === ticks ? 'right' : i === 0 ? 'left' : 'center'; ctx.fillText(t ? (t / 1000) + 'k' : '0', x(t), h - 15);
    }
    ctx.textAlign = 'right'; ctx.fillText('Step', right, h - 4);
    ctx.save(); ctx.beginPath(); ctx.rect(left, top, right - left, bottom - top + 1); ctx.clip();
    ctx.beginPath();
    rows.forEach((row, i) => ctx[i ? 'lineTo' : 'moveTo'](x(row.step), y(row.mean + row.std)));
    for (let i = rows.length - 1; i >= 0; i--) ctx.lineTo(x(rows[i].step), y(Math.max(0, rows[i].mean - rows[i].std)));
    ctx.closePath(); ctx.fillStyle = termColors[key]||palette.green[600]; ctx.globalAlpha=.18;ctx.fill();ctx.globalAlpha=1;
    ctx.beginPath(); rows.forEach((row, i) => ctx[i ? 'lineTo' : 'moveTo'](x(row.step), y(row.mean)));
    ctx.strokeStyle = termColors[key]||palette.green[600]; ctx.lineWidth = 1.6; ctx.stroke(); ctx.restore();
    const row = index === null ? null : rows[index];
    chart.dataset.inspected = JSON.stringify(row); chart.dataset.inspectedStep = row?.step ?? '';
    if (row) {
      ctx.strokeStyle = '#99a1af'; ctx.setLineDash([3, 4]); ctx.beginPath(); ctx.moveTo(x(row.step), top); ctx.lineTo(x(row.step), bottom); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = termColors[key]||palette.green[600]; ctx.beginPath(); ctx.arc(x(row.step), y(row.mean), 3.5, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(x(row.step), y(row.raw), 4, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); ctx.strokeStyle = termColors[key]||palette.green[600]; ctx.lineWidth = 1.5; ctx.stroke();
    }
    const tooltip = chart.querySelector('.loss-tooltip'); tooltip.hidden = hovered !== chart || !row;
    if (!tooltip.hidden) {
      tooltip.replaceChildren(); const heading = document.createElement('strong'); heading.textContent = 'Step ' + row.step.toLocaleString('en-US'); tooltip.append(heading);
      for (const [label, n] of [['Raw loss', row.raw], ['Local mean', row.mean], ['Std. deviation', row.std]]) {
        const entry = document.createElement('div'); entry.className = 'loss-tooltip-row';
        const name = document.createElement('span'), metric = document.createElement('span'); name.textContent = label; metric.textContent = value(n); entry.append(name, metric); tooltip.append(entry);
      }
      tooltip.style.left = Math.max(0, Math.min(w - tooltip.offsetWidth, x(row.step) + 12)) + 'px';
      tooltip.style.top = (canvas.offsetTop + 14) + 'px';
    }
  }
  function renderComposition(){
    const holder=root.querySelector('[data-loss-composition]');if(!holder)return;
    const weights=data.weights||{kl:.001,flow:1,affordance:1,availability:0};
    const row=data.samples[index??data.samples.length-1],items=[['selection','Selection',1],['order','Ranking',1],['kl','KL × '+weights.kl,weights.kl],['flow','Flow',weights.flow],['affordance','Affordance',weights.affordance]];
    if(weights.availability>0)items.push(['availability','Availability × '+weights.availability,weights.availability]);
    const title=document.createElement('p');title.textContent='Step '+row.step.toLocaleString('en-US')+' · Weighted contributions → total '+value(row.loss);
    const bar=document.createElement('div');bar.className='loss-contribution-bar';bar.setAttribute('aria-hidden','true');
    const legend=document.createElement('div');legend.className='loss-contribution-values';
    for(const [key,label,weight]of items){
      const contribution=row[key]*weight,segment=document.createElement('span');segment.style.flexGrow=String(contribution);segment.style.background=termColors[key];bar.append(segment);
      const item=document.createElement('span');const swatch=document.createElement('i');swatch.style.background=termColors[key];item.append(swatch,document.createTextNode(label+' '+value(contribution)));legend.append(item);
    }
    if(!weights.availability){const inactive=document.createElement('span');inactive.textContent='Availability × 0 = 0';legend.append(inactive);}
    holder.replaceChildren(title,bar,legend);
  }
  function render() { if (data) {charts.forEach(renderChart);renderComposition();} }
  function schedule() { if (scheduled) return; scheduled = true; requestAnimationFrame(() => { scheduled = false; render(); }); }
  function inspect(chart, target) { index = nearest(target); hovered = chart; schedule(); }
  function initialize() {
    if (data) return Promise.resolve();
    if (!pendingLoad) pendingLoad = loadData();
    return pendingLoad;
  }
  async function loadData() {
    try {
      await loadScript('assets/training-loss-data.js', () => !!window.CLEAR_TRAINING_LOSSES);
      data = window.CLEAR_TRAINING_LOSSES;
      const weights=data.weights||{kl:.001,flow:1,affordance:1,availability:0};
      if(weights.availability>0&&data.samples.every(row=>Number.isFinite(row.availability))){
        roleKeys.availability=['availability'];
        roleHelp.availability='Penalizes unavailable first interactions through selection probabilities and priority scores. Weight '+weights.availability+'.';
        const chart=document.createElement('figure');chart.className='training-loss-chart';chart.id='loss-availability';chart.dataset.loss='availability';
        chart.innerHTML='<figcaption><h5>(f) Availability</h5><p>Feasible first interactions.</p></figcaption><canvas aria-label="Availability loss. Use left and right arrows to inspect recorded steps." role="img" tabindex="0"></canvas><div class="loss-tooltip" hidden></div>';
        const grid=root.querySelector('.loss-chart-grid');grid.append(chart);grid.classList.add('has-availability');grid.setAttribute('aria-label','Six component training losses');charts.push(chart);bindPreview(chart,chart.querySelector('canvas'));
        const state=root.querySelector('.availability-state');if(state)state.textContent='λavail = '+weights.availability;
        root.querySelector('.loss-scope:not(.loss-band-note)').textContent='Objective weights: λflow = '+weights.flow+', λKL = '+weights.kl+', λaff = '+weights.affordance+', λavail = '+weights.availability+'. Hover a curve to inspect its recorded values.';
      }
      root.querySelector('#loss-loss figcaption p').textContent=data.maxStep.toLocaleString('en-US')+' training steps';
      const radius = Math.floor(data.window / 2);
      for (const chart of charts) {
        const key = chart.dataset.loss;
        series.set(key, data.samples.map((row, i) => {
          const local = data.samples.slice(Math.max(0, i - radius), i + radius + 1).map(s => s[key]);
          const mean = local.reduce((sum, n) => sum + n, 0) / local.length;
          return {step:row.step, raw:row[key], mean, std:Math.sqrt(local.reduce((sum, n) => sum + (n - mean) ** 2, 0) / local.length)};
        }));
        const canvas = chart.querySelector('canvas');
        const pointerInspect = e => { const box = canvas.getBoundingClientRect(), plot = chart._plot; if (plot) inspect(chart, (e.clientX - box.left - plot.left) / (plot.right - plot.left) * data.maxStep); };
        canvas.addEventListener('pointermove', pointerInspect); canvas.addEventListener('pointerdown', pointerInspect);
        canvas.addEventListener('pointerleave', () => { if (document.activeElement === canvas) return; index = null; hovered = null; schedule(); });
        canvas.addEventListener('focus', () => { inspect(chart, data.samples[index ?? 0].step); });
        canvas.addEventListener('blur', () => { hovered = null; index = null; schedule(); });
        canvas.addEventListener('keydown', e => {
          if (!['ArrowLeft','ArrowRight','Home','End','Escape'].includes(e.key)) return; e.preventDefault();
          if (e.key === 'Escape') { canvas.blur(); return; }
          index = e.key === 'Home' ? 0 : e.key === 'End' ? data.samples.length - 1 : Math.max(0, Math.min(data.samples.length - 1, (index ?? 0) + (e.key === 'ArrowRight' ? 1 : -1)));
          hovered = chart; render(); const row = series.get(key)[index];
          root.querySelector('.loss-keyboard-status').textContent = chart.querySelector('h5').textContent + ', step ' + row.step.toLocaleString('en-US') + '. Raw loss ' + value(row.raw) + ', local mean ' + value(row.mean) + ', standard deviation ' + value(row.std) + '.';
        });
      }
      root.querySelector('.loss-loading').hidden = true; root.querySelector('.loss-content').hidden = false;
      new ResizeObserver(schedule).observe(root); render();
    } catch {
      data = null; const node = root.querySelector('.loss-loading'); node.textContent = 'Training curves could not load. ';
      const retry = document.createElement('button'); retry.type = 'button'; retry.textContent = 'Retry'; retry.onclick = () => { pendingLoad = null; retry.remove(); initialize(); }; node.append(retry);
    }
  }
  const roleForTerm = term => Object.keys(roleKeys).find(key => term.classList.contains('term-' + key));
  const roleForLoss = key => Object.keys(roleKeys).find(role => roleKeys[role].includes(key));
  const previewFor = node => {
    const role = node.dataset.objectiveRole || roleForTerm(node) || roleForLoss(node.dataset.loss || node.dataset.lossTerm);
    const loss = node.dataset.loss || node.dataset.lossTerm;
    return {node, role, keys:loss ? [loss] : roleKeys[role] || []};
  };
  function paintInteraction() {
    const preview = pointerPreview || focusPreview;
    showRole(preview?.role || selectedRole || 'order');
    const selectedKeys = roleKeys[selectedRole] || [];
    charts.forEach(chart => {
      chart.classList.toggle('loss-term-active', !!preview?.keys.includes(chart.dataset.loss));
      chart.classList.toggle('loss-term-selected', selectedKeys.includes(chart.dataset.loss));
    });
    root.querySelectorAll('[data-objective-role], .objective-term').forEach(node => {
      const role = node.dataset.objectiveRole || roleForTerm(node);
      node.classList.toggle('loss-role-preview', !!preview && preview.role === role);
      node.setAttribute('aria-pressed', String(role === selectedRole));
    });
  }
  function showRole(key) {
    root.querySelectorAll('[data-role-panel]').forEach(panel => panel.hidden = panel.dataset.rolePanel !== key);
  }
  function selectRole(key) {
    if (!roleKeys[key]) return;
    selectedRole = selectedRole === key ? null : key;
    showRole(key);
    termHelp.hidden = true;
    paintInteraction();
  }
  function showHelp(term) {
    const key = roleForTerm(term);
    if (!key) return;
    termHelp.textContent = roleHelp[key]; termHelp.hidden = false;
    const box = term.getBoundingClientRect();
    termHelp.style.left = Math.max(12, Math.min(innerWidth - termHelp.offsetWidth - 12, box.left)) + 'px';
    termHelp.style.top = Math.max(12, Math.min(innerHeight - termHelp.offsetHeight - 12, box.bottom + 12)) + 'px';
  }
  function bindPreview(node, focusNode = node) {
    node.addEventListener('pointerenter', e => {
      if (e.pointerType === 'touch') return;
      pointerPreview = previewFor(node); paintInteraction();
      if (node.matches('.objective-term')) showHelp(node);
    });
    node.addEventListener('pointerleave', () => {
      if (pointerPreview?.node === node) pointerPreview = null;
      termHelp.hidden = true; paintInteraction();
    });
    focusNode.addEventListener('focus', () => {
      if (!focusNode.matches(':focus-visible')) return;
      focusPreview = previewFor(node); paintInteraction();
      if (node.matches('.objective-term')) showHelp(node);
    });
    focusNode.addEventListener('blur', () => {
      if (focusPreview?.node === node) focusPreview = null;
      termHelp.hidden = true; paintInteraction();
    });
  }
  const rolePanels=[...root.querySelectorAll('[data-role-panel]')];
  const panelStack=document.createElement('div');panelStack.className='loss-role-panels';
  rolePanels[0]?.before(panelStack);
  rolePanels.forEach(panel => {panel.id = 'loss-role-' + panel.dataset.rolePanel;panelStack.append(panel);});
  root.querySelectorAll('[data-objective-role], .objective-term').forEach(node => {
    const role = node.dataset.objectiveRole || roleForTerm(node);
    node.setAttribute('aria-controls', ['loss-role-' + role, ...(roleKeys[role] || []).map(key => 'loss-' + key)].join(' '));
    if (node.matches('.objective-term')) node.removeAttribute('title');
    bindPreview(node);
    node.addEventListener('click', () => selectRole(role));
    if (node.matches('.objective-term')) node.addEventListener('keydown', e => {
      if (['Enter', ' '].includes(e.key)) {e.preventDefault(); selectRole(role);}
    });
  });
  charts.forEach(chart => bindPreview(chart, chart.querySelector('canvas')));
  root.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    selectedRole = null; pointerPreview = null; focusPreview = null;
    termHelp.hidden = true; paintInteraction();
  });
  addEventListener('scroll', () => {termHelp.hidden = true;}, {passive:true});
  addEventListener('resize', () => {termHelp.hidden = true;});
  showRole('order'); paintInteraction();
  root.querySelectorAll('[data-loss-term]').forEach(button => {
    bindPreview(button);
    button.onclick = async () => {
      await initialize(); if (!data) return;
      const chart = charts.find(c => c.dataset.loss === button.dataset.lossTerm);
      if (!chart) return;
      chart.scrollIntoView({behavior:reduced.matches ? 'instant' : 'smooth', block:'center'});
      chart.querySelector('canvas').focus({preventScroll:true});
    };
  });
  new IntersectionObserver(entries => { if (entries.some(e => e.isIntersecting)) initialize(); }, {rootMargin:'250px'}).observe(root);
})();
