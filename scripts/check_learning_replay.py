"""Verify rendered checkpoint poses, native seeks, playback and camera control."""
import asyncio,json,tempfile,traceback
from pathlib import Path
import numpy as np
from PIL import Image
from recording_io import read_recording
ROOT=Path(__file__).resolve().parents[1]
def recording(body):
 text=(ROOT/f'assets/recordings/learning-{body}.hex.js').read_text()
 with tempfile.NamedTemporaryFile(suffix='.viser') as temporary:
  temporary.write(bytes.fromhex(json.loads(text.rsplit(' = ',1)[1].rstrip(';\n'))));temporary.flush()
  return read_recording(temporary.name)
def positions_at(record,buffers,time):
 reference=None
 for t,message in record['messages']:
  if t>time:break
  if message.get('name')!='/agents/2':continue
  props=message.get('props',message.get('updates',{}))
  reference=props.get('batched_positions',reference)
 return np.frombuffer(buffers[reference['__binary_index']],dtype='<f4').tolist()
def visible_terrain_colors(path):
 """Require distinguishable pastel hues in the actual native screenshot.

 Message RGB values alone do not detect washed-out lighting. A substantial
 colored area excludes small playback icons and colored stair edges. The
 camera can contain only one terrain category, so do not require all hues.
 """
 from style_learning_checkpoints import TERRAIN_COLORS
 pixels=np.asarray(Image.open(path).convert('RGB'),dtype=float)
 # Remove the top preview button and bottom transport overlay.
 pixels=pixels[int(len(pixels)*.1):int(len(pixels)*.85)].reshape(-1,3)
 total=len(pixels)
 pixels=pixels[(pixels.max(1)-pixels.min(1)>=12)&(pixels.mean(1)>140)]
 names=[name for name in TERRAIN_COLORS if name!='border']
 palette=np.array([TERRAIN_COLORS[name] for name in names],dtype=float)
 def chroma(v):
  v=v-v.mean(1,keepdims=True)
  return v/np.maximum(np.linalg.norm(v,axis=1,keepdims=True),1e-8)
 score=chroma(pixels)@chroma(palette).T
 nearest=score.argmax(1) if len(score) else np.empty(0,dtype=int)
 count={name:int(np.count_nonzero((nearest==i)&(score[:,i]>.96))) for i,name in enumerate(names)}
 assert sum(count.values())>=.12*total, f'Terrain is visually washed out or absent: {count}, colored fraction {sum(count.values())/total:.3f}'
 return count
