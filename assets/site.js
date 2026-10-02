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
  if (!entries.at(-1).isIntersecting) teaser.pause();
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
    if (!heroManuallyPaused && !reduced.matches && teaser.getBoundingClientRect().bottom > 0 && teaser.getBoundingClientRect().top < innerHeight) teaser.play().catch(updateHero);
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
  if(viewer._automaticObserved)return;viewer._automaticObserved=true;
  let timer, attempted = false;
  viewer.addEventListener('scene-evicted',()=>{attempted=false;});
  const observer = new IntersectionObserver(entries => {
    viewer._sceneNearby = entries.at(-1).isIntersecting;
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
  }, {rootMargin:'0px'});
  viewer.querySelector('.launch').addEventListener('click', () => { attempted = true; });
  observer.observe(viewer);
}
document.addEventListener('visibilitychange', drainScenes);

// Runs inside each native player, including opaque-origin anonymous embeds.
function sceneLifecycle() {
  let ready = false, visible = false, resume = false, initialized = false, initialMotionApplied = false;
  // The native player applies time-zero messages on its first tick. Pausing
  // before those messages arrive leaves an empty canvas at time zero.
  function hasScene() {
    const root = document.querySelector('#root');
    const key = root && Object.keys(root).find(k => k.startsWith('__reactContainer'));
    if (!key) return false;
    const queue = [root[key], root[key]?.stateNode?.current], seen = new Set();
    while (queue.length) {
      const f = queue.pop(); if (!f || seen.has(f)) continue; seen.add(f);
      const viewer = f.memoizedProps?.value;
      if (viewer?.useSceneTree?.getAll) {
        const nodes = Object.values(viewer.useSceneTree.getAll());
        const geometry = nodes.filter(n => n.message?.name && !['FrameMessage','LabelMessage','Gui3DMessage','TransformControlsMessage'].includes(n.message.type));
        if (!geometry.length) { queue.push(f.child, f.sibling, f.alternate); continue; }
        // Scene messages can precede React's actual geometry by several frames.
        // Keep the preview until the native meshes, rather than just empty
        // coordinate frames or labels, have mounted in the renderer.
        const mounted = node => {
          let drawable = false;
          viewer.mutable?.current?.nodeRefFromName?.[node.message.name]?.traverse?.(object => {
            if (object.geometry?.attributes?.position?.count > 0 && object.visible !== false) drawable = true;
          });
          return drawable;
        };
        if (window.__CLEAR_CHECKPOINT_REPLAY__) {
          const shown = geometry.filter(n => n.effectiveVisibility !== false);
          const robots = shown.filter(n => n.message.name.startsWith('/agents/'));
          const terrain = shown.filter(n => n.message.name.startsWith('/terrain/'));
          // Reveal real scene content progressively. Waiting for every mesh
          // keeps a usable renderer hidden when a part is deferred or invisible.
          if (robots.some(mounted) && terrain.some(mounted)) return true;
        } else if (geometry.some(mounted)) return true;
      }
      queue.push(f.child, f.sibling, f.alternate);
    }
    return false;
  }
  window.addEventListener('webglcontextlost', () => parent.postMessage({type:'clear-scene-error'}, '*'), true);
  const apply = () => {
    if (!initialized) return;
    const button = document.querySelector('[class*="tabler-icon-player-play"],[class*="tabler-icon-player-pause"]')?.closest('button');
    if (!button) return;
    const playing = !!button.querySelector('.tabler-icon-player-pause-filled');
    if (!initialMotionApplied) {
      initialMotionApplied = true;
      // Let time-zero geometry mount first, then honor reduced motion once.
      // Later explicit Play commands and viewport resume remain available.
      if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
        resume = false; if (playing) button.click(); return;
      }
    }
    if (!visible && playing) { resume = true; button.click(); }
    else if (visible && resume) { resume = false; if (!playing) button.click(); }
  };
  window.addEventListener('message', event => {
    if (event.source !== parent || event.data?.type !== 'clear-scene-visible') return;
    visible = event.data.visible; apply();
  });
  const timer = setInterval(() => {
    initialized ||= hasScene();
    if (!initialized) return;
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
// Bound offscreen automatic WebGL contexts while keeping visible scenes alive.
function releaseOffscreenScenes(current){
 const live=[...document.querySelectorAll('.viewer')].filter(v=>v.querySelector('iframe'));
 let count=live.length;
 for(const view of live){
  if(count<6)break;
  const rect=view.getBoundingClientRect();
  if(view===current||!view._automaticObserved||(rect.bottom>0&&rect.top<innerHeight&&rect.width>0))continue;
  view._savedReplayTime=view._lastReplayTime||0;
  view.dispatchEvent(new Event('reset-viewer'));view.dispatchEvent(new Event('scene-evicted'));count--;
 }
}
// The same player supports the fixed panels and the enlarged grid previews.
function wireViewer(viewer, onLaunch = () => {}) {
  const launch = viewer.querySelector('.launch');
  const video = viewer.querySelector('video, img.preview-image');
  const launchLabel = launch.textContent;
  let timer, revealTimer, generation = 0, inView = false, localRecoveries = 0;
  const settled = (failed = false) => viewer.dispatchEvent(new CustomEvent('scene-settled', {detail:{failed}}));
  const syncVisibility = () => viewer.querySelector('iframe')?.contentWindow.postMessage({type:'clear-scene-visible',visible:inView && !document.hidden}, '*');
  new IntersectionObserver(entries => { inView = entries.at(-1).isIntersecting; syncVisibility(); }, {threshold:.01}).observe(viewer);
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
    releaseOffscreenScenes(viewer);
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
      if(viewer.dataset.ego||viewer.dataset.generation||viewer.dataset.autostart!==undefined)await loadScript('assets/playback-bridge.js', () => typeof window.CLEAR_PLAYBACK_BRIDGE === 'function');
      if(viewer.dataset.orderStage)await loadScript('assets/order-bridge.js', () => typeof window.CLEAR_ORDER_BRIDGE === 'function');
      if(attempt !== generation)return;
      const data = window.CLEAR_RECORDINGS?.[scene];
      if (!data || !window.CLEAR_VIEWER_HEX) throw new Error('Scene unavailable');
      const iframe = document.createElement('iframe');
      iframe.title = `${viewer.dataset.title || viewer.closest('article').querySelector('h3').textContent} interactive 3D playback`;
      const bridge=(viewer.dataset.embodiment ? `window.__CLEAR_EMBODIMENT__=${JSON.stringify({robot:viewer.dataset.embodiment,mode:viewer.dataset.displayMode||'structure'})};(${window.CLEAR_EMBODIMENT_BRIDGE.toString()})();` : '')+((viewer.dataset.ego||viewer.dataset.generation||viewer.dataset.autostart!==undefined) ? `(${window.CLEAR_PLAYBACK_BRIDGE.toString()})();` : '')+(viewer.dataset.orderStage ? `window.__CLEAR_ORDER__=${JSON.stringify({stage:viewer.dataset.orderStage,sample:+viewer.dataset.orderSample||0})};(${window.CLEAR_ORDER_BRIDGE.toString()})();` : '');
      const embedded = `<script>window.__CLEAR_BODY_CHASE__=${viewer.dataset.scene==='mpc-g1-native'};window.__CLEAR_CONTACT_SIDE__=${viewer.dataset.contactSide==='true'};window.__CLEAR_CHECKPOINT_REPLAY__=${!!viewer.dataset.locoViewer};window.__CLEAR_EXTERNAL_TIMELINE__=${viewer.dataset.externalTimeline==='true'};(${sceneLifecycle.toString()})();${bridge}window.__VISER_EMBED_DATA__=${JSON.stringify(recordingBase64(data))};window.__VISER_EMBED_CONFIG__={darkMode:false};<\/script>`;
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
    if(event.data?.type==='clear-playback-time')viewer._lastReplayTime=event.data.time;
    if (event.data?.type !== 'clear-scene-ready') return;
    viewer.removeAttribute('aria-busy'); iframe.removeAttribute('tabindex');
    clearTimeout(timer); viewer.querySelector('.viewer-status')?.remove();
    iframe.classList.remove('scene-pending'); iframe.classList.add('scene-ready');
    syncVisibility();
    if(viewer.dataset.contactSide==='true')iframe.contentWindow.postMessage({type:'clear-contact-camera'},'*');
    if(viewer._savedReplayTime>0){iframe.contentWindow.postMessage({type:'clear-playback-command',time:viewer._savedReplayTime,playing:inView&&!reduced.matches},'*');delete viewer._savedReplayTime;}
    settled();
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
  let closeTimer;
  function pinOverlay(value) { pinned=value; overlay.dataset.pinned=String(value); }
  const reset = wireViewer(viewer, () => { pinOverlay(true); });
  function open(tile, pin = false) {
    clearTimeout(closeTimer);
    if (current === tile && !overlay.hidden) { pinOverlay(pinned || pin); return; }
    reset(); current=tile; pinOverlay(pin);
    viewer.dataset.scene=tile.dataset.scene; viewer.dataset.title=tile.dataset.title;viewer.dataset.contactSide=tile.dataset.contactSide||'';
    if(tile.dataset.scene.startsWith('mpc-'))attachEgoVideo(viewer,tile.dataset.scene);
    overlay.querySelector('.focus-title').textContent=tile.dataset.title;
    const outcome=overlay.querySelector('.focus-outcome');
    if(outcome)outcome.textContent=[tile.dataset.outcome,tile.dataset.note].filter(Boolean).join(' · ');
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
    clearTimeout(closeTimer);
    reset(); video.pause(); if(manualMedia.has(video))manualMedia.get(video).resume=false; overlay.hidden=true; grid.classList.remove('has-focus'); pinOverlay(false);
    if(restoreFocus) { suppressHover=true; current?.focus(); }
    current=null;
  }
  grid.querySelectorAll('.media-tile').forEach(tile => {
    tile.addEventListener('pointerenter', () => { if(hoverAvailable.matches && !pinned && !suppressHover) open(tile); });
    tile.addEventListener('click', () => { open(tile,true); overlay.querySelector('.launch').focus(); });
  });
  const keepOpen=()=>clearTimeout(closeTimer);
  const leave=event=>{
    if(grid.contains(event.relatedTarget)||overlay.contains(event.relatedTarget))return;
    suppressHover=false;
    clearTimeout(closeTimer);
    closeTimer=setTimeout(()=>{if(!pinned&&!grid.matches(':hover')&&!overlay.matches(':hover'))close();},160);
  };
  grid.addEventListener('pointermove',event=>{if(suppressHover&&(event.movementX||event.movementY)){suppressHover=false;const tile=event.target.closest('.media-tile');if(tile&&hoverAvailable.matches&&!pinned)open(tile);}});
  grid.addEventListener('pointerenter',keepOpen);
  overlay.addEventListener('pointerenter',keepOpen);
  grid.addEventListener('pointerleave',leave);
  overlay.addEventListener('pointerleave',leave);
  overlay.addEventListener('click',event=>{
    if(!event.target.closest('button')&&!pinned){pinOverlay(true);video.play().catch(()=>{});}
  });
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
    if(panel.hidden)panel.querySelectorAll('.viewer').forEach(viewer=>{viewer._savedReplayTime=viewer._lastReplayTime||0;viewer.dispatchEvent(new Event('reset-viewer'));viewer.dispatchEvent(new Event('scene-evicted'));});
  });
});

