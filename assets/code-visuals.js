/* Numeric explanation uses the same observation as all five native figures. */
(() => {
 const data=window.CLEAR_CODE_NATIVE;if(!data)return;
 function featureCards(figure){
  const host=figure.querySelector('.component-features'),r=data.representation;
  const average=rows=>rows[0].map((_,i)=>rows.reduce((sum,row)=>sum+row[i],0)/rows.length);
  const weights=average(r.attention);
  for(const [kind,title,indices,detail] of [
   ['embodiment','Embodiment',[0],r.structure.length+' links · '+r.structure[0].length+' input features'],
   ['objects','Objects',[1,2,3],data.scene.objects.length+' objects · pose, size, mass, friction'],
   ['scene','Scene',r.keys.map((k,i)=>i).filter(i=>i>3),data.scene.walls.length+' walls · start and goal']]){
   const card=document.createElement('button');card.type='button';card.dataset.componentFocus=kind;card.setAttribute('aria-pressed',String(kind==='embodiment'));card.className='feature-card';
   const heading=document.createElement('strong');heading.textContent=title;card.append(heading);
   const summary=document.createElement('small');summary.textContent=detail;card.append(summary);
   const vector=average(indices.map(i=>r.tokens[i]));const maximum=Math.max(...vector.map(Math.abs),1e-9);
   const heat=document.createElement('span');heat.className='feature-vector';heat.setAttribute('aria-label',title+' encoded features');
   vector.forEach((value,i)=>{const cell=document.createElement('i');const a=Math.abs(value)/maximum;cell.style.background=value>=0?`rgba(36,120,87,${.12+.88*a})`:`rgba(78,111,161,${.12+.88*a})`;cell.title=`${title} · channel ${i}: ${value.toFixed(4)}`;heat.append(cell);});
   card.append(heat);const note=document.createElement('span');note.className='feature-stat';const share=indices.reduce((sum,i)=>sum+weights[i],0);
   note.textContent='Attention '+(100*share).toFixed(1)+'%';note.title='Encoder attention averaged over layers, heads and object queries. Group shares sum to 100%. Embeddings are averaged within each group.';card.append(note);host.append(card);
  }
 }
 function selection(figure){
  const host=figure.querySelector('.selection-logic');
  data.selection.forEach((q,i)=>{const row=document.createElement('div');row.className='selection-row';
   const name=document.createElement('span');name.textContent='Object '+i;row.append(name);
   const bar=document.createElement('span');bar.className='participation-bar';bar.title=`q = ${q.toFixed(6)}; draw = ${data.selectionDraw[i].toFixed(6)}. Independent Bernoulli participation; selected when draw < q.`;
   const fill=document.createElement('i');fill.style.width=(q*100)+'%';const draw=document.createElement('b');draw.style.left=(data.selectionDraw[i]*100)+'%';bar.append(fill,draw);row.append(bar);
   const probability=document.createElement('span');probability.className='participation-value';probability.textContent=q<.001?'<0.1%':q>.999?'>99.9%':(q*100).toFixed(1)+'%';row.append(probability);
   const score=document.createElement('span');score.className='latent-score';score.textContent=data.rank[i]<0?'Omit':'u = '+data.priority[i].toFixed(2)+' → '+(data.rank[i]+1);row.append(score);host.append(row);
  });
 }
 for(const figure of document.querySelectorAll('[data-native-example]')){
  const kind=figure.dataset.nativeExample,viewer=figure.querySelector('.viewer');
  if(kind==='representation')featureCards(figure);if(kind==='ordering')selection(figure);
  const slider=figure.querySelector('input[type=range]'),play=figure.querySelector('[data-native-play]'),output=figure.querySelector('output');
  const duration=kind==='generation'?8:kind==='validation'?12:kind==='execution'?data.execution.duration:0;
  let time=kind==='generation'?6:0,playing=false,focus='embodiment',stage='participation';
  const send=message=>viewer.querySelector('iframe')?.contentWindow.postMessage(message,'*');
  const syncFocus=()=>send({type:'clear-code-focus',focus,stage});
  const ensureScene=()=>{if(!viewer.querySelector('iframe,.viewer-status'))viewer.querySelector('.launch').click();};
  function draw(){if(slider)slider.value=String(time);if(play)play.textContent=playing?'Pause':kind==='generation'?'Play generation':kind==='validation'?'Play sequence':'Play';
   if(output)output.textContent=kind==='generation'?'Flow t = '+Math.min(1,time/6).toFixed(2):kind==='validation'?(time<4?'Open passage 1':time<8?'Open passage 2':'Route to goal'):time.toFixed(1)+' / '+duration.toFixed(1)+' s';}
  function command(nextTime,nextPlaying){time=nextTime;playing=nextPlaying;send({type:'clear-playback-command',time,playing});draw();}
  function request(nextTime,nextPlaying){command(nextTime,nextPlaying);ensureScene();}
  viewer.addEventListener('scene-settled',()=>{if(!viewer.querySelector('iframe.scene-ready'))return;syncFocus();command(time,playing);});
  for(const button of figure.querySelectorAll('[data-component-focus]'))button.addEventListener('click',()=>{focus=button.dataset.componentFocus;
   figure.querySelectorAll('[data-component-focus]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));syncFocus();ensureScene();});
  for(const button of figure.querySelectorAll('[data-selection-stage]'))button.addEventListener('click',()=>{stage=button.dataset.selectionStage;figure.dataset.selection=stage;
   figure.querySelectorAll('[data-selection-stage]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
   figure.querySelector('.selection-explanation').textContent={context:'Shared context conditions object participation and latent priority.',participation:'Bars show participation probability. Marks show the uniform draw. Include when draw < probability.',order:'Sample u = μ + σε for each included object. Lower sampled scores execute first.'}[stage];syncFocus();ensureScene();});
  play?.addEventListener('click',()=>{request(!playing&&(time>=duration-.1||kind==='generation'&&time>=6)?0:time,!playing);});
  figure.querySelector('[data-native-replay]')?.addEventListener('click',()=>request(0,true));
  slider?.addEventListener('input',()=>request(Number(slider.value),false));
  for(const jump of figure.querySelectorAll('[data-replay-jump]'))jump.addEventListener('click',()=>request(Number(jump.dataset.replayJump),false));
  window.addEventListener('message',event=>{if(event.source!==viewer.querySelector('iframe.scene-ready')?.contentWindow||event.data?.type!=='clear-playback-time')return;
   time=event.data.time;playing=!!event.data.playing;if(duration&&time>=duration-.02&&playing){command(duration-.001,false);return;}draw();});
  draw();observeAutomaticScene(viewer);
 }
})();
