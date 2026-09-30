"""Verify metric map/native alignment, ordered ghosts and a single teaser view."""
import asyncio
from playwright.async_api import async_playwright

FIND='''() => {const r=document.querySelector('#root'),key=Object.keys(r).find(k=>k.startsWith('__reactContainer')),queue=[r[key],r[key]?.stateNode?.current],seen=new Set();while(queue.length){const f=queue.pop();if(!f||seen.has(f))continue;seen.add(f);const v=f.memoizedProps?.value;if(v?.useSceneTree?.getAll){window.testViewer=v;return true;}queue.push(f.child,f.sibling,f.alternate);}return false;}'''

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist'])
  page=await browser.new_page(viewport={'width':1440,'height':1050},reduced_motion='reduce')
  errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
  await page.goto('http://localhost:8765',wait_until='domcontentloaded')
  root=page.locator('#flow-learning');await root.scroll_into_view_if_needed()
  await page.wait_for_function('()=>document.querySelector("#teaser-flow-map")._flowState?.length===3')
  assert await root.locator('.flow-pair canvas').count()==1
  assert await root.locator('.flow-pair .maze-flow-viewer').count()==1
  assert await page.locator('.flow-learning-grid').count()==0
  data=await page.evaluate('window.CLEAR_TEASER_FLOW')
  assert data['scene']['world_size']==[10,17] and len(data['scene']['objects'])==5
  assert data['conditionedOrder']==[0,1,2]
  viewer=root.locator('.maze-flow-viewer');await viewer.locator('.launch').click()
  await viewer.locator('iframe.scene-ready').wait_for(timeout=90000)
  frame=await (await viewer.locator('iframe').element_handle()).content_frame();assert await frame.evaluate(FIND)
  async def seek(t):
   print("PROGRESS paired flow seek",t,flush=True)
   await root.locator('#flow-progress').evaluate('(e,t)=>{e.value=t;e.dispatchEvent(new Event("input",{bubbles:true}));}',t)
   await page.wait_for_function('(t)=>Math.abs(Number(document.querySelector("#teaser-flow-map").dataset.time)-t)<.02',arg=t)
   expected=await root.locator('canvas').evaluate('c=>c._flowState')
   await frame.wait_for_function('''(expected)=>{
    const refs=testViewer.mutable.current.nodeRefFromName;
    return expected.every(path=>path.anchors.every((p,j)=>{const n=refs['/anchor-'+path.object+'-'+j];return n?.visible&&p.every((v,k)=>Math.abs(v-n.position.toArray()[k])<.002);})&&path.ghosts.every((p,j)=>{const n=refs['/ghost-'+path.object+'-'+j];return n?.visible&&p.every((v,k)=>Math.abs(v-n.position.toArray()[k])<.002);}));
   }''',arg=expected,timeout=20000)
   return expected
  for t in [0,1.234,3,6,7.5,10.5,11.111,13.5,16,0]:
   await seek(t)
   if t in (7.5,10.5,13.5): assert await root.get_attribute('data-active-object')==str(int((t-6)//3))
  await seek(10.5)
  marker=await root.locator('canvas').evaluate('c=>c._markers.find(p=>p.object===1&&p.waypoint===3)')
  box=await root.locator('canvas').bounding_box();await page.mouse.move(box['x']+marker['x'],box['y']+marker['y'])
  assert await root.locator('.flow-map-tooltip').is_visible()
  assert 'waypoint 3' in await root.locator('.flow-map-tooltip').inner_text()
  await root.screenshot(path='/tmp/teaser-flow-pair-desktop.png')
  for width in [768,390]:
   await page.set_viewport_size({'width':width,'height':1050});await page.wait_for_timeout(150)
   assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  assert not errors,errors
  await browser.close()
 print('PASS shared teaser scene, all 24 anchors and six ghosts aligned in map/native views, three ordered objects, rewind, hover and mobile layout')

if __name__=='__main__':asyncio.run(main())
