"""Verify exact training readouts, stage colors, lazy media and preserved playback."""
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
def data(body):return json.loads((ROOT/f'assets/locomotion-training-{body}.js').read_text().split(']=',1)[1].rstrip(';\n'))
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce',has_touch=True)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765',wait_until='domcontentloaded')
  root=page.locator('#controller-pretraining')
  assert await root.locator('iframe').count()==0
  assert not await page.evaluate('!!window.CLEAR_LOCOMOTION_DATA')
  await root.scroll_into_view_if_needed()
  await root.locator('[data-loco-source="recorded"]').click()
  await root.locator('.loco-charts').wait_for()
  assert await page.locator('#page-contents a[href="#controller-pretraining"]').count()==1
  for body in ['g1','spot_arm']:
   await root.locator(f'[data-loco-body="{body}"]').click()
   await root.locator('[data-loco-source="recorded"]').click()
   await root.locator('.loco-charts').wait_for()
   await page.wait_for_function('(body)=>document.querySelector("#controller-pretraining").dataset.body===body',arg=body)
   d=data(body)
   assert await root.locator('.loco-phases span').count()==len(d['phases'])
   for index,phase in enumerate(d['phases']):
    assert await root.locator('.loco-phases span').nth(index).inner_text()=='Phase '+['I','II','III'][index]+' · '+phase['label']
   assert await root.locator('.loco-terrain-legend [data-terrain]:visible').count()==(6 if body=='g1' else 5)
   assert await root.locator('[data-loco-viewer]:visible').count()==1
   assert await root.locator('[data-loco-stage]').count()==4
   for index in range(4):assert (await root.locator('[data-loco-stage]').nth(index).inner_text()).startswith(str(index+1)+' · ')
   assert await root.locator('[data-loco-stage][aria-pressed="true"]').count()==1
   for mode in ['optimization','task']:
    await root.locator(f'[data-loco-metrics="{mode}"]').click()
    for canvas in await root.locator('[data-policy-recorded] canvas').all():
     await canvas.focus();await canvas.press('End')
     point=json.loads(await canvas.locator('..').get_attribute('data-inspected'))
     assert point['step']==d['checkpointIteration']
     assert point['value']==d['samples'][-1][d['columns'].index(point['metric'])]
    assert await root.locator('iframe').count()==0,'Inspecting curves must not create a player in reduced motion mode'
   await root.locator('[data-loco-metrics="optimization"]').click()
   canvas=root.locator('[data-policy-recorded] canvas').first;await canvas.focus();await canvas.press('Home');await canvas.press('ArrowRight')
   point=json.loads(await canvas.locator('..').get_attribute('data-inspected'));assert point['step']==25
   box=await canvas.bounding_box();await page.mouse.move(box['x']+box['width']*.55,box['y']+45);await page.wait_for_timeout(100)
   assert await root.locator('.loco-tooltip:visible').count()==1
   points=await root.locator('[data-loco-chart]').evaluate_all('es=>es.map(e=>JSON.parse(e.dataset.inspected))');assert len({p['step'] for p in points})==1
   for point in points:
    row=next(r for r in d['samples'] if r[0]==point['step']);assert point['value']==row[d['columns'].index(point['metric'])]
   await root.screenshot(path=f'/tmp/controller-pretraining-{body}.png')
  for width in [1440,1280,1024,768,390]:
   await page.set_viewport_size({'width':width,'height':1000});await page.wait_for_timeout(150)
   assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
   if width>=1024:
    video=await root.locator('[data-policy-recorded] .loco-rollout').bounding_box();plots=await root.locator('[data-policy-recorded] .loco-evidence').bounding_box()
    assert abs(video['y']-plots['y'])<1 and plots['x']>video['x']+video['width']
   if width==390:await root.screenshot(path='/tmp/controller-pretraining-mobile.png')
  canvas=root.locator('[data-policy-recorded] canvas').first;await canvas.scroll_into_view_if_needed();box=await canvas.bounding_box();await page.touchscreen.tap(box['x']+box['width']*.6,box['y']+45);await page.wait_for_timeout(100)
  assert await root.locator('.loco-tooltip:visible').count()==1
  assert not errors,errors
  await browser.close()
 print('PASS controller checkpoint endpoints, raw hover values, phase mapping, keyboard/touch, lazy scenes, checkpoint controls and responsive row')
asyncio.run(main())
