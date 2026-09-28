function clearAssetURL(path) { const base=path.split('?')[0], version=window.CLEAR_ASSET_REVISIONS?.[base]; return version ? base+'?v='+version : path; }
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const hoverAvailable = matchMedia('(hover: hover) and (pointer: fine)');
const teaser = document.querySelector('#teaser');
const heroToggle = document.querySelector('#hero-toggle');
function updateHero() { heroToggle.textContent = teaser.paused ? 'Play teaser' : 'Pause teaser'; }
if (reduced.matches) teaser.pause();
heroToggle.addEventListener('click', () => teaser.paused ? teaser.play().catch(updateHero) : teaser.pause());
teaser.addEventListener('play', updateHero); teaser.addEventListener('pause', updateHero); updateHero();
const visibility = new IntersectionObserver(entries => {
  for (const {target, isIntersecting} of entries) {
    if (!isIntersecting) target.pause();
    else if (!reduced.matches && !target.closest('.viewer')?.querySelector('iframe')) target.play().catch(() => {});
  }
}, {threshold: .15});
document.querySelectorAll('video[data-autoplay]').forEach(v => visibility.observe(v));

// Classic script loading also works on hosts that give pages an opaque origin.
const scriptLoads = new Map();
function loadScript(path) {
  if (!scriptLoads.has(path)) {
    scriptLoads.set(path, new Promise((resolve, reject) => {
      const script = document.createElement('script'); script.src = clearAssetURL(path);
      script.onload = resolve;
      script.onerror = () => { script.remove(); scriptLoads.delete(path); reject(new Error('Scene unavailable')); };
      document.head.append(script);
    }));
  }
  return scriptLoads.get(path);
}
function decodeHex(hex) {
  if (hex.length % 2 || /[^0-9a-f]/i.test(hex)) throw new Error('Invalid scene data');
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return bytes;
}
function recordingBase64(hex) {
  const bytes = decodeHex(hex); const chunks = [];
  for (let i = 0; i < bytes.length; i += 8192) chunks.push(String.fromCharCode(...bytes.subarray(i, i + 8192)));
  return btoa(chunks.join(''));
}
// The same player supports the fixed panels and the enlarged grid previews.
function wireViewer(viewer, onLaunch = () => {}) {
  const launch = viewer.querySelector('.launch');
  const video = viewer.querySelector('video, img.preview-image');
  let timer, generation = 0;
  function reset() {
    generation++; clearTimeout(timer);
    viewer.querySelectorAll('iframe,.viewer-tools,.viewer-status').forEach(e => e.remove());
    const ego=viewer.querySelector('.ego-inset video');if(ego?.readyState)ego.currentTime=0;
    video.hidden = false; launch.hidden = false; launch.disabled = false;
  }
  viewer.addEventListener('reset-viewer', reset);
  launch.addEventListener('click', async () => {
    reset(); onLaunch(); const attempt = generation;
    launch.disabled = true;
    const status = document.createElement('div'); status.className = 'viewer-status'; status.setAttribute('role','status');
    status.textContent = 'Loading interactive scene…'; viewer.append(status);
    try {
      const scene = viewer.dataset.scene;
      await Promise.all([loadScript('assets/viser/runtime-hex.js'), loadScript(`assets/recordings/${scene}.hex.js`)]);
      if (attempt !== generation) return;
      if(viewer.dataset.embodiment)await loadScript('assets/embodiment-bridge.js');
      if(viewer.dataset.ego||viewer.dataset.generation)await loadScript('assets/playback-bridge.js');
      if(viewer.dataset.orderStage)await loadScript('assets/order-bridge.js');
      if(attempt !== generation)return;
      const data = window.CLEAR_RECORDINGS?.[scene];
      if (!data || !window.CLEAR_VIEWER_HEX) throw new Error('Scene unavailable');
      const iframe = document.createElement('iframe');
      iframe.title = `${viewer.dataset.title || viewer.closest('article').querySelector('h3').textContent} interactive 3D playback`;
      const bridge=(viewer.dataset.embodiment ? `window.__CLEAR_EMBODIMENT__=${JSON.stringify({robot:viewer.dataset.embodiment,mode:viewer.dataset.displayMode||'structure'})};(${window.CLEAR_EMBODIMENT_BRIDGE.toString()})();` : '')+((viewer.dataset.ego||viewer.dataset.generation) ? `(${window.CLEAR_PLAYBACK_BRIDGE.toString()})();` : '')+(viewer.dataset.orderStage ? `window.__CLEAR_ORDER__=${JSON.stringify({stage:viewer.dataset.orderStage,sample:+viewer.dataset.orderSample||0})};(${window.CLEAR_ORDER_BRIDGE.toString()})();` : '');
      const embedded = `<script>${bridge}window.__VISER_EMBED_DATA__=${JSON.stringify(recordingBase64(data))};window.__VISER_EMBED_CONFIG__={darkMode:false};<\/script>`;
      const html = new TextDecoder().decode(decodeHex(window.CLEAR_VIEWER_HEX));
      iframe.srcdoc = html.replace('</head>', embedded + '</head>');
      iframe.allow = 'fullscreen';
      iframe.addEventListener('load', () => { clearTimeout(timer); status.remove(); if(viewer.dataset.embodiment)iframe.contentWindow.postMessage({type:'clear-embodiment-mode',mode:viewer.dataset.displayMode||'structure'},'*'); }, {once:true});
      timer = setTimeout(() => { status.textContent = 'Loading is taking longer than expected. Return to the video to retry.'; }, 20000);
      video.pause?.(); video.hidden = true; launch.hidden = true; viewer.append(iframe);
      const back = document.createElement('button'); back.type='button'; back.className='viewer-tools'; back.textContent=video.tagName==='VIDEO'?'Back to video':'Back to preview';
      back.addEventListener('click', () => { reset(); if(!reduced.matches) video.play?.().catch(()=>{}); launch.focus(); });
      viewer.append(back);
    } catch {
      if(attempt !== generation) return;
      status.textContent='Scene unavailable. Please retry.'; launch.disabled=false;
      timer=setTimeout(()=>status.remove(),2500);
    }
  });
  return reset;
}
document.querySelectorAll('.viewer:not(.focus-viewer)').forEach(v => wireViewer(v));
for (const grid of document.querySelectorAll('.media-grid')) {
  const overlay = grid.querySelector('.grid-focus');
  const viewer = overlay.querySelector('.viewer');
  const video = viewer.querySelector('video');
  let current = null, pinned = false, suppressHover = false;
  const reset = wireViewer(viewer, () => { pinned=true; });
  function open(tile, pin = false) {
    if (current === tile && !overlay.hidden) { pinned ||= pin; return; }
    reset(); current=tile; pinned=pin;
    viewer.dataset.scene=tile.dataset.scene; viewer.dataset.title=tile.dataset.title;
    overlay.querySelector('.focus-title').textContent=tile.dataset.title;
    viewer.querySelector('.launch').setAttribute('aria-label',`Play ${tile.dataset.title} in 3D`);
    const preview=tile.querySelector('video');
    video.poster=preview.poster;
    video.preload='auto';
    video.onloadedmetadata=()=>{if(current===tile&&Number.isFinite(preview.currentTime))video.currentTime=preview.currentTime;};
    video.src=tile.querySelector('source').src;
    overlay.hidden=false; grid.classList.add('has-focus');
    if(!reduced.matches || pin) video.play().catch(()=>{});
  }
  function close(restoreFocus=false) {
    reset(); video.pause(); overlay.hidden=true; grid.classList.remove('has-focus'); pinned=false;
    if(restoreFocus) { suppressHover=true; current?.focus(); }
    current=null;
  }
  grid.querySelectorAll('.media-tile').forEach(tile => {
    tile.addEventListener('pointerenter', () => { if(hoverAvailable.matches && !pinned && !suppressHover) open(tile); });
    tile.addEventListener('click', () => { open(tile,true); overlay.querySelector('.launch').focus(); });
  });
  grid.addEventListener('pointerleave', () => { suppressHover=false; if(!pinned) close(); });
  overlay.querySelector('.focus-close').addEventListener('click', () => close(true));
  grid.addEventListener('keydown', event => { if(event.key==='Escape') {event.preventDefault();close(true);} });
}
reduced.addEventListener('change', () => {
  if(reduced.matches) document.querySelectorAll('#teaser,video[data-autoplay]').forEach(v=>v.pause());
});

