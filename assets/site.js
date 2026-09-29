function clearAssetURL(path) { const base=path.split('?')[0], version=window.CLEAR_ASSET_REVISIONS?.[base]; return version ? base+'?v='+version : path; }
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const hoverAvailable = matchMedia('(hover: hover) and (pointer: fine)');
const teaser = document.querySelector('#teaser');
const heroToggle = document.querySelector('#hero-toggle');
function updateHero() { heroToggle.textContent = teaser.paused ? 'Play teaser' : 'Pause teaser'; }
if (reduced.matches) teaser.pause();
heroToggle.addEventListener('click', () => teaser.paused ? teaser.play().catch(updateHero) : teaser.pause());
teaser.addEventListener('play', updateHero); teaser.addEventListener('pause', updateHero); updateHero();
// Warm only nearby previews, with two media preparations at a time.
// Sources are retained after preparation so scrolling back never resets playback.
const mediaQueue = new Set(), mediaStates = new Map();
let preparingMedia = 0;
function drainMedia() {
  if (document.hidden) return;
  for (const video of mediaQueue) {
    if (preparingMedia >= 2) break;
    mediaQueue.delete(video);
    const state = mediaStates.get(video);
    if (!state.near || state.loaded || state.loading || state.attempts >= 3 || reduced.matches) continue;
    state.loading = true; state.attempts = (state.attempts || 0) + 1; preparingMedia++;
    let timeout, finished = false;
    const done = event => {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      video.removeEventListener('loadeddata', done); video.removeEventListener('error', done, true);
      state.loading = false; state.loaded = video.readyState >= 2;
      preparingMedia--; drainMedia();
      if (state.visible && !document.hidden && !reduced.matches && state.loaded && !video.closest('.viewer')?.querySelector('iframe')) video.play().catch(() => {});
      if ((event?.type === 'error' || video.error) && state.attempts < 3) {
        clearTimeout(state.timer);
        state.timer = setTimeout(() => { if (state.near) { mediaQueue.add(video); drainMedia(); } }, state.attempts === 1 ? 1000 : 4000);
      }
    };
    video.addEventListener('loadeddata', done, {once:true}); video.addEventListener('error', done, {once:true,capture:true});
    timeout = setTimeout(done, 15000);
    if (video.readyState >= 2) done();
    else {
      const restart = video.preload === 'auto' || !!video.error || video.networkState === 3;
      video.preload = 'auto';
      // Changing preload starts the first request; load() is needed only for a retry.
      if (restart) video.load();
    }
  }
}
const nearbyMedia = new IntersectionObserver(entries => {
  for (const {target:video,isIntersecting} of entries) {
    const state = mediaStates.get(video); state.near = isIntersecting;
    clearTimeout(state.timer);
    if (!isIntersecting) { mediaQueue.delete(video); continue; }
    if (state.attempts >= 3 && !state.loaded) continue;
    // Do not start downloads for sections passed during a quick scroll.
    state.timer = setTimeout(() => { mediaQueue.add(video); drainMedia(); }, 350);
  }
}, {rootMargin:'240px 0px'});
const visibleMedia = new IntersectionObserver(entries => {
  for (const {target:video,isIntersecting} of entries) {
    const state = mediaStates.get(video); state.visible = isIntersecting;
    if (!isIntersecting) video.pause();
    else if (state.loaded && !document.hidden && !reduced.matches && !video.closest('.viewer')?.querySelector('iframe')) video.play().catch(() => {});
  }
}, {threshold:.05});
document.querySelectorAll('video[data-autoplay]').forEach(video => {
  mediaStates.set(video, {near:false,visible:false,loaded:false,loading:false});
  video.addEventListener('loadeddata', () => {
    const state = mediaStates.get(video); state.loaded = true;
    if (state.visible && !document.hidden && !reduced.matches && !video.closest('.viewer')?.querySelector('iframe')) video.play().catch(() => {});
  });
  nearbyMedia.observe(video); visibleMedia.observe(video);
});
// A native poster remains visible until decoding produces a frame.
document.querySelectorAll('video').forEach(video => {
  video.addEventListener('playing', () => video.classList.add('media-ready'));
});
const heroVisibility = new IntersectionObserver(entries => {
  if (!entries[0].isIntersecting) teaser.pause();
  else if (!document.hidden && !reduced.matches && !heroManuallyPaused) teaser.play().catch(updateHero);
});
let heroManuallyPaused = false;
heroToggle.addEventListener('click', () => { heroManuallyPaused = teaser.paused; });
heroVisibility.observe(teaser);
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { teaser.pause(); for (const video of mediaStates.keys()) video.pause(); }
  else {
    drainMedia();
    for (const [video,state] of mediaStates) if (state.visible && state.loaded && !reduced.matches && !video.closest('.viewer')?.querySelector('iframe')) video.play().catch(() => {});
    if (!heroManuallyPaused && !reduced.matches && teaser.getBoundingClientRect().bottom > 0) teaser.play().catch(updateHero);
  }
});

