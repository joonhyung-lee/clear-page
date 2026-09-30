"""Compare the rendered metric layout and exact readouts for all three bodies."""
import asyncio,json
from playwright.async_api import async_playwright

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  page=await browser.new_page(viewport={'width':1440,'height':1100},reduced_motion='reduce',has_touch=True)
  errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
  await page.goto('http://localhost:8765/#controller-pretraining',wait_until='domcontentloaded')
  section=page.locator('#controller-pretraining')
  await section.scroll_into_view_if_needed()
  reference=None; reference_video=None
  for body in ['g1','spot','spot_arm']:
   await section.locator(f'[data-loco-body="{body}"]').click()
   if body=='g1':await section.locator('[data-loco-source="recorded"]').click()
   panel=section.locator('[data-policy-recorded]' if body=='g1' else '#spot-curriculum')
   if body=='g1':
    await panel.locator('.loco-charts').wait_for(state='visible')
   else:
    await page.wait_for_function('(body)=>document.querySelector("#spot-curriculum").dataset.body===body',arg=body)
   buttons=panel.locator('.loco-metrics button:not([data-policy-evaluation])');assert await buttons.count()==2
   assert await buttons.locator('svg[aria-hidden="true"]').count()==2
   assert [s.strip() for s in await buttons.all_text_contents()]==['PPO losses','Training progress']
   charts=panel.locator('.loco-chart');assert await charts.count()==3
   viewer=panel.locator('[data-loco-viewer="g1"]' if body=='g1' else '.scratch-viewer')
   await viewer.evaluate('node=>window.layoutReplayNode=node')
   for mode in ['optimization','task']:
    await buttons.nth(int(mode=='task')).click()
    expected=['Value loss','Policy surrogate loss','Policy entropy'] if mode=='optimization' else ['Episode return','Mean terrain level','Arm curriculum level' if body=='spot_arm' else 'Velocity tracking error']
    assert await charts.locator('figcaption').all_text_contents()==expected,(body,mode)
    assert await buttons.locator('..').locator('[aria-pressed="true"]').count()==1
    bounds=[await chart.bounding_box() for chart in await charts.all()]
    video=await viewer.bounding_box()
    if reference_video is None:reference_video=video
    assert abs(video['width']-reference_video['width'])<1 and abs(video['height']-reference_video['height'])<1,(body,video,reference_video)
    assert all(b['x']>video['x']+video['width'] for b in bounds)
    assert max(b['x'] for b in bounds)-min(b['x'] for b in bounds)<1
    assert all(b['y']>=a['y']+a['height'] for a,b in zip(bounds,bounds[1:])),bounds
    assert abs((await panel.locator('.loco-evidence').bounding_box())['y']-video['y'])<1
    dims=[await c.bounding_box() for c in await charts.locator('canvas').all()]
    if reference is None:reference=dims
    assert all(abs(d['width']-r['width'])<1 and abs(d['height']-148)<1 for d,r in zip(dims,reference)),(body,dims,reference)
    if body!='g1':
     assert 'Loss logging begins with PPO update 1' in await panel.locator('.curriculum-baseline-note').inner_text()
     await page.mouse.move(0,0)
     await page.evaluate('document.activeElement?.blur()')
     source=await page.evaluate('(body)=>window.CLEAR_BODY_CURRICULA[body].curves',body)
     for chart in await charts.all():
      key=await chart.get_attribute('data-metric')
      rows=[row for row in source if key in row]
      c=json.loads(await chart.get_attribute('data-comparison'))
      if rows:
       assert c['baselineUpdate']==rows[0]['update'] and c['baselineUpdate']>0
       assert c['baseline']==rows[0][key] and c['value']==rows[-1][key]
       assert abs(c['delta']-(rows[-1][key]-rows[0][key]))<1e-9
       if key in ['value','entropy'] and rows[0][key]>1e-12:
        assert abs(c['percent']-100*(rows[-1][key]-rows[0][key])/rows[0][key])<1e-8
       else:assert c['percent'] is None
       assert 'Latest' in await chart.locator('.curriculum-comparison').inner_text()
      else:assert c['baseline'] is None and c['delta'] is None
     for chart in await charts.all():
      canvas=chart.locator('canvas');await canvas.focus();await canvas.press('End')
      point=json.loads(await chart.get_attribute('data-inspected'))
      row=await page.evaluate('(body)=>window.CLEAR_BODY_CURRICULA[body].curves.at(-1)',body)
      assert point['step']==row['update']
      assert point['value']==row.get(point['metric']),(body,point,row)
      comparison=json.loads(await chart.get_attribute('data-comparison'))
      assert comparison['comparedUpdate']==point['step'] and comparison['value']==point['value']
      assert await chart.locator('.loco-tooltip').is_visible()
     canvas=charts.first.locator('canvas');box=await canvas.bounding_box()
     await page.mouse.move(box['x']+box['width']*.6,box['y']+55)
     point=json.loads(await charts.first.get_attribute('data-inspected'))
     rows=await page.evaluate('(body)=>window.CLEAR_BODY_CURRICULA[body].curves',body)
     assert point['value']==next(r for r in rows if r['update']==point['step']).get(point['metric'])
    assert await viewer.evaluate('node=>node===window.layoutReplayNode'),'Metric controls recreated the replay'
   if body!='g1':
    assert await panel.locator('[data-curriculum-stages]').count()==0
    stages=await page.evaluate('(body)=>window.CLEAR_BODY_CURRICULA[body].stages',body)
    assert await charts.first.evaluate('e=>e._plot.maximum')==sum(s['targetUpdates'] for s in stages)
    assert await panel.locator('[data-curriculum-phases] span').count()==len(stages)-1
    saved=[s for s in stages if s['replay']]
    assert await charts.first.locator('[data-checkpoint-stage]').count()==len(saved)
    for stage in (saved[-1],saved[0]):
     button=charts.first.locator('[data-checkpoint-stage="'+stage['id']+'"]')
     await button.click()
     assert await panel.locator('.scratch-viewer').get_attribute('data-scene')==stage['replay']['scene']
     assert await button.get_attribute('aria-pressed')=='true'
     assert await panel.get_attribute('data-replay-updates')==str(stage['replay']['cumulativeUpdates'])
   await section.screenshot(path=f'/tmp/clear-training-layout-{body}.png')
   for width in [768,390]:
    await page.set_viewport_size({'width':width,'height':1000})
    video=await viewer.bounding_box();evidence=await panel.locator('.loco-evidence').bounding_box()
    assert evidence['y']>=video['y']+video['height']
    assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(body,width)
   await page.set_viewport_size({'width':1440,'height':1100})
  assert not errors,errors
  await browser.close()
 print('PASS matching G1/Spot/Spot+arm icon controls, vertical three-plot layout, exact logged readouts, shared dimensions, preserved replay nodes and mobile stacking')

if __name__=='__main__':asyncio.run(main())
