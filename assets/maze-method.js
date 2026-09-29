(() => {
 const d=window.CLEAR_MAZE_TRACE,root=document.querySelector('#method-order');if(!d||!root)return;
 let sample=0,playing=false,pending=null;
 const viewer=document.querySelector('.maze-flow-viewer'),orderViewer=root.querySelector('.viewer');
 function updateOrder(){
  orderViewer.dataset.orderStage='sampling';orderViewer.dataset.orderSample=String(sample);
  orderViewer.querySelector('iframe')?.contentWindow.postMessage({type:'clear-order-stage',stage:'sampling',sample},'*');
 }
 function update(reload=false){
  const trace=d.traces[sample],rows=document.querySelector('#maze-selection-rows');rows.replaceChildren();
  root.querySelector('.maze-selection-table thead tr').innerHTML='<th>Object</th><th>Selection</th><th>Mean ± σ</th><th>Sampled priority</th>';
  d.scene.objects.forEach((object,i)=>{
   const tr=document.createElement('tr');tr.dataset.selected=String(trace.selected[i]);
   const priority=trace.selected[i]?trace.priority[i].toFixed(2):'Not selected';
   [object.object_id+' · '+object.mass_kg+' kg',(100*d.selection[i]).toFixed(3)+'%',d.mu[i].toFixed(2)+' ± '+d.sigma[i].toFixed(2),priority].forEach((text,j)=>{const cell=document.createElement(j===0?'th':'td');if(j===0)cell.scope='row';cell.textContent=text;tr.append(cell);});rows.append(tr);
  });
  const order=trace.rank.map((rank,i)=>({rank,i})).filter(o=>o.rank>=0).sort((a,b)=>a.rank-b.rank);
  document.querySelector('#maze-order-result').textContent=order.map(o=>'Object '+o.i).join(' → ');
  document.querySelector('#maze-order-sample').textContent='Sample '+(sample+1)+' of '+d.traces.length;
  document.querySelector('#maze-flow-sample').value=String(sample);
  const scene='method-flow-'+sample+'-refined',active=!!viewer.querySelector('iframe');
  if(viewer.dataset.scene!==scene){viewer.dispatchEvent(new Event('reset-viewer'));viewer.dataset.scene=scene;viewer.querySelector('.preview-image').src=clearAssetURL('assets/media/'+scene+'.png');if(active&&reload)viewer.querySelector('.launch').click();}
  updateOrder();
 }
 document.querySelector('#maze-order-next').addEventListener('click',()=>{sample=(sample+1)%d.traces.length;update(true);});
 document.querySelector('#maze-flow-sample').addEventListener('change',e=>{sample=+e.target.value;update(true);});
 function controls(time=0){document.querySelector('#flow-time').textContent=time.toFixed(2);document.querySelector('#flow-progress').value=time;document.querySelector('#flow-play').textContent=playing?'Pause generation':'Play generation';}
 function command(value){const iframe=viewer.querySelector('iframe');if(iframe)iframe.contentWindow.postMessage({type:'clear-playback-command',...value},'*');else{pending=value;if(!viewer.querySelector('.viewer-status'))viewer.querySelector('.launch').click();}}
 document.querySelector('#flow-play').addEventListener('click',()=>command({playing:!playing}));
 document.querySelector('#flow-replay').addEventListener('click',()=>command({time:0,playing:true}));
 window.addEventListener('message',event=>{
  if(event.source!==viewer.querySelector('iframe')?.contentWindow||event.data?.type!=='clear-playback-time')return;
  if(pending){command(pending);pending=null;}playing=event.data.playing;controls(Math.max(0,Math.min(1,event.data.time/(359/60))));
 });
 viewer.addEventListener('reset-viewer',()=>{playing=false;controls();});
 observeAutomaticScene(viewer);
 update();controls();
})();
