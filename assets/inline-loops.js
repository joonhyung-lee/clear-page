/* Visible previews loop locally; only two new video loads start at a time. */
(() => {
  const states=new Map(), queue=[];
  const assets=new Map();
  let loading=0, scheduled=false;
  function asset(path){
    const key=path.split('?')[0];
    if(!assets.has(key)){
      const request=(async()=>{
        if(window.origin==='null'||location.protocol==='file:'){
          const script=key.replace('assets/media/','assets/loop-videos/').replace(/\.mp4$/,'.js');
          await loadScript(script,()=>!!window.CLEAR_VIDEO_LOOPS?.[key]);
          return window.CLEAR_VIDEO_LOOPS[key];
        }
        const response=await fetch(clearAssetURL(key),{cache:'force-cache'});
        if(!response.ok)throw new Error(`Video unavailable (${response.status})`);
        return URL.createObjectURL(await response.blob());
      })();
      assets.set(key,request);
      request.catch(()=>{if(assets.get(key)===request)assets.delete(key);});
    }
    return assets.get(key);
  }
  const visible=state=>state.visible&&!document.hidden&&!state.video.hidden&&state.video.getClientRects().length>0;
  function pause(state){
    state.wantPlay=false;
    if(!state.video.paused){state.programmaticPauses++;state.video.pause();}
  }
  function play(state){
    if(!visible(state)||reduced.matches||state.userPaused)return;
    if(!state.video.paused)return;
    state.wantPlay=true;
    state.video.play().catch(()=>{state.wantPlay=false;state.video.controls=true;});
  }
  function sync(state){
    if(!visible(state)||reduced.matches){pause(state);return;}
    if(state.error||state.userPaused)return;
    if(state.ready){play(state);return;}
    if(!state.loading&&!state.queued){state.queued=true;queue.push(state);}
    drain();
  }
  function failed(state){
    state.error=true;state.ready=false;pause(state);
    state.video.controls=true;
    if(state.retry||state.video.closest('.media-tile'))return;
    const retry=document.createElement('button');retry.type='button';retry.className='media-retry';retry.textContent='Retry video';
    retry.onclick=()=>{retry.remove();state.retry=null;state.error=false;state.userPaused=false;sync(state);};
    state.retry=retry;state.video.after(retry);
  }
  function drain(){
    while(loading<2&&queue.length){
      const state=queue.shift();state.queued=false;
      if(!visible(state)||reduced.matches||state.ready||state.loading||state.error||state.userPaused)continue;
      const video=state.video,source=video.querySelector('source');
      const path=video.dataset.loopSource||source?.dataset.src||source?.getAttribute('src');
      if(!path)continue;
      state.loading=true;loading++;
      let timer,done=false;
      const finish=()=>{
        if(done)return;done=true;clearTimeout(timer);
        video.removeEventListener('loadeddata',ready);video.removeEventListener('error',error);
        video.removeEventListener('progress',buffered);video.removeEventListener('suspend',idle);
        state.loading=false;state.cancelLoad=null;loading--;
      };
      const buffered=()=>{
        if(state.ready&&Number.isFinite(video.duration)&&video.buffered.length&&video.buffered.end(video.buffered.length-1)>=video.duration-.05){finish();drain();}
      };
      const idle=()=>{if(state.ready){finish();drain();}};
      const ready=()=>{state.ready=true;play(state);buffered();};
      const error=()=>{finish();failed(state);drain();};
      state.cancelLoad=finish;
      video.addEventListener('loadeddata',ready);video.addEventListener('error',error);
      video.addEventListener('progress',buffered);video.addEventListener('suspend',idle);
      timer=setTimeout(()=>{if(state.ready){finish();drain();}else error();},30000);
      asset(path).then(url=>{
        if(done)return;
        video.preload='auto';
        if(source){source.src=url;source.removeAttribute('data-src');}
        else video.src=url;
        video.load();
      },error);
    }
  }
  const observer=new IntersectionObserver(entries=>{
    for(const entry of entries){const state=states.get(entry.target);state.visible=entry.isIntersecting;sync(state);}
  },{threshold:.05});
  function prepare(video){
    if(states.has(video))return;
    video.muted=true;video.defaultMuted=true;video.loop=true;video.playsInline=true;video.preload='none';
    const state={video,visible:false,ready:false,loading:false,queued:false,userPaused:false,wantPlay:false,error:false,programmaticPauses:0};
    states.set(video,state);observer.observe(video);
    video.addEventListener('pause',()=>{
      if(state.programmaticPauses){state.programmaticPauses--;return;}
      if(video.paused&&state.wantPlay&&visible(state)&&video.readyState>0)state.userPaused=true;
    });
    video.addEventListener('play',()=>{state.userPaused=false;state.error=false;state.retry?.remove();state.retry=null;});
    video.addEventListener('error',()=>{if(!state.loading)failed(state);});
  }
  function refresh(){
    if(scheduled)return;scheduled=true;
    requestAnimationFrame(()=>{scheduled=false;for(const state of states.values())sync(state);});
  }
  function resume(video,time=0){
    prepare(video);const state=states.get(video);state.userPaused=false;
    const seek=()=>{if(Number.isFinite(video.duration)&&video.duration>0)video.currentTime=time%video.duration;};
    if(video.readyState)seek();else video.addEventListener('loadedmetadata',seek,{once:true});
    sync(state);
  }
  document.querySelectorAll('video[data-inline-loop]').forEach(prepare);
  new MutationObserver(records=>{
    for(const record of records)for(const node of record.addedNodes){
      if(node.nodeType!==1)continue;
      if(node.matches('video[data-inline-loop]'))prepare(node);
      node.querySelectorAll('video[data-inline-loop]').forEach(prepare);
    }
    refresh();
  }).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden']});
  document.addEventListener('visibilitychange',refresh);
  reduced.addEventListener('change',refresh);
  document.addEventListener('scene-settled',refresh,true);
  window.CLEAR_INLINE_LOOPS={prepare,resume,refresh};
})();
