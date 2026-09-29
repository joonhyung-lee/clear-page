"""Check saved candidate fidelity, rapid forecasts, ordering draws, and contact seeks."""
import asyncio,json,math
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
records=json.loads((ROOT/'assets/mpc-process-data.js').read_text().split('=',1)[1].rstrip(';\n'))
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':1440,'height':1050},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765',wait_until='domcontentloaded');root=page.locator('#mpc-process');await root.scroll_into_view_if_needed();await root.locator('.mpc-process-content').wait_for();await root.locator('#mpc-full-rollout').check()
  async def seek(t):await root.locator('#mpc-process-update').evaluate('(e,t)=>{e.value=t/40;e.dispatchEvent(new Event("input"))}',t)
  await seek(8)
  before={name:await root.locator('[data-process='+name+']').get_attribute('data-update') for name in records}
  pixels=await root.locator('canvas').first.evaluate('e=>e.toDataURL()');await seek(8.1)
  assert pixels!=await root.locator('canvas').first.evaluate('e=>e.toDataURL()')
  for name,r in records.items():
   panel=root.locator('[data-process='+name+']');assert int(await panel.get_attribute('data-update'))>=int(before[name])
   source=int(await panel.get_attribute('data-update'));u=next(v for v in r['updates'] if v['sourceIndex']==source);assert int(await panel.get_attribute('data-candidate-count'))==24
   time=float(await panel.get_attribute('data-time'));assert u['time']<=time<=u['time']+r['horizon']+1e-5
   canvas=panel.locator('canvas');assert await canvas.get_attribute('data-hands')=='2';assert int(await canvas.get_attribute('data-applied'))==u['applied']
  await root.locator('#mpc-process-play').click();start=float(await root.get_attribute('data-elapsed'));await page.wait_for_timeout(400);assert float(await root.get_attribute('data-elapsed'))-start>.5;await root.locator('#mpc-process-play').click()
  await seek(8);source=await root.locator('[data-process]').evaluate_all('es=>es.map(e=>[e.dataset.update,e.dataset.retained])')
  for mode in ['2d','3d']:
   await root.locator('[data-mpc-view="'+mode+'"]').click()
   assert await root.locator('[data-process]').evaluate_all('es=>es.map(e=>[e.dataset.update,e.dataset.retained])')==source
   assert await root.locator('canvas').evaluate_all('(es,m)=>es.every(e=>e.dataset.view===m)',mode)
  assert await root.locator('button').count()==5;await root.screenshot(path='/tmp/candidate-final.png')
  order=page.locator('.ordering-main');await order.scroll_into_view_if_needed();assert await order.locator('svg g').count()==3;assert await page.locator('.ordering-spatial .viewer').is_hidden()
  assert await order.locator('.ordering-sequence strong').all_text_contents()==['Object 1','Object 2']
  a=await order.locator('svg').inner_html();await order.locator('#maze-order-next').click();assert a!=await order.locator('svg').inner_html();assert await order.get_attribute('data-sample')=='1'
  await order.locator('.order-draw-play').click();await page.wait_for_timeout(2450);assert await order.get_attribute('data-sample')=='2';await order.locator('.order-draw-play').click()
  button=page.locator('[data-mpc-seek="14.14"]');await button.click();video=page.locator('[data-scene=mpc-baseline] .preview-video');await page.wait_for_function('e=>e.currentTime>=14.14&&e.currentTime<16',arg=await video.element_handle());await video.evaluate('e=>e.pause()')
  for width in [768,390]:
   await page.set_viewport_size({'width':width,'height':1000});await root.scroll_into_view_if_needed();await root.screenshot(path=f'/tmp/candidate-final-{width}.png');await order.scroll_into_view_if_needed();assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');await order.screenshot(path=f'/tmp/ordering-final-{width}.png')
  assert not errors,errors;await browser.close();print('PASS rapid complete forecasts, recorded candidate spread, actual tracking, paired hands in 2D/3D, probability draws, contact-event seek, responsive layouts')
asyncio.run(main())
