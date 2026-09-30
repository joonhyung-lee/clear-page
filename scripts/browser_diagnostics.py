"""Private browser failure artifacts, including iframe state before it is removed."""
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import tempfile
import time

PROBE = r'''(() => {
 if (window === top) return;
 let graphics=null;
 setInterval(() => {
  const root=document.querySelector('#root');
  const key=root && Object.keys(root).find(k=>k.startsWith('__reactContainer'));
  const pending=key?[root[key],root[key]?.stateNode?.current]:[],seen=new Set();
  let viewer=null;
  while(pending.length){
   const f=pending.pop();if(!f||seen.has(f))continue;seen.add(f);
   const v=f.memoizedProps?.value;
   if(v?.useSceneTree?.getAll){viewer=v;break;}
   pending.push(f.child,f.sibling,f.alternate);
  }
  const canvas=document.querySelector('canvas'), mutable=viewer?.mutable?.current;
  if(canvas && !graphics){
   const gl=canvas.getContext('webgl2');
   if(gl){const info=gl.getExtension('WEBGL_debug_renderer_info');graphics={renderer:gl.getParameter(info?info.UNMASKED_RENDERER_WEBGL:gl.RENDERER),vendor:gl.getParameter(info?info.UNMASKED_VENDOR_WEBGL:gl.VENDOR)};}
  }
  const nodes=Object.values(viewer?.useSceneTree?.getAll()||{});
  const groups={agents:[],terrain:[],other:[]};
  for(const node of nodes){
   const name=node.message?.name;if(!name)continue;
   const ref=mutable?.nodeRefFromName?.[name];let meshes=0,vertices=0,visibleMeshes=0;
   ref?.traverse?.(o=>{if(o.geometry?.attributes?.position?.count>0){meshes++;vertices+=o.geometry.attributes.position.count;if(o.visible!==false)visibleMeshes++;}});
   const group=name.startsWith('/agents/')?'agents':name.startsWith('/terrain/')?'terrain':'other';
   if(groups[group].length<100)groups[group].push({name,type:node.message.type,shown:node.effectiveVisibility,ref:!!ref,meshes,vertices,visibleMeshes});
  }
  window.__clearCaptureProbe({age:Math.round(performance.now()),root:!!root,react:!!key,
   viewer:!!viewer,nodes:nodes.length,groups,queue:mutable?.messageQueue?.length,graphics,
   canvas:canvas?{width:canvas.width,height:canvas.height,clientWidth:canvas.clientWidth,clientHeight:canvas.clientHeight}:null,
   time:document.querySelector('input')?.value,
   playing:!!document.querySelector('.tabler-icon-player-pause-filled')}).catch(()=>{});
 },2000);
})();'''


@asynccontextmanager
async def browser_diagnostics(page, label):
    started = time.monotonic()
    events = []
    graphics_reported = False

    def record(kind, value):
        nonlocal graphics_reported
        if kind == 'native' and value.get('graphics') and not graphics_reported:
            graphics_reported = True
            print('PROGRESS',label,'graphics:',value['graphics']['renderer'],flush=True)
        events.append(dict(seconds=round(time.monotonic()-started, 2), kind=kind, value=value))
        if len(events) > 300:
            del events[0]

    await page.expose_binding('__clearCaptureProbe', lambda source, value: record('native', value))
    await page.add_init_script(PROBE)
    page.on('pageerror', lambda error: record('pageerror', str(error)[:3000]))
    page.on('console', lambda message: record('console', dict(type=message.type, text=message.text[:2000]))
            if message.type in ('error', 'warning') else None)
    page.on('requestfailed', lambda request: record('requestfailed', dict(url=request.url[:300], error=request.failure)))
    page.on('response', lambda response: record('response', dict(url=response.url[:300], status=response.status))
            if response.status >= 400 or '/assets/viser/' in response.url or '/assets/recordings/' in response.url else None)
    try:
        yield
    except Exception as error:
        directory = Path(os.environ.get('CLEAR_CHECK_REPORT_DIR') or tempfile.mkdtemp(prefix='clear-browser-failure-'))
        directory.mkdir(parents=True, exist_ok=True)
        try:
            state = await page.locator('.viewer').evaluate_all('''viewers=>viewers.filter(v=>v.querySelector('iframe,.viewer-status')).map(v=>({scene:v.dataset.scene,status:v.querySelector('.viewer-status')?.textContent,iframe:v.querySelector('iframe')?.className,busy:v.getAttribute('aria-busy')}))''')
            record('viewers', state)
            await page.screenshot(path=str(directory/(label+'.png')), timeout=5000)
        except Exception as capture_error:
            record('capture-error', str(capture_error)[:1000])
        output = directory/(label+'.diagnostics.json')
        output.write_text(json.dumps(dict(error=str(error), events=events), indent=2)+'\n')
        print('Browser diagnostics:', output, flush=True)
        raise
