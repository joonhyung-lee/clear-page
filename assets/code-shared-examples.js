/* Reuse the paper's media; hidden input groups release playback. */
(() => {
 const root=document.querySelector('[data-shared-grounding]');if(!root)return;
 root.querySelectorAll('[data-grounding-tab]').forEach(button=>button.addEventListener('click',()=>{
  root.querySelectorAll('[data-grounding-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
  root.querySelectorAll('[data-grounding-panel]').forEach(panel=>{
   panel.hidden=panel.dataset.groundingPanel!==button.dataset.groundingTab;
   if(panel.hidden){
    panel.querySelectorAll('video').forEach(video=>video.pause());
   }
  });
 }));
})();

/* Continue the paper's illustrative scene through ordered clearance checks. */
(() => {
 const figure=document.querySelector('[data-shared-validation]'),api=window.CLEAR_METHOD_SCHEMATIC;if(!figure||!api)return;
 const svg=figure.querySelector('svg'),slider=figure.querySelector('input'),play=figure.querySelector('[data-validation-play]'),output=figure.querySelector('output');
 let progress=0,playing=!reduced.matches,visible=false,last=0;
 function draw(){
  svg.innerHTML=api.scene('2d','validation',progress);slider.value=progress;
  figure.dataset.progress=progress.toFixed(2);play.textContent=playing?'Pause':'Play';
  const state=api.validationState(progress),complete=state.clear.every(Boolean);
  output.textContent=progress===0?'Initial scene':complete?'Route open':progress<=1?'Relocate o₂':'Relocate o₃';
  for(const b of figure.querySelectorAll('[data-validation-step]'))b.setAttribute('aria-pressed',String(Math.abs(progress-Number(b.dataset.validationStep))<.005));
 }
 slider.addEventListener('input',()=>{progress=Number(slider.value);playing=false;draw();});
 play.addEventListener('click',()=>{if(progress>=2)progress=0;playing=!playing;last=0;draw();});
 figure.querySelectorAll('[data-validation-step]').forEach(b=>b.addEventListener('click',()=>{progress=Number(b.dataset.validationStep);playing=false;draw();}));
 new IntersectionObserver(entries=>{visible=entries.at(-1).isIntersecting;last=0;}).observe(figure);
 function tick(now){if(visible&&!document.hidden&&playing){progress=Math.min(2,progress+(last?Math.min(now-last,100):0)/3500);if(progress>=2)playing=false;draw();}last=now;requestAnimationFrame(tick);}
 draw();requestAnimationFrame(tick);
})();

/* The original controller videos and native scenes share the same RGB clock. */
(() => {
 const root=document.querySelector('[data-shared-execution]');if(!root)return;
 root.querySelectorAll('.viewer').forEach(viewer=>wireEgoVideo(viewer,viewer.querySelector('.preview-video'),viewer.querySelector('.ego-inset video')));
 root.querySelectorAll('[data-execution-tab]').forEach(button=>button.addEventListener('click',()=>{
  root.querySelectorAll('[data-execution-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
  root.querySelectorAll('[data-execution-panel]').forEach(panel=>{
   panel.hidden=panel.dataset.executionPanel!==button.dataset.executionTab;
   if(panel.hidden)panel.querySelectorAll('video').forEach(video=>video.pause());
  });
 }));
})();