const mazeFamily = document.querySelector('#maze-family');
mazeFamily?.addEventListener('change', () => {
  document.querySelectorAll('[data-maze-family]').forEach(panel => {
    panel.hidden = panel.dataset.mazeFamily !== mazeFamily.value;
    if(panel.hidden)panel.querySelectorAll('.viewer').forEach(viewer=>{viewer._savedReplayTime=viewer._lastReplayTime||0;viewer.dispatchEvent(new Event('reset-viewer'));viewer.dispatchEvent(new Event('scene-evicted'));});
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
    if(viewer.dataset.executionClock&&viewer._egoClockMode==='external')continue;
    syncEgoClock(viewer,event.data,'native');
  }
});

// Detail views accompany the video preview as well as native 3D playback.
for(const viewer of document.querySelectorAll('.mpc-comparison .viewer[data-ego]')){
 const main=viewer.querySelector('.preview-video'),ego=viewer.querySelector('.ego-inset video');
 if(main&&ego)wireEgoVideo(viewer,main,ego);
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

// CSS traces follow document visibility as well as their viewport observer.
document.addEventListener('visibilitychange',()=>document.documentElement.toggleAttribute('data-page-hidden',document.hidden));

// One RGB inset follows the same physical recording as its outer view.
// Let the decoder play continuously. Seek only for explicit jumps or large drift.
function syncEgoClock(viewer,clock,mode='video'){
 const ego=viewer.querySelector('.ego-inset video');if(!ego||!Number.isFinite(clock.time))return;
 const now=performance.now()/1000,previous=viewer._egoClock;
 let rate=Number.isFinite(clock.rate)?clock.rate:1;
 const same=previous&&viewer._egoClockMode===mode;
 if(mode==='native'&&same&&clock.playing&&previous.playing){
  const elapsed=now-previous.wall,advance=clock.time-previous.time;
  if(elapsed>.025&&advance>=0&&advance/elapsed<8)rate=Math.max(.1,advance/elapsed);
  else rate=previous.rate;
 }
 const expected=same?previous.time+(previous.playing?(now-previous.wall)*previous.rate:0):clock.time;
 const jump=!!clock.seek||(same&&Math.abs(clock.time-expected)>.5);
 viewer._egoClockMode=mode;viewer._egoClock={...clock,rate,wall:now};
 if(ego.preload!=='auto')ego.preload='auto';
 if(!ego.readyState)return;
 const end=Number.isFinite(ego.duration)?Math.max(0,ego.duration-.001):Infinity;
 const target=Math.max(0,Math.min(clock.time,end)),error=target-ego.currentTime;
 const playing=!!clock.playing&&target<end;
 if(!ego.seeking&&(jump||Math.abs(error)>.5||(!playing&&Math.abs(error)>.025)))ego.currentTime=target;
 const correction=playing&&!jump&&Math.abs(error)<.5?Math.max(-.08,Math.min(.08,error*.3)):0;
 ego.playbackRate=Math.max(.1,Math.min(8,rate+correction));
 if(playing){ego.preload='auto';if(ego.paused)ego.play().catch(()=>{});}else ego.pause();
}
function wireEgoVideo(viewer,main,ego){
 if(main._egoWired)return;main._egoWired=true;
 let waiting=false;
 const sync=(seek=false)=>{
  if(viewer.dataset.executionClock||viewer.querySelector('iframe.scene-ready'))return;
  syncEgoClock(viewer,{time:main.currentTime,playing:!main.paused&&!waiting,rate:main.playbackRate,seek},'video');
 };
 main.addEventListener('play',()=>{waiting=false;ego.preload='auto';sync();});
 main.addEventListener('playing',()=>{waiting=false;sync();});
 for(const event of ['timeupdate','ratechange'])main.addEventListener(event,()=>sync());
 for(const event of ['seeking','seeked'])main.addEventListener(event,()=>sync(true));
 for(const event of ['pause','ended'])main.addEventListener(event,()=>sync());
 main.addEventListener('waiting',()=>{waiting=true;sync();});
 ego.addEventListener('loadeddata',()=>{
  if((viewer.dataset.executionClock||viewer.querySelector('iframe.scene-ready'))&&viewer._egoClock)syncEgoClock(viewer,viewer._egoClock,viewer._egoClockMode);
  else sync(true);
 });
 if(!main.paused)sync();
}
function attachEgoVideo(viewer,scene){
 const key='assets/media/'+scene+'-ego.mp4';if(!window.CLEAR_ASSET_REVISIONS?.[key])return;
 viewer.dataset.ego='true';let inset=viewer.querySelector('.ego-inset');
 if(!inset){inset=document.createElement('div');inset.className='ego-inset';inset.innerHTML='<span>Ego RGB</span><video muted playsinline preload="none"></video>';viewer.append(inset);}
 inset.title='Rendered robot camera, synchronized with the recorded motion';
 const main=viewer.querySelector('video'),ego=inset.querySelector('video');ego.muted=true;ego.playsInline=true;
 if(viewer._egoScene!==scene){
  viewer._egoScene=scene;viewer._egoClock=null;
  ego.src=clearAssetURL(key);ego.poster=clearAssetURL(key.replace('.mp4','.png'));
 }
 wireEgoVideo(viewer,main,ego);
}
