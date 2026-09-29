import asyncio,json,math
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'assets/mpc-process-data.js').read_text().split('=',1)[1].rstrip(';\n'))
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':1440,'height':1080},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765',wait_until='domcontentloaded');sample=page.locator('#learning-ordering');await sample.scroll_into_view_if_needed();await sample.locator('.learning-content').wait_for();await sample.locator('.sample-scatter circle').nth(16).focus();assert await sample.locator('canvas').is_visible();assert await sample.locator('canvas').get_attribute('data-selected')=='1,2';assert await sample.locator('.sample-ordering').count()==0
  await sample.screenshot(path='/tmp/route-map-17.png');await sample.locator('.sample-route-order button').first.click();assert float(await sample.locator('canvas').get_attribute('data-time'))>0;await sample.screenshot(path='/tmp/route-map-move.png')
  root=page.locator('#mpc-process');await root.scroll_into_view_if_needed();await root.locator('.mpc-process-content').wait_for();assert await root.locator('canvas').count()==2
  before=await root.locator('canvas').evaluate_all('es=>es.map(e=>[e.dataset.coordinateBounds,e.dataset.ghostTrajectories,e.dataset.recordedEnd])')
  for view in ['2d','3d']:
   await root.locator('[data-mpc-view="'+view+'"]').click()
   for t in [0,.2,.5,1]:
    await root.locator('input').evaluate('(e,t)=>{e.value=t;e.dispatchEvent(new Event("input"))}',t)
    assert await root.locator('canvas').evaluate_all('es=>es.map(e=>[e.dataset.coordinateBounds,e.dataset.ghostTrajectories,e.dataset.recordedEnd])')==before
    for name,r in data.items():
     canvas=root.locator('[data-process='+name+'] canvas');expected=min(t*40,r['observed'][-1][0]-r['updates'][0]['time'])
     assert math.isclose(float(await canvas.get_attribute('data-observed-until')),expected,abs_tol=1e-7)
     assert await canvas.get_attribute('data-hands')=='2'
  await root.locator('input').evaluate('(e)=>{e.value=.2;e.dispatchEvent(new Event("input"))}');await root.screenshot(path='/tmp/fixed-palms.png')
  for width in [768,390]:
   await page.set_viewport_size({'width':width,'height':1050});await root.scroll_into_view_if_needed();await root.screenshot(path=f'/tmp/fixed-palms-{width}.png');await sample.scroll_into_view_if_needed();assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');await sample.screenshot(path=f'/tmp/route-map-{width}.png')
  assert not errors,errors;await b.close();print('PASS Sample 17 visible route and selection, interaction seek, paired palm 2D/3D charts and fixed axes across the entire replay, responsive layout')
asyncio.run(main())