// User-started videos and enlarged previews pause outside the viewport, too.
const manualMedia = new Map();
function syncManualMedia(video, state) {
  if ((!state.visible || document.hidden) && !video.paused) { state.resume = true; video.pause(); }
  else if (state.visible && !document.hidden && state.resume) { state.resume = false; video.play().catch(() => {}); }
}
const manualVisibility = new IntersectionObserver(entries => {
  for (const entry of entries) {
    const state = manualMedia.get(entry.target); state.visible = entry.isIntersecting;
    syncManualMedia(entry.target, state);
  }
});
document.querySelectorAll('video[controls],.focus-viewer video').forEach(video => {
  manualMedia.set(video, {visible:false,resume:false}); manualVisibility.observe(video);
});
document.addEventListener('visibilitychange', () => { for (const [video,state] of manualMedia) syncManualMedia(video,state); });

// Automatic scenes must remain nearby and start one at a time.
const autoScenes = new Set();
let startingScene = false, sceneRetryAfter = 0;
function drainScenes() {
  if (startingScene || document.hidden || Date.now() < sceneRetryAfter) return;
  for (const viewer of autoScenes) {
    autoScenes.delete(viewer);
    if (!viewer._sceneNearby || viewer.querySelector('iframe,.viewer-status') || reduced.matches) continue;
    startingScene = true; viewer._automaticStarting = true;
    const done = event => {
      viewer.removeEventListener('scene-settled', done); startingScene = false; viewer._automaticStarting = false;
      if (event.detail?.failed) { sceneRetryAfter = Date.now() + 60000; setTimeout(drainScenes, 60000); }
      drainScenes();
    };
    viewer.addEventListener('scene-settled', done);
    viewer.querySelector('.launch').click();
    return;
  }
}
function observeAutomaticScene(viewer) {
  let timer, attempted = false;
  const observer = new IntersectionObserver(entries => {
    viewer._sceneNearby = entries[0].isIntersecting;
    clearTimeout(timer);
    if (!viewer._sceneNearby) {
      autoScenes.delete(viewer);
      if (viewer._automaticStarting && !viewer.querySelector('iframe')) {
        attempted = false; viewer.dispatchEvent(new Event('reset-viewer'));
      }
      return;
    }
    if (!attempted && !reduced.matches) timer = setTimeout(() => {
      if (viewer.querySelector('iframe,.viewer-status')) return;
      autoScenes.add(viewer); drainScenes();
    }, 550);
  }, {rootMargin:'120px 0px'});
  viewer.querySelector('.launch').addEventListener('click', () => { attempted = true; });
  observer.observe(viewer);
}
document.addEventListener('visibilitychange', drainScenes);

