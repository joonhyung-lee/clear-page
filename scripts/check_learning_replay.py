"""Verify rendered checkpoint poses, native seeks, playback and camera control."""
import asyncio,json,tempfile
from pathlib import Path
import numpy as np
from recording_io import read_recording
ROOT=Path(__file__).resolve().parents[1]
text=(ROOT/'assets/recordings/learning-g1.hex.js').read_text()
with tempfile.NamedTemporaryFile(suffix='.viser') as temporary:
 temporary.write(bytes.fromhex(json.loads(text.rsplit(' = ',1)[1].rstrip(';\n'))));temporary.flush()
 record,buffers=read_recording(temporary.name)
def positions_at(time):
 reference=None
 for t,message in record['messages']:
  if t>time:break
  if message.get('name')!='/agents/2':continue
  props=message.get('props',message.get('updates',{}))
  reference=props.get('batched_positions',reference)
 return np.frombuffer(buffers[reference['__binary_index']],dtype='<f4').tolist()
from playwright.async_api import async_playwright
FIND='''() => {const r=document.querySelector('#root'),key=Object.keys(r).find(k=>k.startsWith('__reactContainer')),queue=[r[key],r[key]?.stateNode?.current],seen=new Set();while(queue.length){const f=queue.pop();if(!f||seen.has(f))continue;seen.add(f);const v=f.memoizedProps?.value;if(v?.useSceneTree?.getAll){window.testViewer=v;return Object.keys(v);}queue.push(f.child,f.sibling,f.alternate);}return [];}'''
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765/#controller-pretraining',wait_until='domcontentloaded')
  v=page.locator('[data-loco-viewer=g1]');await v.locator('.launch').click();await v.locator('iframe.scene-ready').wait_for(timeout=90000)
  f=await (await v.locator('iframe').element_handle()).content_frame();await f.evaluate(FIND)
  nodes=await f.evaluate("()=>Object.values(testViewer.useSceneTree.getAll()).filter(n=>n.message?.type==='BatchedMeshesMessage').map(n=>({name:n.message.name,positions:n.message.props.batched_positions.length}))")
  assert len(nodes)==34 and all(n['positions']==96 for n in nodes),nodes
  for i,step in enumerate([0,5000,17000,22800]):
   await page.locator('[data-loco-stage="'+str(i)+'"]').click();await f.wait_for_function('(time)=>Math.abs(Number(document.querySelector("input").value)-time)<.06',arg=i*8,timeout=5000)
   expected=positions_at(i*8+.001)
   await f.wait_for_function('(expected)=>{const p=testViewer.useSceneTree.getAll()["/agents/2"].message.props.batched_positions;return expected.every((v,i)=>Math.abs(v-p[i])<1e-5)}',arg=expected,timeout=15000)
   assert await page.locator('#controller-pretraining').get_attribute('data-checkpoint')==str(step)
  await v.evaluate("v=>v.querySelector('iframe').contentWindow.postMessage({type:'clear-playback-command',time:16,playing:true},'*')")
  await f.wait_for_function('()=>Number(document.querySelector("input").value)>16.1',timeout=15000)
  await page.evaluate('scrollTo(0,0)');await f.locator('.tabler-icon-player-play-filled').wait_for(state='attached',timeout=10000);paused=float(await f.locator('input').first.input_value());await page.wait_for_timeout(600);assert float(await f.locator('input').first.input_value())==paused
  await v.scroll_into_view_if_needed();await f.wait_for_function('(time)=>Number(document.querySelector("input").value)>time',arg=paused,timeout=15000)
  # Native camera controls must remain interactive after seeking.
  await v.evaluate("v=>v.querySelector('iframe').contentWindow.postMessage({type:'clear-playback-command',playing:false},'*')")
  await f.locator('.tabler-icon-player-play-filled').wait_for(state='attached')
  initial=await f.evaluate('()=>testViewer.mutable.current.camera.position.toArray()')
  box=await v.bounding_box();await page.mouse.move(box['x']+box['width']*.6,box['y']+box['height']*.6);await page.mouse.wheel(0,-220)
  await f.wait_for_function('(initial)=>testViewer.mutable.current.camera.position.toArray().some((v,i)=>Math.abs(v-initial[i])>.1)',arg=initial)
  print('PASS native batched meshes, 32 agents, all checkpoint seeks, actual motion, viewport pause/resume and camera zoom',errors,flush=True);assert not errors
  await b.close()
asyncio.run(main())
