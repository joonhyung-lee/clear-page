/* Feature and selection overlays share the native scene and camera. */
window.CLEAR_CODE_LAYER_BRIDGE=function(){
 let viewer=null,focus='embodiment',stage='participation',visible=true;
 function apply(){
  if(!visible)return;
  if(!viewer){const root=document.querySelector('#root'),key=root&&Object.keys(root).find(k=>k.startsWith('__reactContainer'));const queue=key?[root[key],root[key]?.stateNode?.current]:[],seen=new Set();
   while(queue.length){const f=queue.pop();if(!f||seen.has(f))continue;seen.add(f);const v=f.memoizedProps?.value;if(v?.sceneTreeActions&&v?.useSceneTree){viewer=v;break;}queue.push(f.child,f.sibling,f.alternate);}}
  if(!viewer)return;
  const groups={'/features/embodiment':focus==='embodiment','/features/objects':focus==='objects','/features/scene':focus==='scene','/selection/participation':stage!=='context','/selection/order':stage==='order'};
  for(const [name,visibility] of Object.entries(groups)){
   const node=viewer.useSceneTree.get(name);if(node&&node.visibility!==visibility)viewer.sceneTreeActions.updateNodeAttributes(name,{visibility});
  }
 }
 window.addEventListener('message',e=>{if(e.source!==parent)return;const d=e.data;
  if(d?.type==='clear-scene-visible'){visible=!!d.visible;return;}
  if(d?.type!=='clear-code-focus')return;
  if(['embodiment','objects','scene'].includes(d.focus))focus=d.focus;
  if(['context','participation','order'].includes(d.stage))stage=d.stage;
  apply();
 });
 const timer=setInterval(apply,150);window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});
};
