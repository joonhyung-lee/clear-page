/* Native timeline remains authoritative, including seeks and pauses. */
window.CLEAR_PLAYBACK_BRIDGE=function(){
 let previous='',command=null,afterSeek=null;
 let viewer=null;
 function compactCheckpointSeek(){
  if(!window.__CLEAR_CHECKPOINT_REPLAY__)return;
  if(!viewer){
   const root=document.querySelector('#root'),key=root&&Object.keys(root).find(k=>k.startsWith('__reactContainer'));
   if(!key)return;const pending=[root[key],root[key]?.stateNode?.current],seen=new Set();
   while(pending.length){const f=pending.pop();if(!f||seen.has(f))continue;seen.add(f);const v=f.memoizedProps?.value;if(v?.mutable?.current?.messageQueue){viewer=v;break;}pending.push(f.child,f.sibling,f.alternate);}
  }
  const queue=viewer?.mutable.current.messageQueue;if(!Array.isArray(queue))return;
  // Historical checkpoint scenes have fixed geometry. A seek needs only the
  // final pose of each agent batch, not thousands of superseded pose updates.
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
  while(f){const p=f.memoizedProps;if(p&&p.step===.0001&&typeof p.onChange==='function'){p.onChange(time);compactCheckpointSeek();return true;}f=f.return;}return false;
 }
 window.addEventListener('message',e=>{if(e.source===parent&&e.data?.type==='clear-playback-command')command=e.data;});
 const interval=setInterval(()=>{
  const input=document.querySelector('input'),button=document.querySelector('[class*="tabler-icon-player-play"],[class*="tabler-icon-player-pause"]')?.closest('button');if(!input||!button)return;
  let playing=!!button.querySelector('.tabler-icon-player-pause-filled');
  if(command){
   const next=command;command=null;afterSeek=null;
   // Native seeking also pauses playback. Wait for that React state update
   // before restoring the requested play state, including play-to-play seeks.
   if(Number.isFinite(next.time)&&seek(Math.max(0,next.time))){afterSeek=typeof next.playing==='boolean'?next.playing:null;return;}
   if(typeof next.playing==='boolean'&&playing!==next.playing)button.click();
  }else if(afterSeek!==null&&!playing){if(afterSeek)button.click();afterSeek=null;}
  const time=Number(input.value);if(!Number.isFinite(time))return;
  const key=time+'|'+playing;if(key===previous)return;previous=key;
  parent.postMessage({type:'clear-playback-time',time,playing},'*');
 },50);
 window.addEventListener('pagehide',()=>clearInterval(interval),{once:true});
};
