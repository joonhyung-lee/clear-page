/* Start nearby evidence automatically, retain true failures and preserve clocks. */
(() => {
 document.querySelectorAll('.viewer[data-autostart]').forEach(observeAutomaticScene);
 document.querySelectorAll('.media-tile[data-scene^="mpc-"]').forEach(tile=>attachEgoVideo(tile,tile.dataset.scene));
 document.querySelectorAll('.execution-body-viewer').forEach(viewer=>{
  const main=viewer.querySelector('.preview-video'),ego=viewer.querySelector('.ego-inset video');
  const sync=()=>{if(viewer.querySelector('iframe.scene-ready'))return;if(ego.readyState&&Math.abs(ego.currentTime-main.currentTime)>.08)ego.currentTime=Math.min(main.currentTime,ego.duration-.01);};
  main.addEventListener('play',()=>{ego.preload='auto';sync();ego.play().catch(()=>{});});
  for(const event of ['timeupdate','seeking','seeked'])main.addEventListener(event,sync);
  main.addEventListener('pause',()=>ego.pause());ego.addEventListener('loadeddata',()=>{sync();if(!main.paused)ego.play().catch(()=>{});});
 });
 document.querySelector('[data-paper-figure]')?.addEventListener('click',()=>{
  const dialog=document.querySelector('#resource-dialog');dialog.querySelector('h2').textContent='Architecture in the paper';
  const image=document.createElement('img');image.src=clearAssetURL('assets/pipeline-anonymous.png');image.alt='Original CLEAR paper architecture';image.style.cssText='width:100%;height:100%;object-fit:contain';
  dialog.querySelector('[data-resource-content]').replaceChildren(image);const download=dialog.querySelector('[data-resource-download]');download.href=image.src;download.textContent='Download figure';dialog.showModal();
 });
 const failure=document.querySelector('[data-failure-example="execution"] video');
 failure?.addEventListener('loadedmetadata',()=>{failure.currentTime=12.5;},{once:true});
 failure?.addEventListener('timeupdate',()=>{
  failure.closest('article').querySelector('output').textContent=failure.currentTime<14.14?'Pushing · Contact lost at 14.14 s':failure.currentTime<15?'Contact lost · Goal not reached':'Box stopped · Goal still 1.33 m away';
 });
})();

// One replay clock drives the measured body and palm views, including seeks.
(() => {
 const views=[...document.querySelectorAll('[data-execution-clock]')];let clock={time:0,playing:false,speed:2};
 function synchronize(){for(const view of views){
  const video=view.querySelector('.preview-video'),ego=view.querySelector('.ego-inset video');
  const limit=Number.isFinite(video.duration)?Math.max(0,video.duration-.04):Infinity;
  const target=Math.min(clock.time,limit),finished=clock.time>=limit;
  for(const media of [video,ego]){
   if(media.preload!=='auto')media.preload='auto';
   media.playbackRate=clock.speed;
   if(media.readyState&&!media.seeking&&Math.abs(media.currentTime-Math.min(target,media.duration-.04))>.14)media.currentTime=Math.max(0,Math.min(target,media.duration-.04));
   if(clock.playing&&!finished&&!view.querySelector('iframe.scene-ready')){if(media.paused)media.play().catch(()=>{});}else media.pause();
  }
  const native=view.querySelector('iframe.scene-ready');
  if(native&&(!view._clockSent||Math.abs(target-view._clockSent)>.08)){native.contentWindow.postMessage({type:'clear-playback-command',time:target,playing:false},'*');view._clockSent=target;}
  view.querySelector('.execution-clock-note').textContent=finished&&view.dataset.executionClock==='optimized'?'First interaction complete · Final video frame':target.toFixed(1)+' s · Recorded motion';
 }}
 document.addEventListener('clear-mpc-clock',event=>{clock=event.detail;synchronize();});
 for(const view of views){view.querySelector('.preview-video').addEventListener('loadedmetadata',synchronize);view.addEventListener('scene-settled',synchronize);}
})();
