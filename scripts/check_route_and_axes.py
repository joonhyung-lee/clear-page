import asyncio,json,math
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'assets/mpc-process-data.js').read_text().split('=',1)[1].rstrip(';\n'))
maxima={}
for name,r in data.items():
 direction=[r['reference'][-1][i]-r['reference'][0][i] for i in range(2)];norm=math.hypot(*direction)
 maxima[name]=max(1000*abs(sum((point[hand][i]-u['paths'][u['applied']][j][hand][i])*direction[i]/norm for i in range(2))) for u in r['updates'] for path in u['paths'][:r['population']] for j,point in enumerate(path) for hand in range(2))
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':1440,'height':1080},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765',wait_until='domcontentloaded');sample=page.locator('#learning-ordering');await sample.scroll_into_view_if_needed();await sample.locator('.learning-content').wait_for();await sample.locator('.sample-scatter circle').nth(16).focus();assert await sample.locator('canvas').is_visible();assert await sample.locator('canvas').get_attribute('data-selected')=='1,2';assert await sample.locator('.sample-ordering').count()==0
  await sample.screenshot(path='/tmp/route-map-17.png');await sample.locator('.sample-route-order button').first.click();assert float(await sample.locator('canvas').get_attribute('data-time'))>0;await sample.screenshot(path='/tmp/route-map-move.png')
  root=page.locator('#mpc-process');await root.scroll_into_view_if_needed();await root.locator('.mpc-process-content').wait_for();assert await root.locator('canvas').count()==4
  for name,maximum in maxima.items():
   panel=root.locator('[data-process='+name+']');assert float(await panel.get_attribute('data-residual-limit'))>=maximum
   top=await panel.locator('canvas').nth(0).bounding_box();bottom=await panel.locator('canvas').nth(1).bounding_box();assert bottom['y']>=top['y']+top['height'] and abs(top['x']-bottom['x'])<1
  before=await root.locator('canvas').evaluate_all('es=>es.map(e=>[e.dataset.residualLimit,e.dataset.horizon,e.width,e.height])')
  for t in [0,.1,.2,.5,.9,1]:
   await root.locator('input').evaluate('(e,t)=>{e.value=t;e.dispatchEvent(new Event("input"))}',t)
   assert await root.locator('canvas').evaluate_all('es=>es.map(e=>[e.dataset.residualLimit,e.dataset.horizon,e.width,e.height])')==before
  await root.locator('input').evaluate('(e)=>{e.value=.2;e.dispatchEvent(new Event("input"))}');await root.screenshot(path='/tmp/fixed-palms.png')
  for width in [768,390]:
   await page.set_viewport_size({'width':width,'height':1050});await root.scroll_into_view_if_needed();await root.screenshot(path=f'/tmp/fixed-palms-{width}.png');await sample.scroll_into_view_if_needed();assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');await sample.screenshot(path=f'/tmp/route-map-{width}.png')
  assert not errors,errors;await b.close();print('PASS Sample 17 visible route and selection, interaction seek, four stacked palm charts and fixed axes across the entire replay, responsive layout')
asyncio.run(main())
