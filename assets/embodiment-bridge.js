/* Bridge for the pinned, vendored Viser runtime. Changes display props only. */
window.CLEAR_EMBODIMENT_BRIDGE = function () {
  const config=window.__CLEAR_EMBODIMENT__;
  if(!config)return;
  const style=document.createElement('style');
  style.textContent='.mantine-Paper-root:has([role=slider]){opacity:0;transition:opacity .15s}body:hover .mantine-Paper-root:has([role=slider]),.mantine-Paper-root:has([role=slider]):focus-within{opacity:1}';
  document.head.append(style);
  let viewer=null,mode=config.mode||'structure';
  const originals=new Map();
  function findViewer(){
    const root=document.querySelector('#root');if(!root)return null;
    const key=Object.keys(root).find(k=>k.startsWith('__reactContainer'));if(!key)return null;
    const first=root[key],queue=[first,first?.stateNode?.current],seen=new Set();
    while(queue.length){const f=queue.pop();if(!f||seen.has(f))continue;seen.add(f);const v=f.memoizedProps?.value;if(v?.sceneTreeActions&&v?.useSceneTree)return v;queue.push(f.child,f.sibling,f.alternate);}
    return null;
  }
  function apply(){
    viewer ||= findViewer();if(!viewer)return;
    const nodes=viewer.useSceneTree.getAll();
    for(const [name,node] of Object.entries(nodes)){
      if(!node?.message)continue;
      if(name.includes('/field/support-')||name.endsWith('/contact-field')){
        const visible=name.includes('/field/support-')?mode==='traversability':mode==='manipulation';
        if(node.visibility!==visible)viewer.sceneTreeActions.updateNodeAttributes(name,{visibility:visible});continue;
      }
      const match=name.match(/\/body-(\d+)\/mesh-\d+$/);if(!match)continue;
      const props=node.message.props;if(!originals.has(name))originals.set(name,{color:props.color,opacity:props.opacity});
      const body=+match[1],robot=config.robot;
      const mobility=robot==='g1'?body>=2&&body<=13:robot==='husky'?body>=2&&body<=5:body>=2&&body<=13;
      const manipulation=robot==='g1'?body>=17:robot==='spot_arm'?body>=14:body===1;
      const selected=mode==='traversability'?mobility:manipulation;
      const desired=mode==='structure'?originals.get(name):{color:selected?[159,198,151]:[163,170,168],opacity:selected?.8:.16};
      if(props.opacity!==desired.opacity||String(props.color)!==String(desired.color))viewer.sceneTreeActions.updateSceneNodeProps(name,desired);
    }
  }
  window.addEventListener('message',event=>{
    if(event.source!==parent||event.data?.type!=='clear-embodiment-mode')return;
    if(!['structure','traversability','manipulation'].includes(event.data.mode))return;
    mode=event.data.mode;apply();
    parent.postMessage({type:'clear-embodiment-mode-applied',mode},'*');
  });
  // Reapply display props when the native recording loops, without changing poses.
  const interval=setInterval(apply,100);
  window.addEventListener('pagehide',()=>clearInterval(interval),{once:true});
};
