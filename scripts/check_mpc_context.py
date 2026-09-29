"""Check measured continuation, native robot overlay, and shared replay controls."""
import asyncio,json,io,numpy as np
from PIL import Image
from pathlib import Path
from playwright.async_api import async_playwright
from check_research_visuals import FIND
from recording_io import read_recording
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist']);page=await b.new_page(viewport={'width':1600,'height':1100},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765',wait_until='domcontentloaded');root=page.locator('#mpc-process');await root.scroll_into_view_if_needed();await root.locator('.mpc-process-content').wait_for();await root.locator('#mpc-full-rollout').check()
  slider=root.locator('#mpc-process-update');await slider.evaluate('e=>{e.value=.625;e.dispatchEvent(new Event("input"))}')
  ours=root.locator('[data-process=optimized]');assert await ours.locator('canvas').get_attribute('data-observed-until')=='25';assert await ours.locator('canvas').get_attribute('data-forecast-valid')=='false'
  await root.locator('#mpc-robot-context').click();frames=[]
  for name in ['optimized','baseline']:
   viewer=root.locator('[data-scene=mpc-context-'+name+']');await viewer.locator('iframe.scene-ready').wait_for(timeout=90000);frame=await (await viewer.locator('iframe').element_handle()).content_frame();assert await frame.evaluate(FIND);frames.append(frame)
   await frame.wait_for_function('Math.abs(Number(document.querySelector("input").value)-25)<.12')
   props=await frame.evaluate(r'()=>Object.entries(testViewer.useSceneTree.getAll()).filter(([n,v])=>n.match(/body-1\/geom/) && v.message?.props).map(([n,v])=>v.message.props.opacity)');assert props and all(p==.16 for p in props),props
   assert await frame.evaluate('!!testViewer.useSceneTree.get("/tracking/skeleton")');assert await frame.evaluate('!!testViewer.useSceneTree.get("/tracking/current-palms")')
  for name,frame in zip(['optimized','baseline'],frames):
   record,buffers=read_recording(Path(__file__).resolve().parents[1]/f'assets/recordings/mpc-context-{name}.viser');message=[m for t,m in record['messages'] if t<=25 and m.get('name')=='/tracking/skeleton'][-1];payload=message.get('updates',message.get('props'))['points'];expected=np.frombuffer(buffers[payload['__binary_index']],dtype=payload['dtype']);actual=await frame.evaluate('()=>Array.from(testViewer.useSceneTree.get("/tracking/skeleton").message.props.points)');assert np.allclose(actual,expected,atol=1e-6),name
  await root.screenshot(path='/tmp/mpc-context-25.png');srcs=await root.locator('iframe').evaluate_all('es=>es.map(e=>e.srcdoc)')
  async def dark_pixels(frame):
   rgb=np.asarray(Image.open(io.BytesIO(await frame.locator('canvas').last.screenshot())))[:,:,:3];return int((rgb.max(axis=2)<150).sum())
  before_dark=[await dark_pixels(frame) for frame in frames]
  await root.locator('#mpc-robot-context').click();assert await ours.locator('canvas').is_visible();await root.locator('#mpc-robot-context').click();assert await root.locator('iframe').evaluate_all('es=>es.map(e=>e.srcdoc)')==srcs
  await page.wait_for_timeout(250)
  after_dark=[await dark_pixels(frame) for frame in frames];assert all(a>150 and a>b*.6 for a,b in zip(after_dark,before_dark)),(before_dark,after_dark)
  for t in [5,14,30,40]:
   await slider.evaluate('(e,t)=>{e.value=t/40;e.dispatchEvent(new Event("input"))}',t)
   print('Seeking',t,flush=True)
   for frame in frames:
    try:await frame.wait_for_function('(t)=>Math.abs(Number(document.querySelector("input").value)-t)<.12',arg=t,timeout=6000)
    except Exception:
     print('Native seek mismatch',t,await frame.locator('input').first.input_value(),await frame.locator('button').first.inner_html(),flush=True);raise
   if t==5:
    await page.wait_for_timeout(250);assert all(count>150 for count in [await dark_pixels(frame) for frame in frames])
    await root.screenshot(path='/tmp/mpc-context-5.png')
  await root.locator('[data-mpc-view="2d"]').click();assert await ours.locator('canvas').is_visible();assert await root.locator('#mpc-robot-context').get_attribute('aria-pressed')=='false';assert await root.get_attribute('data-elapsed')=='40.000'
  await page.locator('.mpc-objective').screenshot(path='/tmp/objective-wide.png');await page.locator('.mpc-scenes-grid').screenshot(path='/tmp/comparison-wide.png')
  width=await page.locator('#method-execution').evaluate('e=>e.getBoundingClientRect().width/innerWidth');assert .84<width<.86,width
  assert not errors,errors;await b.close();print('PASS 40 s measured continuation, translucent native meshes and skeleton, synchronized seek, persistent overlay, 85% layout')
asyncio.run(main())
