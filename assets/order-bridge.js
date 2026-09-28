window.CLEAR_ORDER_BRIDGE=function(){
 let viewer=null,stage=window.__CLEAR_ORDER__?.stage||'context',sample=window.__CLEAR_ORDER__?.sample||0;
 function apply(){
  if(!viewer){const root=document.querySelector('#root');if(!root)return;const r=root[Object.keys(root).find(k=>k.startsWith('__reactContainer'))],q=[r,r?.stateNode?.current],seen=new Set();while(q.length){const f=q.pop();if(!f||seen.has(f))continue;seen.add(f);const v=f.memoizedProps?.value;if(v?.sceneTreeActions&&v?.useSceneTree){viewer=v;break;}q.push(f.child,f.sibling,f.alternate);}}
  if(!viewer)return;
  const active=stage==='sampling'?'sample-'+sample:stage;
  for(const [name,node] of Object.entries(viewer.useSceneTree.getAll())){
   if(/^\/label-\d+$/.test(name)){const visible=stage==='context';if(node.visibility!==visible)viewer.sceneTreeActions.updateNodeAttributes(name,{visibility:visible});continue;}
   if(!/^\/order\/(context|supervision|prediction|sample-\d+)$/.test(name))continue;
   const visible=name==='/order/'+active;if(node.visibility!==visible)viewer.sceneTreeActions.updateNodeAttributes(name,{visibility:visible});
  }
 }
 window.addEventListener('message',e=>{if(e.source!==parent||e.data?.type!=='clear-order-stage')return;if(!['context','supervision','prediction','sampling'].includes(e.data.stage))return;stage=e.data.stage;sample=Math.max(0,Math.min(3,Number(e.data.sample)||0));apply();});
 const timer=setInterval(apply,100);window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
};
