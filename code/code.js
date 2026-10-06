/* Source-level system flow paired with recorded examples. Python is display-only. */
(() => {
  'use strict';
  const catalog=window.CLEAR_CODE_CATALOG, files=new Map((catalog?.files||[]).map(f=>[f.path,f]));
  const cache=new Map(), pending=new Map();
  window.CLEAR_CODE={register(path,value){if(files.has(path)){cache.set(path,value);pending.get(path)?.resolve(value);}}};
  function load(path){
    if(cache.has(path))return Promise.resolve(cache.get(path));
    if(pending.has(path))return pending.get(path).promise;
    const file=files.get(path);if(!file)return Promise.reject(new Error('Source missing'));
    let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});
    const script=document.createElement('script');script.src=file.url;
    const finish=()=>{clearTimeout(timer);pending.delete(path);script.remove();};
    const timer=setTimeout(()=>{finish();reject(new Error('Source timed out'));},15000);
    script.onload=()=>{finish();if(!cache.has(path))reject(new Error('Incomplete source'));};
    script.onerror=()=>{finish();reject(new Error('Source unavailable'));};
    pending.set(path,{promise,resolve});document.head.append(script);return promise;
  }
  function render(code,lines,start=1,end=lines.length){
    const fragment=document.createDocumentFragment();
    for(let n=start;n<=end;n++){
      const row=document.createElement('span');row.className='code-line';
      const number=document.createElement('span');number.className='line-number';number.textContent=n;number.setAttribute('aria-hidden','true');
      const body=document.createElement('span');body.className='line-content';body.innerHTML=lines[n-1];
      row.append(number,body);fragment.append(row);
    }
    code.replaceChildren(fragment);
  }
  const excerptTickets=new WeakMap();
  async function excerpt(card){
    const ticket=(excerptTickets.get(card)||0)+1;excerptTickets.set(card,ticket);
    const guide=catalog?.nodes.find(n=>n.id===card.dataset.node)||catalog?.guides.find(g=>g.id===card.dataset.component),status=card.querySelector('.code-status');
    if(!guide){status.textContent='Source index unavailable. Reload to retry.';return;}
    status.textContent='Loading code…';
    card.querySelector('[data-copy-source]').disabled=true;
    try{
      const data=await load(guide.file);if(excerptTickets.get(card)!==ticket)return;
      const display=data.formatted||data;
      const symbol=display.symbols?.find(s=>s.name===guide.symbol)||guide;
      const full=card.dataset.scope==='file',start=full?1:symbol.start,end=full?display.lines.length:symbol.end;
      render(card.querySelector('code'),display.lines,start,end);
      card.querySelector('[data-copy-source]').disabled=false;
      card.querySelector('.snippet-heading>span').textContent=full?guide.file.split('/').pop():guide.symbol;
      card.querySelector('.snippet-footer').textContent=guide.file.replace(/^runtime\//,'')+` · ${data.formatted?'formatted · ':''}${end-start+1} lines`;
      card.querySelector('pre').scrollTop=0;
      status.textContent='';
    }catch{
      if(excerptTickets.get(card)!==ticket)return;
      status.textContent='Code could not load. ';
      const retry=document.createElement('button');retry.type='button';retry.textContent='Retry';retry.onclick=()=>excerpt(card);status.append(retry);
    }
  }
  const observer=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){observer.unobserve(e.target);excerpt(e.target);}},{rootMargin:'240px'});
  document.querySelectorAll('.snippet').forEach(card=>observer.observe(card));
  const dialog=document.querySelector('#source-dialog');let dialogRequest=0;
  document.querySelectorAll('[data-open-source]').forEach(button=>button.onclick=async()=>{
    const guide=catalog?.nodes.find(n=>n.id===button.closest('.snippet').dataset.node)||catalog?.guides.find(g=>g.id===button.dataset.openSource);if(!guide)return;
    const ticket=++dialogRequest;document.querySelector('#source-title').textContent=guide.file;
    document.querySelector('#full-source').textContent='Loading source…';dialog.showModal();
    try{const data=await load(guide.file);if(ticket===dialogRequest&&dialog.open)render(document.querySelector('#full-source'),(data.formatted||data).lines);}
    catch{if(ticket===dialogRequest)document.querySelector('#full-source').textContent='Source could not load. Close and reopen to retry.';}
  });
  document.querySelector('#source-close').onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>{dialogRequest++;});
  document.querySelectorAll('[data-copy]').forEach(button=>button.onclick=async()=>{
    try{
      const target=document.getElementById(button.dataset.copy);
      const lines=target.querySelectorAll('.line-content');
      const text=lines.length?[...lines].map(line=>line.textContent).join('\n')+'\n':target.textContent;
      if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(text);
      else{const field=document.createElement('textarea');field.value=text;field.style.position='fixed';field.style.opacity='0';document.body.append(field);field.select();const ok=document.execCommand('copy');field.remove();button.focus();if(!ok)throw new Error('Clipboard unavailable');}
      button.textContent='Copied';
    }catch{button.textContent='Select to copy';}
    setTimeout(()=>{button.textContent='Copy';},1800);
  });
  const stages=[...document.querySelectorAll('[data-flow-node]')];
  const panels=[...document.querySelectorAll('section.component')];
  const workspace=document.querySelector('.implementation-workspace');
  const stageSelect=document.querySelector('#pipeline-select');
  let stageIndex=0;
  function selectStage(index,focus=false){
    stageIndex=(index+stages.length)%stages.length;
    const node=catalog.nodes.find(n=>n.id===stages[stageIndex].dataset.flowNode);
    let parent=node;
    for(const panel of panels){
      panel.hidden=panel.id!==node.stage;
      if(panel.hidden)panel.querySelectorAll('video').forEach(video=>video.pause());
    }
    stages.forEach((el,i)=>{
      el.setAttribute('aria-pressed',String(i===stageIndex));
    });
    stageSelect.value=node.id;
    workspace.dataset.activeStage=node.id;
    const panel=document.getElementById(node.stage),card=panel.querySelector('.snippet');
    panel.querySelector('h2').textContent=node.title;
    panel.querySelector('.component-heading p').textContent=node.description;
    const trail=[];parent=node;
    while(parent){trail.unshift(parent.title);parent=catalog.nodes.find(n=>n.id===parent.parent);}
    const breadcrumb=panel.querySelector('.component-index');
    breadcrumb.textContent=trail.join(' / ');breadcrumb.hidden=trail.length<2;
    card.dataset.node=node.id;card.dataset.scope='symbol';
    const scope=card.querySelector('[data-source-scope]');scope.textContent='View file';scope.setAttribute('aria-pressed','false');
    const related=card.querySelector('.source-relations');related.replaceChildren();
    const neighbors=catalog.nodes.filter(n=>n.id===node.parent||n.parent===node.id);
    for(const neighbor of neighbors){
      const link=document.createElement('button');link.type='button';
      link.textContent=(neighbor.id===node.parent?'↑ ':'↳ ')+neighbor.title;
      link.onclick=()=>selectStage(stages.findIndex(el=>el.dataset.flowNode===neighbor.id));related.append(link);
    }
    excerpt(card);
    if(focus)stages[stageIndex].focus();
  }
  document.querySelectorAll('.snippet').forEach(card=>{
    const scope=document.createElement('button');scope.type='button';scope.dataset.sourceScope='';
    scope.textContent='View file';scope.setAttribute('aria-pressed','false');
    scope.onclick=()=>{const full=card.dataset.scope!=='file';card.dataset.scope=full?'file':'symbol';
      scope.textContent=full?'View symbol':'View file';scope.setAttribute('aria-pressed',String(full));excerpt(card);};
    card.querySelector('.snippet-heading').insertBefore(scope,card.querySelector('[data-open-source]'));
  });
  stages.forEach((node,index)=>{
    node.addEventListener('click',()=>selectStage(index));
    node.addEventListener('keydown',event=>{
      if(['Enter',' ','ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(event.key)){
        event.preventDefault();
        const next=event.key==='Home'?0:event.key==='End'?stages.length-1:
          ['ArrowLeft','ArrowUp'].includes(event.key)?index-1:['ArrowRight','ArrowDown'].includes(event.key)?index+1:index;
        selectStage(next,true);
      }
    });
  });
  const initial=stages.findIndex(el=>'#'+el.dataset.flowNode===location.hash);
  selectStage(initial>=0?initial:0);
  stageSelect.addEventListener('change',()=>selectStage(stages.findIndex(el=>el.dataset.flowNode===stageSelect.value)));
  document.querySelectorAll('[data-workspace-view-button]').forEach(button=>button.addEventListener('click',()=>{
    workspace.dataset.workspaceView=button.dataset.workspaceViewButton;
    document.querySelectorAll('[data-workspace-view-button]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
    if(workspace.dataset.workspaceView==='code')panels.filter(p=>!p.hidden).forEach(p=>p.querySelectorAll('video').forEach(v=>v.pause()));
  }));
  for(const node of document.querySelectorAll('[data-archive]')){
    const item=window.CLEAR_CODE_ARCHIVES?.[node.dataset.archive];if(!item)continue;
    const link=node.closest('a.resource'),key=node.dataset.archive;
    const local=['localhost','127.0.0.1','[::1]'].includes(location.hostname)||location.protocol==='file:';
    const configured=window.CLEAR_CODE_DOWNLOADS?.[key];
    const url=key==='checkpoints'?(configured||(local?item.url:null)):item.url;
    if(url){
      link.href=url+(url.startsWith('../')?'?v='+item.sha256.slice(0,12):'');
      link.removeAttribute('aria-disabled');link.removeAttribute('tabindex');link.referrerPolicy='no-referrer';
    }else{
      link.removeAttribute('href');link.setAttribute('aria-disabled','true');link.tabIndex=-1;
    }
    const size=item.bytes>=1e9?(item.bytes/1e9).toFixed(2)+' GB':Math.round(item.bytes/1e6)+' MB';
    node.textContent=url?'ZIP · '+size+(key==='checkpoints'?' · '+item.files+' models':''):'Download pending · '+item.files+' models';
  }
  function formatBytes(bytes){
    if(bytes<1000)return bytes+' B';
    const unit=bytes>=1e9?1e9:bytes>=1e6?1e6:1e3;
    return (bytes/unit).toFixed(1)+' '+({1000:'KB',1000000:'MB',1000000000:'GB'}[unit]);
  }
  for(const region of document.querySelectorAll('[data-archive-tree]')){
    const archive=window.CLEAR_CODE_ARCHIVES?.[region.dataset.archiveTree];
    if(!archive?.members){region.textContent='Archive contents unavailable. Reload to retry.';continue;}
    const root={children:new Map(),bytes:0,count:0};
    for(const member of archive.members){
      let node=root;const parts=member.path.split('/');
      parts.forEach((name,index)=>{
        node.bytes+=member.bytes;node.count++;
        if(!node.children.has(name))node.children.set(name,{name,children:new Map(),bytes:0,count:0});
        node=node.children.get(name);
        if(index===parts.length-1){node.bytes=member.bytes;node.type=member.type;}
      });
    }
    function branch(parent,depth=0){
      const list=document.createElement('ul');
      const children=[...parent.children.values()].sort((a,b)=>Number(!a.children.size)-Number(!b.children.size)||a.name.localeCompare(b.name));
      for(let entry of children){
        // Collapse directory-only chains while preserving the actual archive path.
        let label=entry.name;
        while(entry.children.size===1){
          const child=[...entry.children.values()][0];
          if(!child.children.size)break;
          label+='/'+child.name;entry=child;
        }
        const li=document.createElement('li'),folder=entry.children.size>0;
        const row=document.createElement(folder?'summary':'div');row.className='archive-row';
        const name=document.createElement('span');name.className='archive-name';name.textContent=label+(folder?'/':'');
        const meta=document.createElement('span');meta.className='archive-meta';meta.textContent=(folder?entry.count+' files · ':entry.type==='symlink'?'link · ':'')+formatBytes(entry.bytes);
        row.append(name,meta);row.title=label+(entry.type==='symlink'?' (symbolic link)':'');
        if(folder){
          const details=document.createElement('details');
          details.open=depth===0;
          details.append(row,branch(entry,depth+1));li.append(details);
        }else li.append(row);
        list.append(li);
      }
      return list;
    }
    region.replaceChildren(branch(root));
  }
})();
