"""Exercise actual Play in 3D embeds and both native palm markers."""
import asyncio,io
import numpy as np
from PIL import Image
from playwright.async_api import async_playwright
from check_research_visuals import FIND,SEEK
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist']);page=await b.new_page(viewport={'width':1440,'height':1050},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765',wait_until='domcontentloaded')
  for scene in ['mpc-stock-optimized','mpc-baseline','mpc-stock-baseline']:
   view=page.locator('[data-scene='+scene+']');await view.scroll_into_view_if_needed();await view.locator('.launch').click(force=True);await view.locator('iframe.scene-ready').wait_for(timeout=60000)
   frame=await (await view.locator('iframe').element_handle()).content_frame();assert await frame.evaluate(FIND)
   if scene.endswith('baseline'):
    names=await frame.evaluate('()=>Object.keys(testViewer.useSceneTree.getAll()).filter(n=>n.includes("/palm-centers-"))')
    assert len(names)==4,names
   for time in ([2,15,45] if scene.endswith('optimized') else [2,5]):
    await frame.evaluate(SEEK,time);await page.wait_for_timeout(250)
    await frame.evaluate('''()=>{const v=testViewer,m=v.mutable.current,q=v.useSceneTree.get("").wxyz,r=m.camera.quaternion.clone().set(q[1],q[2],q[3],q[0]);const eye=m.camera.position.clone().set(-2.2,-2.2,1.8).applyQuaternion(r),at=m.camera.position.clone().set(.7,0,.7).applyQuaternion(r);m.cameraControl.setLookAt(...eye.toArray(),...at.toArray(),false)}''');await page.wait_for_timeout(200)
    await view.screenshot(path=f'/tmp/{scene}-palm-play-{time}.png')
    if scene.endswith('baseline') and time==5:
     canvas=frame.locator('canvas').last;before=np.asarray(Image.open(io.BytesIO(await canvas.screenshot())))
     await frame.evaluate('()=>Object.keys(testViewer.useSceneTree.getAll()).filter(n=>n.includes("/palm-centers-")).forEach(n=>testViewer.sceneTreeActions.updateNodeAttributes(n,{overrideVisibility:false}))');await page.wait_for_timeout(250)
     after=np.asarray(Image.open(io.BytesIO(await canvas.screenshot())))
     changed=int(np.any(abs(before.astype(int)-after.astype(int))>10,axis=2).sum());assert changed>5,(scene,'Palm markers not visibly rendered',changed)
     print(scene,'visible palm-marker pixels',changed,flush=True)
     await frame.evaluate('()=>Object.keys(testViewer.useSceneTree.getAll()).filter(n=>n.includes("/palm-centers-")).forEach(n=>testViewer.sceneTreeActions.updateNodeAttributes(n,{overrideVisibility:true}))')

   await view.get_by_role('button',name='Back to video',exact=True).click();assert await view.locator('.preview-video').is_visible()
  assert not errors,errors;await b.close();print('PASS actual 3D launches, stock contact overlays, paired SUMO palm anchors, seek and return to video')
asyncio.run(main())
