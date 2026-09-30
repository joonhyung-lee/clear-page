/* Three chapters, explicit details and local resource previews. */
(() => {
 const nav=document.querySelector('#research-nav');if(!nav)return;
 const resources=nav.querySelector('.research-resources');resources.id='research-resources';
 const resourceToggle=document.createElement('button');resourceToggle.type='button';resourceToggle.id='resource-menu-toggle';resourceToggle.setAttribute('aria-label','Resources');resourceToggle.setAttribute('aria-controls',resources.id);resourceToggle.setAttribute('aria-expanded','false');
 resourceToggle.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v14H5zM9 9h6M9 12h6M9 15h4"/></svg>';resources.before(resourceToggle);
 function resourceMenu(open){nav.dataset.resourcesOpen=String(open);resourceToggle.setAttribute('aria-expanded',String(open));}
 resourceToggle.onclick=()=>resourceMenu(resourceToggle.getAttribute('aria-expanded')!=='true');
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!document.querySelector('#resource-dialog').open&&nav.dataset.resourcesOpen==='true'){resourceMenu(false);resourceToggle.focus();}});
 document.addEventListener('pointerdown',e=>{if(!nav.contains(e.target)&&!e.target.closest('#resource-dialog'))resourceMenu(false);});
 const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
 function reveal(hash,focus=false){
  const target=document.getElementById(hash.slice(1));if(!target)return;
  for(let n=target;n;n=n.parentElement)if(n.tagName==='DETAILS')n.open=true;
  const input=target.closest('[data-input-content]');
  if(input)document.querySelector(`[data-input-panel="${input.dataset.inputContent}"]`)?.click();
  if(target.closest('[data-sample-panels]')){
   const panel=target.closest('[data-sample-panels]>section');
   document.querySelector(`[data-sample-panel="${panel.id}"]`)?.click();
  }
  requestAnimationFrame(()=>{target.scrollIntoView({behavior:reduced()?'instant':'smooth'});if(focus){target.tabIndex=-1;target.focus({preventScroll:true});}});
 }
 document.addEventListener('click',e=>{
  const a=e.target.closest('a[href^="#"]');if(!a||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||!document.getElementById(a.hash.slice(1)))return;
  e.preventDefault();history.pushState(null,'',a.hash);reveal(a.hash,true);
 });
 window.addEventListener('hashchange',()=>reveal(location.hash));
 window.addEventListener('popstate',()=>reveal(location.hash));
 const links=[...nav.querySelectorAll('.research-links a')];let queued=false;
 function current(){queued=false;let active=null;for(const link of links)if(document.querySelector(link.hash).getBoundingClientRect().top<180)active=link;links.forEach(link=>{if(link===active)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');});}
 window.addEventListener('scroll',()=>{if(!queued){queued=true;requestAnimationFrame(current);}},{passive:true});current();
 document.querySelectorAll('[data-sample-panel]').forEach(button=>button.onclick=()=>{
  document.querySelectorAll('[data-sample-panel]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
  document.querySelectorAll('[data-sample-panels]>section').forEach(p=>p.hidden=p.id!==button.dataset.samplePanel);
 });
 document.querySelectorAll('[data-grounding-body]').forEach(button=>button.onclick=()=>{
  document.querySelectorAll('[data-grounding-body]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
  document.querySelectorAll('#embodiment-demo .embodiment-gallery>figure').forEach(figure=>figure.hidden=figure.querySelector('.viewer').dataset.embodiment!==button.dataset.groundingBody);
 });
 document.querySelectorAll('[data-input-panel]').forEach(button=>button.onclick=()=>{
  document.querySelectorAll('[data-input-panel]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
  document.querySelectorAll('[data-input-content]').forEach(panel=>panel.hidden=panel.dataset.inputContent!==button.dataset.inputPanel);
 });
 document.querySelectorAll('.all-methods-toggle').forEach(button=>button.onclick=()=>{
  const expanded=button.getAttribute('aria-expanded')!=='true';button.setAttribute('aria-expanded',String(expanded));button.textContent=expanded?'Fewer methods':'All methods';button.closest('.experiment').classList.toggle('show-all-methods',expanded);
 });
 const dialog=document.querySelector('#resource-dialog'),content=dialog.querySelector('[data-resource-content]'),download=dialog.querySelector('[data-resource-download]');
 function close(){content.querySelector('video')?.pause();dialog.close();content.replaceChildren();}
 document.querySelectorAll('[data-resource]').forEach(button=>button.onclick=()=>{
  const paper=button.dataset.resource==='paper';dialog.querySelector('h2').textContent=paper?'Paper':'Video';
  const url=clearAssetURL(paper?'assets/clear-paper.pdf':'assets/media/teaser.mp4');
  download.href=url;download.textContent=paper?'Download PDF':'Download video';
  const preview=document.createElement(paper?'iframe':'video');
  if(paper){preview.title='Anonymous CLEAR paper';preview.src=clearAssetURL('assets/paper-preview.html');}else{preview.controls=true;preview.playsInline=true;preview.preload='metadata';preview.src=url;}
  content.replaceChildren(preview);dialog.showModal();
 });
 dialog.querySelector('[data-resource-close]').onclick=close;
 dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
 window.addEventListener('message',e=>{if(e.data?.type==='clear-paper-close'&&e.source===content.querySelector('iframe')?.contentWindow)close();});
 dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)close();}});

 // Move one measured evaluation panel between the two controller lineages.
 // Neither metric switches nor robot switches recreate the replay.
 const training=document.querySelector('#controller-pretraining'),evaluation=document.querySelector('#policy-evaluation');
 document.querySelectorAll('[data-policy-summary-body]').forEach(button=>button.onclick=()=>{
  document.querySelectorAll('[data-policy-summary-body]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
  document.querySelectorAll('[data-policy-summary-panel]').forEach(p=>p.hidden=p.dataset.policySummaryPanel!==button.dataset.policySummaryBody);
 });
 document.querySelectorAll('[data-summary-stage]').forEach(button=>button.onclick=()=>{
  training.closest('details').open=true;
  training.querySelector(`[data-loco-body="${button.dataset.summaryBody}"]`).click();
  training.querySelector('[data-loco-source="new"]').click();
  training.querySelector('#spot-curriculum').dispatchEvent(new CustomEvent('policy-select-checkpoint',{detail:{stage:button.dataset.summaryStage}}));
  training.scrollIntoView({behavior:reduced()?'instant':'smooth'});
 });
 let evaluationSelected=false;
 evaluation.removeAttribute('aria-labelledby');evaluation.setAttribute('aria-label','Measured policy evaluation');
 evaluation.querySelector('h5')?.remove();
 training.querySelectorAll('.loco-metrics').forEach(group=>{
  group.dataset.trainingMetric='optimization';
  const button=document.createElement('button');button.type='button';button.dataset.policyEvaluation='';button.textContent='Evaluation';button.setAttribute('aria-pressed','false');group.append(button);
  group.addEventListener('click',e=>{const selected=e.target.closest('button');if(!selected)return;evaluationSelected=selected===button;if(!evaluationSelected)group.dataset.trainingMetric=selected.dataset.locoMetrics||selected.dataset.curriculumMetrics;placeEvaluation();});
 });
 function placeEvaluation(){
  const selector=training.dataset.source==='recorded'?'[data-policy-recorded]':'#spot-curriculum';
  const evidence=training.querySelector(selector+' .loco-evidence');evidence.append(evaluation);evaluation.hidden=!evaluationSelected;
  training.querySelectorAll('.loco-evidence').forEach(e=>{
   e.classList.toggle('show-evaluation',evaluationSelected);
   e.querySelector('[data-policy-evaluation]').setAttribute('aria-pressed',String(evaluationSelected));
   const chosen=e.querySelector('.loco-metrics').dataset.trainingMetric;
   e.querySelectorAll('[data-loco-metrics],[data-curriculum-metrics]').forEach(b=>b.setAttribute('aria-pressed',String(!evaluationSelected&&(b.dataset.locoMetrics||b.dataset.curriculumMetrics)===chosen)));
  });
  window.dispatchEvent(new Event('resize'));
 }
 training.addEventListener('policy-body-change',placeEvaluation);placeEvaluation();
 if(location.hash)reveal(location.hash);
})();
