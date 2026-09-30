(() => {
 const d=window.CLEAR_MAZE_TRACE,root=document.querySelector('#method-order');if(!d||!root)return;
 let sample=0;
 const orderViewer=root.querySelector('.viewer');
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
  document.querySelector('#maze-order-result').textContent=order.length?order.map(o=>'Object '+o.i).join(' → '):'No interaction sampled';
  document.querySelector('#maze-order-sample').textContent='Sample '+(sample+1)+' of '+d.traces.length;
  updateOrder();document.dispatchEvent(new Event('clear-order-draw'));
 }
 document.querySelector('#maze-order-next').addEventListener('click',()=>{sample=(sample+1)%d.traces.length;update(true);});
 update();
})();
