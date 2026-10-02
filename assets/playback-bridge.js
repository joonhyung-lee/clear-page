/* Native timeline remains authoritative, including seeks and pauses. */
window.CLEAR_PLAYBACK_BRIDGE=function(){
 let previous='',command=null,afterSeek=null;
 let viewer=null,sideApplied=false;
 let chasedPosition=null,chaseResetBound=false;
 function followBody(){
  if(!window.__CLEAR_BODY_CHASE__)return;
  if(!viewer){
   const root=document.querySelector('#root'),key=root&&Object.keys(root).find(k=>k.startsWith('__reactContainer'));
   const queue=key?[root[key],root[key]?.stateNode?.current]:[],seen=new Set();
   while(queue.length){const f=queue.pop();if(!f||seen.has(f))continue;seen.add(f);const v=f.memoizedProps?.value;
    if(v?.mutable?.current?.cameraControl&&v?.useSceneTree){viewer=v;break;}queue.push(f.child,f.sibling,f.alternate);
   }
  }
  const m=viewer?.mutable.current,node=m?.nodeRefFromName['/body-1'],q=viewer?.useSceneTree.get('')?.wxyz;
  if(node&&q){
   if(!chaseResetBound){
    // Home/double-click reset relative to the current body, rather than the
    // archive's original fixed world camera at the beginning of the run.
    m.resetCameraPose=()=>{chasedPosition=null;};chaseResetBound=true;
   }
   node.updateWorldMatrix(true,false);
   const rotation=m.camera.quaternion.clone().set(q[1],q[2],q[3],q[0]);
   const up=m.camera.position.clone().set(0,0,1).applyQuaternion(rotation);
   const base=node.getWorldPosition(m.camera.position.clone());base.addScaledVector(up,-base.dot(up));
   let eye,at;
   if(!chasedPosition){
    eye=base.clone().add(m.camera.position.clone().set(-2.6,-1.8,2.4).applyQuaternion(rotation));
    at=base.clone().add(m.camera.position.clone().set(.6,0,.7).applyQuaternion(rotation));
    m.camera.up.copy(up);m.cameraControl.updateCameraUp();m.camera.fov=.85*180/Math.PI;m.camera.updateProjectionMatrix();
   }else{
    const delta=base.clone().sub(chasedPosition);
    eye=m.cameraControl.getPosition(m.camera.position.clone()).add(delta);
    at=m.cameraControl.getTarget(m.camera.position.clone()).add(delta);
   }
   m.cameraControl.setLookAt(...eye.toArray(),...at.toArray(),false);chasedPosition=base;
  }
  requestAnimationFrame(followBody);
 }
 if(window.__CLEAR_BODY_CHASE__)requestAnimationFrame(followBody);
 function setContactCamera(){
  if(!window.__CLEAR_CONTACT_SIDE__||sideApplied)return;
  const root=document.querySelector('#root'),key=root&&Object.keys(root).find(k=>k.startsWith('__reactContainer'));
  if(!key)return;
  const queue=[root[key],root[key]?.stateNode?.current],seen=new Set();
  while(queue.length){const f=queue.pop();if(!f||seen.has(f))continue;seen.add(f);const v=f.memoizedProps?.value;
   if(v?.mutable?.current?.cameraControl&&v?.useSceneTree?.get('')?.wxyz){
    const m=v.mutable.current,q=v.useSceneTree.get('').wxyz,r=m.camera.quaternion.clone().set(q[1],q[2],q[3],q[0]);
    const eye=m.camera.position.clone().set(2.6,-1.8,1.5).applyQuaternion(r),at=m.camera.position.clone().set(0,.5,.7).applyQuaternion(r);
    m.cameraControl.setLookAt(...eye.toArray(),...at.toArray(),false);sideApplied=true;return;
   }queue.push(f.child,f.sibling,f.alternate);
  }
 }

 function compactCheckpointUpdates(){
  if(!window.__CLEAR_CHECKPOINT_REPLAY__)return;
  if(!viewer){
   const root=document.querySelector('#root'),key=root&&Object.keys(root).find(k=>k.startsWith('__reactContainer'));
   if(!key)return;const pending=[root[key],root[key]?.stateNode?.current],seen=new Set();
   while(pending.length){const f=pending.pop();if(!f||seen.has(f))continue;seen.add(f);const v=f.memoizedProps?.value;if(v?.mutable?.current?.messageQueue){viewer=v;break;}pending.push(f.child,f.sibling,f.alternate);}
  }
  const queue=viewer?.mutable.current.messageQueue;if(!Array.isArray(queue))return;
  // Checkpoint scenes have fixed geometry. Each rendered frame needs only the
  // latest pose of each batch, including when normal playback falls behind.
  const keep=[],poses=new Map();
  for(const message of queue){
   if(message.type==='SceneNodeUpdateMessage'&&message.name.startsWith('/agents/')){
    const previous=poses.get(message.name);poses.set(message.name,{...message,updates:{...previous?.updates,...message.updates}});
   }else{
    // A backward seek recreates the initial batches. Poses queued before that
    // reset belong to the old playhead and must not overwrite the initial pose.
    if(message.type==='BatchedMeshesMessage')poses.delete(message.name);
    keep.push(message);
   }
  }
  queue.splice(0,queue.length,...keep,...poses.values());
 }
 if(window.__CLEAR_EXTERNAL_TIMELINE__){const style=document.createElement('style');style.textContent='.mantine-Paper-root:has([role=slider]){display:none!important}';document.head.append(style);}
 function seek(time){
  const el=document.querySelector('[role=slider]');if(!el)return false;
  let f=el[Object.keys(el).find(k=>k.startsWith('__reactFiber'))];
  while(f){const p=f.memoizedProps;if(p&&p.step===.0001&&typeof p.onChange==='function'){p.onChange(time);compactCheckpointUpdates();return true;}f=f.return;}return false;
 }
 function preciseTime(input){
  const el=document.querySelector('[role=slider]');
  let f=el?.[Object.keys(el).find(k=>k.startsWith('__reactFiber'))];
  while(f){const p=f.memoizedProps;if(p?.step===.0001&&typeof p.value==='number')return p.value;f=f.return;}
  return Number(input.value);
 }
 window.addEventListener('message',e=>{if(e.source!==parent)return;if(e.data?.type==='clear-playback-command')command=e.data;else if(e.data?.type==='clear-contact-camera'){sideApplied=false;setContactCamera();}});
 const interval=setInterval(()=>{
  setContactCamera();compactCheckpointUpdates();
  const input=document.querySelector('input'),button=document.querySelector('[class*="tabler-icon-player-play"],[class*="tabler-icon-player-pause"]')?.closest('button');if(!input||!button)return;
  let playing=!!button.querySelector('.tabler-icon-player-pause-filled');
  if(command){
   const next=command;command=null;afterSeek=null;
   // Native seeking also pauses playback. Wait for that React state update
   // before restoring the requested play state, including play-to-play seeks.
   if(Number.isFinite(next.time)&&seek(Math.max(0,next.time))){afterSeek=typeof next.playing==='boolean'?next.playing:null;return;}
   if(typeof next.playing==='boolean'&&playing!==next.playing)button.click();
  }else if(afterSeek!==null&&!playing){if(afterSeek)button.click();afterSeek=null;}
  const time=preciseTime(input);if(!Number.isFinite(time))return;
  const key=time+'|'+playing;if(key===previous)return;previous=key;
  parent.postMessage({type:'clear-playback-time',time,playing},'*');
 },50);
 window.addEventListener('pagehide',()=>clearInterval(interval),{once:true});
};
