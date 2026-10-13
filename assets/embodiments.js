(() => {
 const root=document.querySelector('#embodiment-demo');if(!root)return;
 const descriptions={
  structure:'Link and joint structure across robot embodiments.',
  traversability:'Green highlights the legs or wheels and circular ground regions beneath the robot.',
  manipulation:'Green follows the manipulation surfaces: G1 arms and hands, the Spot + arm manipulator, and the Spot base.'
 };
 // Preview modes share the original robot materials and walking clock.
 root.querySelectorAll('[data-embodiment-mode]').forEach(button=>button.addEventListener('click',()=>{
  const mode=button.dataset.embodimentMode;
  root.querySelectorAll('[data-embodiment-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
  root.querySelectorAll('.viewer').forEach(viewer=>{
   const name=viewer.dataset.embodiment;
   viewer.dataset.displayMode=mode;
   // Keep one walking recording and its camera, playhead, and scene graph.
   viewer.dataset.scene='structure-'+name;
   const current=viewer.querySelector('video[data-active-preview]');
   const time=current?.currentTime||0;
   let preview=viewer.querySelector(`video[data-loop-mode="${mode}"]`);
   const stem=`assets/media/${mode==='structure'?'structure':`affordance-${mode}`}-${name}`;
   if(!preview){
    preview=document.createElement('video');preview.className='preview-video';
    preview.dataset.inlineLoop='';preview.dataset.loopMode=mode;preview.dataset.loopSource=stem+'.mp4';
    preview.controls=true;preview.poster=clearAssetURL(stem+'.png');
    viewer.insertBefore(preview,viewer.querySelector('.launch'));
    window.CLEAR_INLINE_LOOPS.prepare(preview);
   }
   const inspecting=!!viewer.querySelector('iframe.scene-ready');
   viewer.querySelectorAll('video[data-inline-loop]').forEach(video=>{
    video.hidden=video!==preview||inspecting;
    video.toggleAttribute('data-active-preview',video===preview);
   });
   preview.setAttribute('aria-label',`${viewer.dataset.title}: ${mode}`);
   // Keep each mode's decoded video so returning to it does not reload its URL.
   window.CLEAR_INLINE_LOOPS.resume(preview,time);
   viewer.dispatchEvent(new Event('preview-changed'));
   const iframe=viewer.querySelector('iframe');
   if(iframe)iframe.contentWindow.postMessage({type:'clear-embodiment-mode',mode},'*');

  });
  root.querySelector('.embodiment-explanation').textContent=descriptions[mode];
 }));
})();
