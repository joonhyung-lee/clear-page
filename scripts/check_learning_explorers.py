import asyncio
from playwright.async_api import async_playwright
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce');errors=[];calls=[]
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:calls.append(r.url))
  await page.goto('http://localhost:8765',wait_until='networkidle')
  assert not any('learning-samples' in x or 'mpc-process-data' in x for x in calls)
  for kind,count in [('grounding',126),('ordering',52)]:
   root=page.locator('#learning-'+kind);await root.scroll_into_view_if_needed();await root.locator('.learning-content').wait_for();assert await root.locator('circle').count()==count
   await root.screenshot(path='/tmp/learning-'+kind+'.png')
   dot=root.locator('circle').nth(7);box=await dot.bounding_box();await page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2);assert 'Sample 8' in await root.locator('.sample-title').inner_text()
   await dot.focus();await page.keyboard.press('ArrowRight');assert 'Sample 9' in await root.locator('.sample-title').inner_text()
   await root.locator('.sample-play').click();await page.wait_for_timeout(250);assert float(await root.locator('.sample-progress').input_value())>0
   await page.evaluate('window.scrollTo(0,0)');await page.wait_for_timeout(200)
   stopped=await root.locator('.sample-progress').input_value();await page.wait_for_timeout(250);assert await root.locator('.sample-progress').input_value()==stopped
   await root.scroll_into_view_if_needed();await page.wait_for_timeout(200);assert await root.locator('.sample-progress').input_value()!=stopped
   await root.locator('.sample-play').click()
  root=page.locator('#mpc-process');await root.scroll_into_view_if_needed();await root.locator('.mpc-process-content').wait_for()
  await root.locator('#mpc-process-play').click();await page.wait_for_timeout(1500);assert float(await root.get_attribute('data-elapsed'))>1;assert int(await root.locator('[data-process=optimized]').get_attribute('data-update'))>1
  await page.evaluate('window.scrollTo(0,0)');await page.wait_for_timeout(200)
  stopped=await root.locator('canvas').first.evaluate('c=>c.toDataURL()');await page.wait_for_timeout(250);assert await root.locator('canvas').first.evaluate('c=>c.toDataURL()')==stopped
  await root.scroll_into_view_if_needed();await root.locator('#mpc-process-play').click();await root.screenshot(path='/tmp/mpc-process.png')
  for width in [768,390]:
   await page.set_viewport_size({'width':width,'height':950})
   for sel in ['#learning-grounding','#learning-ordering','#mpc-process']:
    await page.locator(sel).scroll_into_view_if_needed();assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,sel)
   await root.screenshot(path='/tmp/mpc-process-'+str(width)+'.png')
  assert not errors,errors;print('Explorers: lazy data, 178 actual points, hover/keyboard, replay, offscreen pause/resume, MPC stages, responsive widths PASS');await b.close()
asyncio.run(main())
