(() => {
 const root=document.querySelector('#embodiment-demo');if(!root)return;
 const descriptions={
  structure:'Translucent visual meshes reveal the links and joints of each body. Inspect any robot in 3D.',
  traversability:'Green highlights the legs or wheels that support locomotion. The translucent ground region illustrates the local support neighborhood, not a predicted terrain feasibility map.',
  manipulation:'Green highlights arms or body contact surfaces. Translucent regions mark contact neighborhoods at the hands, gripper, or front of the body. These geometric illustrations are not learned affordance scores.'
 };
 // Start one shared walking player per body when the gallery enters view.
 // Mode buttons then operate only on material and overlay properties.
 if(!matchMedia('(prefers-reduced-motion: reduce)').matches){
  const observer=new IntersectionObserver(entries=>{
   if(!entries.some(e=>e.isIntersecting))return;
   observer.disconnect();
   root.querySelectorAll('.viewer').forEach(viewer=>{
    if(!viewer.querySelector('iframe,.viewer-status'))viewer.querySelector('.launch').click();
   });
  },{rootMargin:'120px',threshold:0});
  observer.observe(root);
 }
 root.querySelectorAll('[data-embodiment-mode]').forEach(button=>button.addEventListener('click',()=>{
  const mode=button.dataset.embodimentMode;
  root.querySelectorAll('[data-embodiment-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
  root.querySelectorAll('.viewer').forEach(viewer=>{
   const name=viewer.dataset.embodiment;
   viewer.dataset.displayMode=mode;
   // Keep one walking recording and its camera, playhead, and scene graph.
   viewer.dataset.scene='structure-'+name;
   const preview=viewer.querySelector('.preview-image');preview.src=clearAssetURL(`assets/media/${mode==='structure'?'structure':`affordance-${mode}`}-${name}.png`);preview.alt=`${viewer.dataset.title}: ${mode}`;
   const iframe=viewer.querySelector('iframe');
   if(iframe)iframe.contentWindow.postMessage({type:'clear-embodiment-mode',mode},'*');
   else if(!viewer.querySelector('.viewer-status'))viewer.querySelector('.launch').click();

  });
  root.querySelector('.embodiment-explanation').textContent=descriptions[mode];
 }));
})();
