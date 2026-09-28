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
      const script = document.createElement('script'); script.src = path;
      script.onload = resolve;
      script.onerror = () => { script.remove(); scriptLoads.delete(path); reject(new Error('Scene unavailable')); };
      document.head.append(script);
    }));
  }
  return scriptLoads.get(path);
}
// The same player supports the fixed panels and the enlarged grid previews.
function wireViewer(viewer, onLaunch = () => {}) {
  const launch = viewer.querySelector('.launch');
  const video = viewer.querySelector('video');
  let timer, generation = 0;
  function reset() {
    generation++; clearTimeout(timer);
    viewer.querySelectorAll('iframe,.viewer-tools,.viewer-status').forEach(e => e.remove());
    video.hidden = false; launch.hidden = false; launch.disabled = false;
  }
  launch.addEventListener('click', async () => {
    reset(); onLaunch(); const attempt = generation;
    launch.disabled = true;
    const status = document.createElement('div'); status.className = 'viewer-status'; status.setAttribute('role','status');
    status.textContent = 'Loading interactive scene…'; viewer.append(status);
    try {
      const scene = viewer.dataset.scene;
      await Promise.all([loadScript('assets/viser/runtime.js'), loadScript(`assets/recordings/${scene}.js`)]);
      if (attempt !== generation) return;
      const data = window.CLEAR_RECORDINGS?.[scene];
      if (!data || !window.CLEAR_VIEWER_HTML) throw new Error('Scene unavailable');
      const iframe = document.createElement('iframe');
      iframe.title = `${viewer.dataset.title || viewer.closest('article').querySelector('h3').textContent} interactive 3D playback`;
      const embedded = `<script>window.__VISER_EMBED_DATA__=${JSON.stringify(data)};window.__VISER_EMBED_CONFIG__={darkMode:false};<\/script>`;
      iframe.srcdoc = window.CLEAR_VIEWER_HTML.replace('</head>', embedded + '</head>');
      iframe.allow = 'fullscreen';
      iframe.addEventListener('load', () => { clearTimeout(timer); status.remove(); }, {once:true});
      timer = setTimeout(() => { status.textContent = 'Loading is taking longer than expected. Return to the video to retry.'; }, 20000);
      video.pause(); video.hidden = true; launch.hidden = true; viewer.append(iframe);
      const back = document.createElement('button'); back.type='button'; back.className='viewer-tools'; back.textContent='Back to video';
      back.addEventListener('click', () => { reset(); if(!reduced.matches) video.play().catch(()=>{}); launch.focus(); });
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
    video.poster=tile.querySelector('video').poster;
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