const gridFamily = document.querySelector('#grid-family');
gridFamily?.addEventListener('change', () => {
  document.querySelectorAll('[data-family]').forEach(panel => {
    panel.hidden = panel.dataset.family !== gridFamily.value;
    if (panel.hidden) panel.querySelectorAll('.viewer-tools').forEach(button => button.click());
  });
});

const mazeFamily = document.querySelector('#maze-family');
mazeFamily?.addEventListener('change', () => {
  document.querySelectorAll('[data-maze-family]').forEach(panel => {
    panel.hidden = panel.dataset.mazeFamily !== mazeFamily.value;
    if (panel.hidden) panel.querySelectorAll('.viewer-tools').forEach(button => button.click());
  });
});

const mpcView = document.querySelector('#mpc-view');
mpcView?.addEventListener('change', () => {
  document.querySelectorAll('.mpc-comparison .viewer').forEach(viewer => {
    viewer.dispatchEvent(new Event('reset-viewer'));
    const base = viewer.dataset.scene.replace(/-candidates$/, '');
    const scene = base + (mpcView.value === 'candidates' ? '-candidates' : '');
    viewer.dataset.scene = scene;
    viewer.querySelector('.preview-image').src = clearAssetURL(`assets/media/${scene}.png`);
  });
});

// Source-window validation also works when the host gives iframes opaque origins.
window.addEventListener('message',event=>{
  if(event.data?.type!=='clear-playback-time'||!Number.isFinite(event.data.time))return;
  for(const viewer of document.querySelectorAll('.viewer[data-ego]')){
    if(viewer.querySelector('iframe')?.contentWindow!==event.source)continue;
    const video=viewer.querySelector('.ego-inset video');
    const time=Math.max(0,Math.min(event.data.time,Number.isFinite(video.duration)?video.duration-.01:event.data.time));
    if(video.readyState&&Math.abs(video.currentTime-time)>.055)video.currentTime=time;
  }
});
