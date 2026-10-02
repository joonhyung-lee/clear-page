/* One original CLEAR run. Shading is local step variation, never seed uncertainty. */
(() => {
  const root = document.querySelector('#training-losses');
  if (!root) return;
  const charts = [...root.querySelectorAll('[data-loss]')], series = new Map();
  let data, pendingLoad, pinnedTerm = null, index = null, hovered = null, scheduled = false;
  const value = n => Number(n.toPrecision(6)).toString();
  function nearest(target) {
    let lo = 0, hi = data.samples.length - 1;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (data.samples[mid].step < target) lo = mid + 1; else hi = mid; }
    return lo && Math.abs(data.samples[lo - 1].step - target) < Math.abs(data.samples[lo].step - target) ? lo - 1 : lo;
  }
  function renderChart(chart) {
    const key = chart.dataset.loss, canvas = chart.querySelector('canvas'), rows = series.get(key);
    const w = canvas.clientWidth, h = key === 'loss' ? 260 : 200, dpr = Math.min(devicePixelRatio || 1, 2);
    if (!w) return;
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); canvas.style.height = h + 'px';
    const ctx = canvas.getContext('2d'); ctx.scale(dpr, dpr);
    const left = 50, right = w - 12, top = 14, bottom = h - 40;
    const maximum = Math.max(...rows.map(row => Math.max(row.raw, row.mean + row.std)));
    const unit = 10 ** Math.floor(Math.log10(maximum || 1));
    const ymax = Math.ceil(maximum / unit * 2) / 2 * unit || 1;
    const x = n => left + n / data.maxStep * (right - left), y = n => bottom - n / ymax * (bottom - top);
    chart._plot = {left, right};
    ctx.font = '13px Arial'; ctx.fillStyle = '#73796e'; ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const v = ymax * i / 4;
      ctx.strokeStyle = '#e8ece4'; ctx.beginPath(); ctx.moveTo(left, y(v)); ctx.lineTo(right, y(v)); ctx.stroke();
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
    ctx.closePath(); ctx.fillStyle = 'rgba(70,123,154,.18)'; ctx.fill();
    ctx.beginPath(); rows.forEach((row, i) => ctx[i ? 'lineTo' : 'moveTo'](x(row.step), y(row.mean)));
    ctx.strokeStyle = '#467b9a'; ctx.lineWidth = 1.6; ctx.stroke(); ctx.restore();
    const row = index === null ? null : rows[index];
    chart.dataset.inspected = JSON.stringify(row); chart.dataset.inspectedStep = row?.step ?? '';
    if (row) {
      ctx.strokeStyle = '#939f89'; ctx.setLineDash([3, 4]); ctx.beginPath(); ctx.moveTo(x(row.step), top); ctx.lineTo(x(row.step), bottom); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = '#467b9a'; ctx.beginPath(); ctx.arc(x(row.step), y(row.mean), 3.5, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(x(row.step), y(row.raw), 4, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); ctx.strokeStyle = '#467b9a'; ctx.lineWidth = 1.5; ctx.stroke();
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
  function render() { if (data) charts.forEach(renderChart); }
  function schedule() { if (scheduled) return; scheduled = true; requestAnimationFrame(() => { scheduled = false; render(); }); }
  function inspect(chart, target) { index = nearest(target); hovered = chart; schedule(); }
  function initialize() {
    if (data) return Promise.resolve();
    if (!pendingLoad) pendingLoad = loadData().finally(() => { pendingLoad = null; });
    return pendingLoad;
  }
  async function loadData() {
    try {
      await loadScript('assets/training-loss-data.js', () => !!window.CLEAR_TRAINING_LOSSES);
      data = window.CLEAR_TRAINING_LOSSES;
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
        canvas.addEventListener('focus', () => { pinnedTerm = key; highlight(key); inspect(chart, data.samples[index ?? 0].step); });
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
      const retry = document.createElement('button'); retry.type = 'button'; retry.textContent = 'Retry'; retry.onclick = initialize; node.append(retry);
    }
  }
  function highlight(key) { key ??= pinnedTerm; const keys=Array.isArray(key)?key:[key]; charts.forEach(chart => chart.classList.toggle('loss-term-active', keys.includes(chart.dataset.loss))); root.querySelectorAll('[data-loss-term]').forEach(button => button.classList.toggle('loss-term-active', keys.includes(button.dataset.lossTerm))); }
  const termKeys=term=>term.classList.contains('term-order')?['selection','order','kl']:term.classList.contains('term-flow')?['flow']:term.classList.contains('term-affordance')?['affordance']:['loss'];
  function inspectTerm(term){
    const keys=termKeys(term);highlight(keys);
    const chart=charts.find(c=>c.dataset.loss===keys[0]),strip=root.querySelector('.loss-chart-grid');
    if(chart&&strip.contains(chart))strip.scrollTo({left:chart.getBoundingClientRect().left-strip.getBoundingClientRect().left+strip.scrollLeft,behavior:reduced.matches?'instant':'smooth'});
  }
  root.addEventListener('pointerover',e=>{const term=e.target.closest('.objective-term');if(term&&!term.contains(e.relatedTarget))inspectTerm(term);});
  root.addEventListener('pointerout',e=>{const term=e.target.closest('.objective-term');if(term&&!term.contains(e.relatedTarget))highlight(null);});
  root.addEventListener('focusin',e=>{const term=e.target.closest('.objective-term');if(term)inspectTerm(term);});
  root.addEventListener('focusout',e=>{if(e.target.closest('.objective-term'))highlight(null);});
  root.addEventListener('click',e=>{const term=e.target.closest('.objective-term');if(term)inspectTerm(term);});
  root.addEventListener('keydown',e=>{const term=e.target.closest('.objective-term');if(term&&['Enter',' '].includes(e.key)){e.preventDefault();inspectTerm(term);}});
  root.querySelectorAll('[data-loss-term]').forEach(button => {
    button.addEventListener('pointerenter', () => highlight(button.dataset.lossTerm)); button.addEventListener('pointerleave', () => highlight(null));
    button.addEventListener('focus', () => highlight(button.dataset.lossTerm)); button.addEventListener('blur', () => highlight(null));
    button.onclick = async () => { pinnedTerm = button.dataset.lossTerm; await initialize(); if (!data) return; const chart = charts.find(c => c.dataset.loss === button.dataset.lossTerm); chart.scrollIntoView({behavior:reduced.matches ? 'instant' : 'smooth', block:'center'}); chart.querySelector('canvas').focus({preventScroll:true}); highlight(button.dataset.lossTerm); };
  });
  new IntersectionObserver(entries => { if (entries.some(e => e.isIntersecting)) initialize(); }, {rootMargin:'250px'}).observe(root);
})();
