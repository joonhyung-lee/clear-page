"""Verify the directly visible policy view and automatic body-specific replays."""
import asyncio
from playwright.async_api import async_playwright
from check_continuous_layout import GPU
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(args=GPU);page=await b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765/#controller-pretraining',wait_until='domcontentloaded')
  root=page.locator('#controller-pretraining');await root.scroll_into_view_if_needed()
  assert await page.locator('#learning-policy-summary').count()==0
  assert await root.evaluate("e=>!e.closest('details:not([open])')")
  scenes=[]
  for body in ['g1','spot','spot_arm']:
   await root.locator(f'[data-loco-body="{body}"]').click()
   await page.wait_for_function('(body)=>document.querySelector("#spot-curriculum").dataset.body===body',arg=body)
   viewer=root.locator('#spot-curriculum .scratch-viewer');await viewer.scroll_into_view_if_needed()
   await viewer.locator('iframe.scene-ready').wait_for(timeout=90000)
   scene=await viewer.get_attribute('data-scene');scenes.append(scene)
   await viewer.evaluate('v=>window.policyFrame=v.querySelector("iframe")')
   await root.locator('#spot-curriculum [data-curriculum-metrics="task"]').click()
   assert await viewer.evaluate('v=>v.querySelector("iframe")===policyFrame')
   await page.wait_for_function('document.querySelector("#spot-curriculum .scratch-viewer")._lastReplayTime>0',timeout=30000)
   print('PASS automatic policy replay',body,scene,flush=True)
  assert len(set(scenes))==3
  assert not errors,errors
  await b.close()
 print('PASS visible policy training, three distinct automatic replays and continuous metric switching')
if __name__=='__main__':asyncio.run(main())
