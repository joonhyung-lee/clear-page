/* Native timeline remains authoritative, including seeks and pauses. */
window.CLEAR_PLAYBACK_BRIDGE=function(){
 let previous='',command=null;
 function seek(time){
  const el=document.querySelector('[role=slider]');if(!el)return false;
  let f=el[Object.keys(el).find(k=>k.startsWith('__reactFiber'))];
  while(f){const p=f.memoizedProps;if(p&&p.step===.0001&&typeof p.onChange==='function'){p.onChange(time);return true;}f=f.return;}return false;
 }
 window.addEventListener('message',e=>{if(e.source===parent&&e.data?.type==='clear-playback-command')command=e.data;});
 const interval=setInterval(()=>{
  const input=document.querySelector('input'),button=document.querySelector('button');if(!input||!button)return;
  let playing=!!button.querySelector('.tabler-icon-player-pause-filled');
  if(command){if(Number.isFinite(command.time))seek(Math.max(0,command.time));if(typeof command.playing==='boolean'&&playing!==command.playing)button.click();command=null;}
  const time=Number(input.value);if(!Number.isFinite(time))return;
  const key=time+'|'+playing;if(key===previous)return;previous=key;
  parent.postMessage({type:'clear-playback-time',time,playing},'*');
 },50);
 window.addEventListener('pagehide',()=>clearInterval(interval),{once:true});
};
