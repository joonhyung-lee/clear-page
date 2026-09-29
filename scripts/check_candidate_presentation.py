"""Check saved candidate fidelity, rapid forecasts, ordering draws, and contact seeks."""
import asyncio,json,math
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
records=json.loads((ROOT/'assets/mpc-process-data.js').read_text().split('=',1)[1].rstrip(';\n'))
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':1440,'height':1050},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765',wait_until='domcontentloaded');root=page.locator('#mpc-process');await root.scroll_into_view_if_needed();await root.locator('.mpc-process-content').wait_for()
  async def seek(t):await root.locator('input').evaluate('(e,t)=>{e.value=t/40;e.dispatchEvent(new Event("input"))}',t)
  await seek(8)
  before={name:await root.locator('[data-process='+name+']').get_attribute('data-update') for name in records}
  pixels=await root.locator('canvas').first.evaluate('e=>e.toDataURL()');await seek(8.1)
  assert pixels!=await root.locator('canvas').first.evaluate('e=>e.toDataURL()')
  for name,r in records.items():
   panel=root.locator('[data-process='+name+']');assert int(await panel.get_attribute('data-update'))>=int(before[name])
   source=int(await panel.get_attribute('data-update'));u=next(v for v in r['updates'] if v['sourceIndex']==source);assert int(await panel.get_attribute('data-candidate-count'))==24
   time=float(await panel.get_attribute('data-time'));assert u['time']<=time<=u['time']+r['horizon']+1e-5
   direction=[r['reference'][-1][i]-r['reference'][0][i] for i in range(2)];norm=math.hypot(*direction);selected=u['paths'][u['applied']]
   assert await panel.locator('canvas').count()==2
   for hand,canvas in enumerate(await panel.locator('canvas').all()):
    delta=[1000*sum((point[hand][i]-selected[j][hand][i])*direction[i]/norm for i in range(2)) for path in u['paths'][:24] for j,point in enumerate(path)]
    limit=float(await canvas.get_attribute('data-residual-limit'));assert max(map(abs,delta))<=limit+1e-8
    assert float(await canvas.get_attribute('data-window-start'))==u['time']-r['updates'][0]['time']
    assert math.isclose(float(await canvas.get_attribute('data-window-end'))-float(await canvas.get_attribute('data-window-start')),r['horizon'])
  await root.locator('#mpc-process-play').click();start=float(await root.get_attribute('data-elapsed'));await page.wait_for_timeout(400);assert float(await root.get_attribute('data-elapsed'))-start>.5;await root.locator('#mpc-process-play').click()
  await seek(8)
  source=await root.locator('[data-process]').evaluate_all('es=>es.map(e=>[e.dataset.update,e.dataset.retained])')
  for anchor in [0,2,1]:
   await root.locator('[data-anchor="'+str(anchor)+'"]').click()
   for name,r in records.items():
    panel=root.locator('[data-process='+name+']');source_index=int(await panel.get_attribute('data-update'));u=next(v for v in r['updates'] if v['sourceIndex']==source_index)
    target=[0,r['horizon']/2,r['horizon']][anchor];j=min(range(len(r['futureTimes'])),key=lambda k:abs(r['futureTimes'][k]-target))
    for canvas in await panel.locator('canvas').all():
     assert await canvas.get_attribute('data-anchor-letter')=='ABC'[anchor]
     assert math.isclose(float(await canvas.get_attribute('data-anchor-time')),u['time']-r['updates'][0]['time']+r['futureTimes'][j])
     assert float(await canvas.get_attribute('data-anchor-offset'))==r['futureTimes'][j]
     assert int(await canvas.get_attribute('data-applied'))==u['applied']
   assert await root.locator('[data-process]').evaluate_all('es=>es.map(e=>[e.dataset.update,e.dataset.retained])')==source
  for mode,counts in [('retained',[3,2]),('all',[24,24])]:
   await root.locator('[data-candidates='+mode+']').click()
   assert await root.locator('[data-process]').evaluate_all('es=>es.map(e=>Number(e.dataset.visibleCandidates))')==counts
   assert await root.locator('[data-process]').evaluate_all('es=>es.map(e=>[e.dataset.update,e.dataset.retained])')==source
   assert await root.locator('#mpc-process-play').inner_text()=='Play'
  assert await root.locator('canvas[data-palm="1"]').count()==2;await root.screenshot(path='/tmp/candidate-final.png')
  order=page.locator('.ordering-main');await order.scroll_into_view_if_needed();assert await order.locator('svg g').count()==3;assert await page.locator('.ordering-spatial .viewer').is_hidden()
  assert await order.locator('.ordering-sequence strong').all_text_contents()==['Object 1','Object 2']
  a=await order.locator('svg').inner_html();await order.locator('#maze-order-next').click();assert a!=await order.locator('svg').inner_html();assert await order.get_attribute('data-sample')=='1'
  await order.locator('.order-draw-play').click();await page.wait_for_timeout(2450);assert await order.get_attribute('data-sample')=='2';await order.locator('.order-draw-play').click()
  button=page.locator('[data-mpc-seek="14.14"]');await button.click();video=page.locator('[data-scene=mpc-baseline] .preview-video');await page.wait_for_function('e=>e.currentTime>=14.14&&e.currentTime<16',arg=await video.element_handle());await video.evaluate('e=>e.pause()')
  for width in [768,390]:
   await page.set_viewport_size({'width':width,'height':1000});await root.scroll_into_view_if_needed();await root.screenshot(path=f'/tmp/candidate-final-{width}.png');await order.scroll_into_view_if_needed();assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');await order.screenshot(path=f'/tmp/ordering-final-{width}.png')
  assert not errors,errors;await browser.close();print('PASS rapid complete forecasts, recorded candidate spread, actual tracking, stacked hands, probability draws, contact-event seek, responsive layouts')
asyncio.run(main())
