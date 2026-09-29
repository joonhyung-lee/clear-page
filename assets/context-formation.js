/* Recorded encoder features, predictions and saved priority draws. */
(() => {
 const d=window.CLEAR_CONTEXT,layout=document.querySelector('.maze-order-layout');if(!d||!layout)return;
 layout.querySelectorAll('.context-source,.context-target').forEach(e=>e.remove());
 const root=document.createElement('section');root.className='context-formation';root.id='context-formation';
 root.innerHTML='<div class="context-heading"><h5>Encode the observed scene</h5></div><div class="context-chain"><div class="context-inputs"><h5>Observed inputs</h5><div>Robot structure <span>G1</span></div><div>Object states <span>3 objects</span></div><div>Scene geometry <span>Walls and routes</span></div></div><div class="context-latent"><h5>Shared encoder → H</h5><div class="context-heatmap"></div><p class="context-dimensions"></p></div><div class="context-head"><h5>Shared OrderNet head</h5><p class="context-head-rule">Different object tokens pass through the same learned weights.</p><div class="context-predictions"></div></div></div><div class="context-inference"><div class="context-inference-rows"></div><div class="context-inference-result"></div></div><p class="context-note">This recorded G1 example connects encoded inputs to object selection and priority sampling. The heatmap and predictions belong to this example. Dataset points above have their own predictions.</p>';
 layout.prepend(root);
 root.querySelector('.context-dimensions').textContent=`${d.displayDimensions} of ${d.dimensions} features shown · ${d.validTokens} valid tokens`;
 const limit=Math.max(...d.features.flat().map(Math.abs));
 d.features.forEach((values,i)=>{const row=document.createElement('div');row.className='context-token';row.dataset.object=i>0&&i<4?String(i-1):'';const label=document.createElement('span');label.textContent=d.labels[i];row.append(label);values.forEach(value=>{const cell=document.createElement('i');const weight=Math.min(1,Math.abs(value)/limit);cell.style.background=value>=0?`rgba(87,132,103,${.1+.9*weight})`:`rgba(163,128,103,${.1+.9*weight})`;cell.title=value.toFixed(3);row.append(cell);});root.querySelector('.context-heatmap').append(row);});
 d.selection.forEach((q,i)=>{const row=document.createElement('div');row.className='context-output';row.dataset.object=String(i);row.innerHTML=`<span>Object ${i}</span><div class="context-probability"><i style="width:${100*q}%"></i></div><strong>${q<.001?'<0.1':q>.999?'>99.9':(100*q).toFixed(1)}%</strong><small>priority ${d.mu[i].toFixed(2)} ± ${d.sigma[i].toFixed(2)}</small>`;root.querySelector('.context-predictions').append(row);});
 let activeObject=1;
 function drawInference(){
  const trace=window.CLEAR_MAZE_TRACE,idx=Number(layout.querySelector('.viewer')?.dataset.orderSample||0),sample=trace.traces[idx];
  const host=root.querySelector('.context-inference-rows');host.replaceChildren();
  d.selection.forEach((q,i)=>{
   const row=document.createElement('div');row.className='context-sampling-row';row.dataset.object=String(i);
   const draw=sample.selectionDraw[i],u=sample.priority[i],epsilon=(u-d.mu[i])/d.sigma[i],selected=sample.selected[i];
   row.innerHTML=`<button type="button" class="context-object-choice" data-inspect-object="${i}">Object ${i}</button><div class="context-gate"><span>Selection draw</span><div class="context-draw-track"><i style="width:${100*q}%"></i><b style="left:${100*draw}%"></b></div><small>${draw.toFixed(3)} ${selected?' < ':' ≥ '} q = ${q.toFixed(5)} · ${selected?'keep':'omit'}</small></div><div class="context-priority-draw"><span>Priority draw</span><strong>${d.mu[i].toFixed(2)} + ${d.sigma[i].toFixed(2)} × ${epsilon.toFixed(2)} ≈ ${u.toFixed(2)}</strong><small>mean + spread × sampled noise</small></div><div class="context-rank-result">${selected?'Rank '+(sample.rank[i]+1):'Excluded'}</div>`;
   host.append(row);
  });
  const order=sample.rank.map((rank,i)=>({rank,i})).filter(v=>v.rank>=0).sort((a,b)=>a.rank-b.rank);
  root.querySelector('.context-inference-result').textContent='Sort only the selected priorities: '+order.map(o=>'Object '+o.i+' ('+sample.priority[o.i].toFixed(2)+')').join(' → ')+' → CausalFlowNet';
  inspect(activeObject);queueMicrotask(()=>inspect(activeObject));
 }
 function inspect(i){activeObject=i;root.dataset.object=String(i);root.querySelectorAll('[data-object]').forEach(row=>row.classList.toggle('context-selected',row.dataset.object===String(i)));root.querySelectorAll('[data-inspect-object]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.inspectObject)===i)));document.querySelectorAll('.ordering-main svg [data-object]').forEach(row=>row.classList.toggle('ordering-focus',row.dataset.object===String(i)));}
 layout.addEventListener('pointerover',e=>{const row=e.target.closest('.ordering-main svg [data-object]');if(row)inspect(Number(row.dataset.object));});
 layout.addEventListener('focusin',e=>{const row=e.target.closest('.ordering-main svg [data-object]');if(row)inspect(Number(row.dataset.object));});
 root.addEventListener('click',e=>{const b=e.target.closest('[data-inspect-object]');if(b)inspect(Number(b.dataset.inspectObject));});
 document.addEventListener('clear-order-draw',drawInference);
 document.addEventListener('DOMContentLoaded',drawInference);
 root.querySelectorAll('[data-object]').forEach(node=>{node.addEventListener('pointerenter',()=>{if(node.dataset.object==='')return;layout.querySelector('.viewer iframe')?.contentWindow.postMessage({type:'clear-order-focus',object:Number(node.dataset.object)},'*');root.querySelectorAll('[data-object]').forEach(row=>row.classList.toggle('context-selected',row.dataset.object===node.dataset.object));});node.addEventListener('pointerleave',()=>{layout.querySelector('.viewer iframe')?.contentWindow.postMessage({type:'clear-order-focus',object:null},'*');root.querySelectorAll('.context-selected').forEach(row=>row.classList.remove('context-selected'));});});
 new IntersectionObserver(entries=>root.classList.toggle('is-visible',entries[0].isIntersecting)).observe(root);
})();