from playwright.async_api import async_playwright
from browser_diagnostics import browser_diagnostics
PLAYING_AFTER_SEEK = r'''() => {
 const time=Number(document.querySelector('input').value);
 return time>16.1 && time<18 && !!document.querySelector('.tabler-icon-player-pause-filled');
}'''
from check_learning_replay_support import FIND
async def main():
 async with async_playwright() as p:
  # Match the GPU-capable configuration used by the other native Viser checks.
  b=await p.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist'])
  failures=[]
  for body,steps in [('g1',[0,5000,17000,22800]),('spot_arm',[13200,18000,22600,28000])]:
   print('PROGRESS',body,'loading native scene',flush=True)
   record,buffers=recording(body)
   page=await b.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   try:
    async with browser_diagnostics(page, 'learning-'+body):
     await page.goto('http://localhost:8765/#controller-pretraining',wait_until='domcontentloaded')
     if body!='g1':await page.locator(f'[data-loco-body="{body}"]').click()
     await page.locator('[data-loco-source="recorded"]').click()
     v=page.locator(f'[data-loco-viewer="{body}"]');await v.locator('.launch').click();await v.locator('iframe.scene-ready').wait_for(timeout=90000)
     f=await (await v.locator('iframe').element_handle()).content_frame();await f.evaluate(FIND)
     # Inspect a stationary scene. Playback is exercised separately below.
     await v.evaluate("v=>v.querySelector('iframe').contentWindow.postMessage({type:'clear-playback-command',playing:false},'*')")
     await f.locator('.tabler-icon-player-play-filled').wait_for(state='attached',timeout=15000)
     await f.wait_for_function('()=>testViewer.mutable.current.messageQueue.length===0',timeout=15000)
     nodes=await f.evaluate("()=>Object.values(testViewer.useSceneTree.getAll()).filter(n=>n.message?.type==='BatchedMeshesMessage').map(n=>({name:n.message.name,positions:n.message.props.batched_positions.length}))")
     assert len(nodes)==(34 if body=='g1' else 30) and all(n['positions']==96 for n in nodes),nodes
     await f.wait_for_function("""()=>Object.keys(testViewer.useSceneTree.getAll()).filter(name=>name.startsWith('/agents/')).every(name=>{
      const node=testViewer.mutable.current.nodeRefFromName[name];let ready=false;
      node?.traverse(o=>{if(o.geometry&&o.material)ready=true;});return ready;
     })""",timeout=30000)
     materials=await f.evaluate("""()=>Object.entries(testViewer.mutable.current.nodeRefFromName).filter(([name])=>name.startsWith('/agents/')).flatMap(([name,node])=>{
      const result=[];node.traverse(o=>{if(o.geometry&&o.material){for(const m of [o.material].flat())result.push({name,opacity:m.opacity,transparent:m.transparent,side:m.side,depthWrite:m.depthWrite,faces:o.geometry.index.count/3});}});return result;
     })""")
     assert len(materials)==len(nodes),materials
     assert all(m['opacity']==1 and not m['transparent'] and m['side']==2 and m['depthWrite'] for m in materials),materials
     assert sum(m['faces'] for m in materials)==(393270 if body=='g1' else 162762),materials
     print('PROGRESS',body,'full meshes verified; checking four checkpoint seeks',flush=True)
     for i,step in enumerate(steps):
      await page.locator('[data-loco-stage="'+str(i)+'"]').click();await f.wait_for_function('(time)=>Math.abs(Number(document.querySelector("input").value)-time)<.06',arg=i*8,timeout=5000)
      expected=positions_at(record,buffers,i*8+.001)
      await f.wait_for_function('(expected)=>{const p=testViewer.useSceneTree.getAll()["/agents/2"].message.props.batched_positions;return expected.every((v,i)=>Math.abs(v-p[i])<1e-5)}',arg=expected,timeout=15000)
      assert await page.locator('#controller-pretraining').get_attribute('data-checkpoint')==str(step)
      print('PROGRESS',body,'checkpoint',step,'verified',flush=True)
     print('PROGRESS',body,'checking playback and viewport pause/resume',flush=True)
     await v.evaluate("v=>v.querySelector('iframe').contentWindow.postMessage({type:'clear-playback-command',time:16,playing:true},'*')")
     # The preceding checkpoint is at 24 s. A one-sided >16.1 predicate can
     # succeed on that stale value before this asynchronous seek even starts.
     await f.wait_for_function(PLAYING_AFTER_SEEK,timeout=15000)
     await page.evaluate('scrollTo(0,0)')
     await f.locator('.tabler-icon-player-play-filled').wait_for(state='attached',timeout=10000)
     paused=float(await f.locator('input').first.input_value())
     await page.wait_for_timeout(600)
     after_pause=float(await f.locator('input').first.input_value())
     assert after_pause==paused, f'{body}: offscreen playhead changed from {paused} to {after_pause}'
     await v.scroll_into_view_if_needed();await f.wait_for_function('(time)=>Number(document.querySelector("input").value)>time',arg=paused,timeout=15000)
     # Native camera controls must remain interactive after seeking.
     await v.evaluate("v=>v.querySelector('iframe').contentWindow.postMessage({type:'clear-playback-command',playing:false},'*')")
     await f.locator('.tabler-icon-player-play-filled').wait_for(state='attached')
     print('PROGRESS',body,'checking camera interaction',flush=True)
     initial=await f.evaluate('()=>testViewer.mutable.current.camera.position.toArray()')
     box=await v.bounding_box();await page.mouse.move(box['x']+box['width']*.6,box['y']+box['height']*.6);await page.mouse.wheel(0,-220)
     await f.wait_for_function('(initial)=>testViewer.mutable.current.camera.position.toArray().some((v,i)=>Math.abs(v-initial[i])>.1)',arg=initial)
     print('PROGRESS',body,'functional checks complete; capturing rendered scene',flush=True)
     screenshot=f'/tmp/learning-mesh-{body}.png'
     await v.screenshot(path=screenshot)
     colors=visible_terrain_colors(screenshot)
     print('PROGRESS',body,'visible native terrain colors',json.dumps(colors),flush=True)
     assert not errors,errors
     print('PASS',body,'complete opaque native meshes, 32 agents, all checkpoint seeks, actual motion, viewport pause/resume and camera zoom',flush=True)
   except Exception as error:
    failures.append(body+': '+type(error).__name__+' '+next(iter(str(error).splitlines()),''))
    print('FAIL',failures[-1],flush=True)
    traceback.print_exc()
   finally:
    await page.close()
  await b.close()
  assert not failures, '\n'.join(failures)
asyncio.run(main())
# Bare Spot owns a separate random-initialized policy and native geometry.
from check_spot_curriculum import main as check_bare_replay
asyncio.run(check_bare_replay())
