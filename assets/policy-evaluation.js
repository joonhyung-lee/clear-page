/* Measured checkpoint evaluations. Synthetic fallback examples are explicitly opt-in. */
(() => {

const bodies={
 g1_scratch:{name:'G1 · from scratch',end:18000,phases:[['Locomotion',0,6000],['Terrain adaptation',6000,18000]],note:'New G1 training begins with random weights before the first optimizer update. Evaluations use the same fixed protocol as the other bodies.'},
 g1:{name:'G1',end:22800,phases:[['Terrain adaptation',0,17100],['Action rate regularization',17100,22800]],note:'G1 starts from its archived warm start checkpoint. Update 0 already includes prior training.'},
 spot:{name:'Spot',end:9000,phases:[['Locomotion',0,3000],['Terrain adaptation',3000,9000]],note:'Spot uses an independent physical model without an arm. Phase spans show the training schedule, not evidence of mastery.'},
 spot_arm:{name:'Spot + arm',end:13000,phases:[['Locomotion',0,3000],['Terrain adaptation',3000,9000],['Arm pose adaptation',9000,13000]],note:'Spot + arm uses its own articulated physical model and policy. Every checkpoint is evaluated at the same nominal arm pose.'}
};
bodies.spot_arm_recorded={name:'Spot + arm · recorded controller',end:28000,phases:[['Mixed terrain',0,7000],['Torso control',7000,13200],['Arm pose curriculum',13200,28000]],note:'Archived controller lineage. Arm adaptation begins at update 13,200. Its initial checkpoint is not the random initialization of the new training run.'};
const metrics=[
 {key:'tracking',title:'Velocity tracking error',unit:'m/s',direction:'Lower is better ↓',max:1.2,color:'#57754f',values:[.92,.84,.75,.67,.59,.54,.50,.46,.43,.40,.38,.35,.33,.31,.29,.28,.26,.25,.24,.23,.22],spread:[.16,.05],description:'Planar velocity RMSE under the same commanded motion.'},
 {key:'success',title:'Terrain traversal success',unit:'%',direction:'Higher is better ↑',max:100,color:'#668bab',values:[5,8,13,19,26,32,38,44,49,54,58,62,66,70,73,76,78,80,82,84,85],spread:[9,5],description:'Goal reached in time, without a fall. Standing still is not a success.'},
 {key:'falls',title:'Fall rate',unit:'%',direction:'Lower is better ↓',max:100,color:'#af8467',values:[76,69,61,55,48,42,37,33,29,26,23,21,19,17,15,14,12,11,10,9,8],spread:[11,4],description:'Episodes ending in a fall, across the same evaluation suite.'}
];
const phaseColors=['#c2d4ba','#c0d3e4','#ddcbb9'];
const root=document.querySelector('#policy-evaluation'),section=document.querySelector('#controller-pretraining');
if(!root||!section)return;
const host=root.querySelector('.plots'),slider=root.querySelector('input');
let body='g1',point=null,illustrative=false;
const fmt=n=>n.toLocaleString('en-US');
const measured=()=>window.CLEAR_POLICY_EVALUATION?.bodies?.[body];
function rows(){
 if(!illustrative)return measured()?.rows||[];
 return metrics[0].values.map((_,i)=>{
  const row={update:Math.round(i/20*bodies[body].end)};
  metrics.forEach(m=>{const spread=m.spread[0]+(m.spread[1]-m.spread[0])*i/20;
   row[m.key]={mean:m.values[i],low:Math.max(0,m.values[i]-spread),high:Math.min(m.max,m.values[i]+spread)};
  });return row;
 });
}
function selectPoint(i){const data=rows();if(!data.length)return;point=Math.max(0,Math.min(data.length-1,i));render();}
function inspect(e,svg){
 const data=rows();if(!data.length)return;
 const rect=svg.getBoundingClientRect(),update=((e.clientX-rect.left)/rect.width*440-43)/380*bodies[body].end;
 selectPoint(data.reduce((best,row,i)=>Math.abs(row.update-update)<Math.abs(data[best].update-update)?i:best,0));
}
metrics.forEach(m=>{
 const figure=document.createElement('figure');figure.dataset.metric=m.key;
 figure.innerHTML=`<figcaption>${m.title}<span class="direction">${m.direction}</span></figcaption><div class="reading"><span class="value"></span><span class="unit"></span></div><div class="delta"></div><svg viewBox="0 0 440 190" role="img"></svg><p class="explain">${m.description}</p>`;
 host.append(figure);const svg=figure.querySelector('svg');
 svg.addEventListener('pointermove',e=>{if(e.pointerType!=='touch')inspect(e,svg)});
 svg.addEventListener('pointerdown',e=>inspect(e,svg));
 svg.addEventListener('keydown',e=>{
  if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)&&rows().length){
   e.preventDefault();selectPoint(e.key==='Home'?0:e.key==='End'?rows().length-1:point+(e.key==='ArrowLeft'?-1:1));
  }
 });
});
function render(){
 const b=bodies[body],data=rows(),real=!illustrative&&data.length>0;
 point=data.length?Math.min(point??data.length-1,data.length-1):0;
 const selected=data[point];
 root.dataset.mode=real?'measured':illustrative?'illustrative':'unmeasured';root.dataset.body=body;
 const example=root.querySelector('[data-eval-example]');example.hidden=!!measured();
 example.setAttribute('aria-pressed',String(illustrative));example.textContent=illustrative?'Hide illustrative example':'Show illustrative example';
 root.querySelector('.eval-disclosure').textContent=real?
  `${b.name} · Measured evaluation · ${data.length}/${measured().plannedCheckpoints} checkpoints${measured().complete?'':measured().trainingState==='stopped'?' · Training stopped · Partial evaluation':' · Evaluation in progress'} · 60 episodes per checkpoint · One trained policy lineage. Tracking bands show episode variability. Rate bands show 95% Wilson intervals.`:
  illustrative?'Illustrative data only. These shared example curves are not measured robot performance. Shaded bands are illustrative, not confidence intervals.':
  'Fixed-protocol evaluation has not been recorded for this controller lineage. No measured values are shown.';
 slider.disabled=!data.length;slider.max=Math.max(0,data.length-1);slider.value=point;
 root.querySelector('.step').textContent=selected?`${real?'Measured':'Example'} checkpoint · Update ${fmt(selected.update)}`:`${b.name} · Awaiting evaluation`;
 root.querySelector('.body-note').textContent=b.note;root.querySelector('.last-step').textContent=fmt(data.at(-1)?.update??b.end);
 slider.setAttribute('aria-valuetext',selected?`${b.name}, ${real?'measured':'example'} update ${fmt(selected.update)}`:'Awaiting evaluation');
 root.querySelector('.phases').innerHTML=b.phases.map((p,i)=>`<span><i class="phase-dot" style="background:${phaseColors[i]}"></i>${p[0]} · ${fmt(p[1])}–${fmt(p[2])}</span>`).join('');
 const legend=root.querySelector('.legend');legend.hidden=!data.length;
 legend.innerHTML=real?'<span><i class="swatch"></i>Tracking: mean ±1 episode SD</span><span>Rates: 95% Wilson interval</span><span><i class="dash"></i>Measured update 0</span><span>Hover, tap or use arrow keys to inspect</span>':'<span><i class="swatch"></i>Example mean and illustrative spread</span><span><i class="dash"></i>Example update 0</span>';
 let context=root.querySelector('.eval-sample-context');
 if(!context){context=document.createElement('p');context.className='eval-sample-context';legend.after(context);}
 context.hidden=!real;
 if(real)context.textContent=`${selected.success.count}/${selected.episodes} goals reached · ${selected.falls.count}/${selected.episodes} falls · ${selected.episodes-selected.success.count-selected.falls.count} time limits · Mean forward progress ${selected.meanProgress.toFixed(2)} m. Episodes end at the goal, at a fall, or at 20 s. Mean duration ${selected.meanDuration.toFixed(1)} s. Tracking error is measured over that interval.`;
 metrics.forEach((m,k)=>{
  const figure=host.children[k],current=selected?.[m.key],first=data[0]?.[m.key];
  figure.querySelector('.unit').textContent=m.unit+(illustrative?' · example':'');
  figure.querySelector('.value').textContent=current?current.mean.toFixed(m.key==='tracking'?3:1):'—';
  if(current){
   const delta=current.mean-first.mean;
   figure.querySelector('.delta').textContent=`From ${first.mean.toFixed(m.key==='tracking'?3:1)} ${m.unit} at update 0 · ${delta<0?'−':delta>0?'+':''}${Math.abs(delta).toFixed(m.key==='tracking'?3:1)} ${m.unit==='%'?'percentage points':'m/s'}`;
  }else figure.querySelector('.delta').textContent='Update 0 comparison awaits evaluation';
  figure.dataset.inspected=JSON.stringify(selected?{update:selected.update,metric:m.key,...current,source:real?'measured':'illustrative'}:null);
  const max=m.key==='tracking'&&real?Math.max(.1,...data.map(row=>row[m.key].high))*1.1:m.max;
  const x=update=>43+update/b.end*380,y=value=>145-value/max*110;
  let svg='';
  b.phases.forEach((phase,i)=>{const a=x(phase[1]),z=x(phase[2]);svg+=`<rect x="${a}" y="35" width="${z-a}" height="110" fill="${phaseColors[i]}" opacity=".14"/><path d="M${a+1} 33 v-7 H${z-1} v7" fill="none" stroke="${phaseColors[i]}" stroke-width="2"/><text x="${(a+z)/2}" y="17" text-anchor="middle" font-size="12" fill="#71806a">Phase ${i+1}</text>`;});
  for(let j=0;j<=4;j++){const value=max*j/4;svg+=`<path d="M43 ${y(value)} H423" stroke="#e0e5dd"/><text x="34" y="${y(value)+4}" text-anchor="end" fill="#7c8875" font-size="12">${m.key==='tracking'?value.toFixed(2):value}</text>`;}
  if(current){
   const upper=data.map(row=>`${x(row.update)},${y(row[m.key].high)}`),lower=data.map(row=>`${x(row.update)},${y(row[m.key].low)}`).reverse();
   svg+=`<polygon points="${upper.concat(lower).join(' ')}" fill="${m.color}" opacity=".14"/><path d="M43 ${y(first.mean)} H423" stroke="#919b8a" stroke-dasharray="4 4"/><polyline points="${data.map(row=>`${x(row.update)},${y(row[m.key].mean)}`).join(' ')}" fill="none" stroke="${m.color}" stroke-width="2.5" stroke-linejoin="round"/>`;
   if(real)data.forEach(row=>{svg+=`<circle cx="${x(row.update)}" cy="${y(row[m.key].mean)}" r="2.5" fill="${m.color}" stroke="white" stroke-width="1"/>`;});
   svg+=`<path d="M${x(selected.update)} 35 V145" stroke="${m.color}" opacity=".5" stroke-dasharray="3 3"/><circle cx="${x(selected.update)}" cy="${y(current.mean)}" r="5" fill="${m.color}" stroke="white" stroke-width="2"/>`;
  }else svg+='<rect x="76" y="122" width="312" height="47" fill="white" opacity=".95"/><text x="232" y="150" text-anchor="middle" font-size="12" fill="#76816d">Not yet evaluated</text>';
  [0,.25,.5,.75,1].forEach(t=>{const update=Math.round(t*b.end);svg+=`<text x="${x(update)}" y="165" text-anchor="${t===0?'start':t===1?'end':'middle'}" font-size="12" fill="#7c8875">${fmt(update)}</text>`;});
  svg+='<text x="233" y="186" text-anchor="middle" font-size="12" fill="#7c8875">Training update</text>';
  const canvas=figure.querySelector('svg');canvas.innerHTML=svg;canvas.setAttribute('tabindex',current?'0':'-1');canvas.setAttribute('aria-label',m.title+(real?', measured evaluation. Arrow keys inspect checkpoints.':illustrative?', illustrative data. Arrow keys inspect examples.':', not yet evaluated.'));
 });
}
function sync(){
 let next=section.dataset.body||'g1';if(next==='g1'&&section.dataset.source!=='recorded')next='g1_scratch';if(next==='spot_arm'&&section.dataset.source==='recorded')next='spot_arm_recorded';
 if(next!==body){point=null;illustrative=false;}
 body=next;render();
}
root.querySelector('[data-eval-example]').onclick=()=>{illustrative=!illustrative;point=null;render()};
slider.oninput=()=>selectPoint(Number(slider.value));
section.addEventListener('policy-body-change',sync);sync();
let nearby=false,refreshing=false;
function refreshScratch(){
 if(!nearby||document.hidden||body!=='g1_scratch'||refreshing)return;
 refreshing=true;
 const previous=rows(),selectedUpdate=previous[point]?.update;
 const follow=point===previous.length-1&&document.activeElement?.tagName.toLowerCase()!=='svg';
 const script=document.createElement('script');
 script.src='assets/g1_scratch-evaluation-data.js?t='+Math.floor(Date.now()/30000);
 script.onload=()=>{
  refreshing=false;script.remove();
  if(body==='g1_scratch'){
   point=follow?null:Math.max(0,rows().findIndex(row=>row.update===selectedUpdate));render();
  }
 };
 script.onerror=()=>{refreshing=false;script.remove()};
 document.head.append(script);
}
new IntersectionObserver(entries=>{nearby=entries[0].isIntersecting;if(nearby)refreshScratch()},{rootMargin:'200px'}).observe(root);
setInterval(refreshScratch,30000);
document.addEventListener('visibilitychange',refreshScratch);
})();