// Runs inside each native player, including opaque-origin anonymous embeds.
function sceneLifecycle() {
  let ready = false, visible = true, resume = false;
  window.addEventListener('webglcontextlost', () => parent.postMessage({type:'clear-scene-error'}, '*'), true);
  const apply = () => {
    const button = document.querySelector('button');
    if (!button) return;
    const playing = !!button.querySelector('.tabler-icon-player-pause-filled');
    if (!visible && playing) { resume = true; button.click(); }
    else if (visible && resume) { resume = false; if (!playing) button.click(); }
  };
  window.addEventListener('message', event => {
    if (event.source !== parent || event.data?.type !== 'clear-scene-visible') return;
    visible = event.data.visible; apply();
  });
  const timer = setInterval(() => {
    apply();
    if (ready || !document.querySelector('canvas') || !document.querySelector('input')) return;
    ready = true;
    requestAnimationFrame(() => requestAnimationFrame(() => parent.postMessage({type:'clear-scene-ready'}, '*')));
  }, 100);
  window.addEventListener('pagehide', () => clearInterval(timer), {once:true});
}

// Classic script loading also works on hosts that give pages an opaque origin.
const scriptLoads = new Map();
const scriptQueue = [];
let activeScripts = 0;
function drainScripts() {
  while (activeScripts < 2 && scriptQueue.length) {
    activeScripts++;
    const job = scriptQueue.shift();
    job.run().then(job.resolve, job.reject).finally(() => { activeScripts--; drainScripts(); });
  }
}
function requestScript(path, ready) {
  return new Promise((resolve, reject) => {
    scriptQueue.push({resolve, reject, run: () => new Promise((resolve, reject) => {
      // Another viewer may already have loaded this shared dependency.
      if (ready()) { resolve(); return; }
      const script = document.createElement('script');
      let settled = false;
      const finish = error => {
        if (settled) return;
        settled = true; clearTimeout(timeout);
        script.onload = script.onerror = null; script.remove();
        error ? reject(error) : resolve();
      };
      const timeout = setTimeout(() => finish(new Error('Scene request timed out')), 45000);
      script.onload = () => finish(ready() ? null : new Error('Incomplete scene response'));
      script.onerror = () => finish(new Error('Scene request failed'));
      script.src = clearAssetURL(path);
      document.head.append(script);
    })});
    drainScripts();
  });
}
function loadScript(path, ready) {
  if (ready()) return Promise.resolve();
  if (!scriptLoads.has(path)) {
    const pending = (async () => {
      // Bound retries so a rate-limited host is not flooded with requests.
      for (let attempt = 0; attempt < 3; attempt++) {
        if (attempt) await new Promise(resolve => setTimeout(resolve, attempt === 1 ? 1000 : 4000));
        try { await requestScript(path, ready); return; }
        catch (error) { if (attempt === 2) throw error; }
      }
    })();
    scriptLoads.set(path, pending);
    const forget = () => { if (scriptLoads.get(path) === pending) scriptLoads.delete(path); };
    pending.then(forget, forget);
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
  const launchLabel = launch.textContent;
  let timer, revealTimer, generation = 0, inView = false, localRecoveries = 0;
  const settled = (failed = false) => viewer.dispatchEvent(new CustomEvent('scene-settled', {detail:{failed}}));
  const syncVisibility = () => viewer.querySelector('iframe')?.contentWindow.postMessage({type:'clear-scene-visible',visible:inView && !document.hidden}, '*');
  new IntersectionObserver(entries => { inView = entries[0].isIntersecting; syncVisibility(); }, {threshold:.01}).observe(viewer);
  document.addEventListener('visibilitychange', syncVisibility);
  function reset() {
    generation++; clearTimeout(timer); clearTimeout(revealTimer);
    settled(); viewer.removeAttribute('aria-busy');
    viewer.querySelectorAll('iframe,.viewer-tools,.viewer-status').forEach(e => e.remove());
    const ego=viewer.querySelector('.ego-inset video');if(ego?.readyState)ego.currentTime=0;
    video.hidden = false; launch.hidden = false; launch.disabled = false; launch.textContent = launchLabel;
  }
  viewer.addEventListener('reset-viewer', reset);
  launch.addEventListener('click', async () => {
    // Reset without settling the new queue slot before it has started.
    generation++; clearTimeout(timer); clearTimeout(revealTimer);
    viewer.querySelectorAll('iframe,.viewer-tools,.viewer-status').forEach(e => e.remove());
    video.hidden = false; launch.hidden = false;
    onLaunch(); const attempt = generation;
    launch.disabled = true; viewer.setAttribute('aria-busy', 'true');
    const status = document.createElement('div'); status.className = 'viewer-status'; status.setAttribute('role','status');
    status.textContent = 'Loading interactive scene…'; viewer.append(status);
    timer = setTimeout(() => { status.textContent = 'Still loading… The preview remains available.'; }, 8000);
    try {
      const scene = viewer.dataset.scene;
      await loadScript('assets/viser/runtime-hex.js', () => !!window.CLEAR_VIEWER_HEX);
      if (attempt !== generation) return;
      await loadScript(`assets/recordings/${scene}.hex.js`, () => !!window.CLEAR_RECORDINGS?.[scene]);
      if (attempt !== generation) return;
      if(viewer.dataset.embodiment)await loadScript('assets/embodiment-bridge.js', () => typeof window.CLEAR_EMBODIMENT_BRIDGE === 'function');
      if(viewer.dataset.ego||viewer.dataset.generation)await loadScript('assets/playback-bridge.js', () => typeof window.CLEAR_PLAYBACK_BRIDGE === 'function');
      if(viewer.dataset.orderStage)await loadScript('assets/order-bridge.js', () => typeof window.CLEAR_ORDER_BRIDGE === 'function');
      if(attempt !== generation)return;
      const data = window.CLEAR_RECORDINGS?.[scene];
      if (!data || !window.CLEAR_VIEWER_HEX) throw new Error('Scene unavailable');
      const iframe = document.createElement('iframe');
      iframe.title = `${viewer.dataset.title || viewer.closest('article').querySelector('h3').textContent} interactive 3D playback`;
      const bridge=(viewer.dataset.embodiment ? `window.__CLEAR_EMBODIMENT__=${JSON.stringify({robot:viewer.dataset.embodiment,mode:viewer.dataset.displayMode||'structure'})};(${window.CLEAR_EMBODIMENT_BRIDGE.toString()})();` : '')+((viewer.dataset.ego||viewer.dataset.generation) ? `(${window.CLEAR_PLAYBACK_BRIDGE.toString()})();` : '')+(viewer.dataset.orderStage ? `window.__CLEAR_ORDER__=${JSON.stringify({stage:viewer.dataset.orderStage,sample:+viewer.dataset.orderSample||0})};(${window.CLEAR_ORDER_BRIDGE.toString()})();` : '');
      const embedded = `<script>(${sceneLifecycle.toString()})();${bridge}window.__VISER_EMBED_DATA__=${JSON.stringify(recordingBase64(data))};window.__VISER_EMBED_CONFIG__={darkMode:false};<\/script>`;
      const html = new TextDecoder().decode(decodeHex(window.CLEAR_VIEWER_HEX));
      iframe.srcdoc = html.replace('</head>', embedded + '</head>');
      iframe.allow = 'fullscreen';
      iframe.addEventListener('load', () => { syncVisibility(); if(viewer.dataset.embodiment)iframe.contentWindow.postMessage({type:'clear-embodiment-mode',mode:viewer.dataset.displayMode||'structure'},'*'); }, {once:true});
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (attempt !== generation) return;
        iframe.remove(); viewer.querySelector('.viewer-tools')?.remove();
        status.textContent = '3D is taking longer than expected. The preview is still available.';
        viewer.removeAttribute('aria-busy');
        launch.hidden = false; launch.disabled = false; launch.textContent = 'Retry 3D'; settled(true);
      }, 45000);
      iframe.className = 'scene-pending'; iframe.tabIndex = -1;
      launch.hidden = true; viewer.append(iframe);
      const ego = viewer.querySelector('.ego-inset video');
      if (ego && ego.readyState === 0) { ego.preload = 'auto'; ego.load(); }
      const back = document.createElement('button'); back.type='button'; back.className='viewer-tools'; back.textContent=video.tagName==='VIDEO'?'Back to video':'Back to preview';
      back.addEventListener('click', () => { reset(); if(!reduced.matches) video.play?.().catch(()=>{}); launch.focus(); });
      viewer.append(back);
    } catch {
      if(attempt !== generation) return;
      clearTimeout(timer);
      viewer.removeAttribute('aria-busy');
      status.textContent='3D could not load. The preview is still available. Please wait a moment, then retry.';
      launch.disabled=false; launch.textContent='Retry 3D'; settled(true);
    }
  });
  window.addEventListener('message', event => {
    const iframe = viewer.querySelector('iframe');
    if (!iframe || event.source !== iframe.contentWindow) return;
    if (event.data?.type === 'clear-scene-error') {
      reset();
      if (inView && !document.hidden && localRecoveries++ < 1) launch.click();
      else { launch.textContent = 'Retry 3D'; }
      return;
    }
    if (event.data?.type !== 'clear-scene-ready') return;
    viewer.removeAttribute('aria-busy'); iframe.removeAttribute('tabindex');
    clearTimeout(timer); viewer.querySelector('.viewer-status')?.remove();
    iframe.classList.remove('scene-pending'); iframe.classList.add('scene-ready');
    syncVisibility(); settled();
    revealTimer = setTimeout(() => { video.pause?.(); video.hidden = true; }, reduced.matches ? 0 : 350);
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
    const syncPreview=()=>{if(current===tile&&Number.isFinite(preview.currentTime))video.currentTime=preview.currentTime;};
    video.onloadedmetadata=syncPreview;
    const source=tile.querySelector('source').src;
    if(video.src!==source)video.src=source;
    else if(video.readyState>=1)syncPreview();
    overlay.hidden=false; grid.classList.add('has-focus');
    if(!reduced.matches || pin) video.play().catch(()=>{});
  }
  function close(restoreFocus=false) {
    reset(); video.pause(); if(manualMedia.has(video))manualMedia.get(video).resume=false; overlay.hidden=true; grid.classList.remove('has-focus'); pinned=false;
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

// Detail views accompany the video preview as well as native 3D playback.
for(const viewer of document.querySelectorAll('.mpc-comparison .viewer[data-ego]')){
 const main=viewer.querySelector('.preview-video'),detail=viewer.querySelector('.ego-inset video');
 if(!main||!detail)continue;
 const synchronize=()=>{if(viewer.querySelector('iframe.scene-ready'))return;if(detail.readyState&&Math.abs(detail.currentTime-main.currentTime)>.08)detail.currentTime=Math.min(main.currentTime,detail.duration-.01);};
 main.addEventListener('play',()=>{if(detail.preload==='none'){detail.preload='auto';detail.load();}synchronize();detail.play().catch(()=>{});});
 for(const name of ['timeupdate','seeking','seeked'])main.addEventListener(name,synchronize);
 main.addEventListener('pause',()=>detail.pause());main.addEventListener('ended',()=>detail.pause());
 detail.addEventListener('loadeddata',()=>{synchronize();if(!main.paused&&!viewer.querySelector('iframe.scene-ready'))detail.play().catch(()=>{});});
}

// Inspect measured contact events in either the movie or the native replay.
for(const button of document.querySelectorAll('[data-mpc-seek]')){
 button.addEventListener('click',()=>{
  const viewer=button.closest('article').querySelector('.viewer'),time=Number(button.dataset.mpcSeek),frame=viewer.querySelector('iframe.scene-ready');
  if(frame){frame.contentWindow.postMessage({type:'clear-playback-command',time,playing:true},'*');return;}
  const video=viewer.querySelector('.preview-video');
  const seek=()=>{video.currentTime=time;video.play().catch(()=>{});};
  if(video.readyState)seek();else{video.addEventListener('loadedmetadata',seek,{once:true});video.load();}
 });
}
