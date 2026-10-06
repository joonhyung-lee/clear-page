"""Verify the three-chapter layout, real resource dialogs and integrated metrics."""
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  page=await browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce')
  errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
  await page.goto('http://localhost:8765/',wait_until='domcontentloaded')
  assert await page.locator('.research-links a').all_text_contents()==['Method','Training','Experiment']
  assert await page.locator('#page-contents').count()==0
  assert await page.locator('#top video').count()==1 and 'CLEAR' in await page.locator('#top h1').inner_text()
  assert await page.evaluate("['method','learning','results'].map(id=>document.getElementById(id).getBoundingClientRect().top).every((v,i,a)=>!i||v>a[i-1])")
  assert await page.locator('#learning #controller-pretraining').count()==1
  assert await page.locator('#learning #training-objective').count()==1
  assert await page.locator('#failure-cases #ordering-context').count()==1
  assert await page.locator('#failure-cases #flow-learning').count()==1
  assert await page.locator('.overview-input-links').count()==0
  await page.locator('.chapter-links a[href="#method-grounding"]').click()
  assert await page.locator('#embodiment-demo').is_visible()
  assert await page.locator('#input-structure').count()==0
  for key in ['objects','scene']:
   await page.locator(f'[data-input-panel="{key}"]').click()
   assert await page.locator(f'#input-{key}').is_visible()
   assert await page.locator('[data-input-content]:visible').count()==1
   assert await page.locator(f'[data-input-panel="{key}"]').get_attribute('aria-pressed')=='true'
  grounding=page.locator('#embodiment-demo')
  assert await grounding.locator('.embodiment-gallery>figure:visible').count()==4
  for mode in ['structure','traversability','manipulation']:
   await grounding.locator(f'[data-embodiment-mode="{mode}"]').click()
   assert await grounding.locator('.embodiment-gallery>figure:visible').count()==4
  generation=page.locator('#method-flow .sequence-explanation')
  assert 'Illustrative rank-causal' in await generation.get_attribute('aria-label')
  assert 'o₂ → o₃' in await page.locator('#method-order .illustration-order-summary').inner_text()
  original=await generation.locator('svg').inner_html()
  await generation.locator('input').fill('1')
  assert await generation.get_attribute('data-flow-time')=='1.00'
  assert await generation.locator('svg').inner_html()!=original
  await generation.locator('[data-illustration-view="3d"]').click()
  assert await generation.get_attribute('data-view')=='3d'
  assert await generation.locator('svg text').all_text_contents()==['Start','Goal','o₁','o₂','o₃','X','Y','Z']
  await generation.locator('[data-attention-mask]').click()
  assert 'later interaction and is masked' in await generation.locator('.illustration-attention').inner_text()
  await generation.locator('select').select_option('2')
  assert 'earlier generated row y₂' in await generation.locator('.illustration-attention').inner_text()
  for kind in ['paper','video']:
   button=page.locator(f'[data-resource="{kind}"]');await button.click()
   dialog=page.locator('#resource-dialog');assert await dialog.is_visible()
   url=await dialog.locator('[data-resource-download]').get_attribute('href')
   response=await page.request.get('http://localhost:8765/'+url,headers={'Range':'bytes=0-1023'})
   assert response.status in [200,206]
   if kind=='paper':
    frame=await (await dialog.locator('iframe').element_handle()).content_frame()
    await frame.wait_for_function("document.querySelector('#page')?.naturalWidth>1000")
    assert await frame.locator('#position').inner_text()=='1 / 8'
    assert 'Anonymous Authors' in await frame.locator('#text').inner_text()
    for number in range(2,9):
     await frame.locator('#next').click()
     await frame.wait_for_function('(number)=>document.querySelector("#page").complete&&document.querySelector("#page").naturalWidth>1000&&document.querySelector("#position").textContent===`${number} / 8`',arg=number)
    assert await frame.locator('#next').is_disabled()
    await frame.locator('#zoom').click()
    assert await frame.locator('main').evaluate("e=>e.classList.contains('zoomed')")
    await frame.locator('#page').click()
   else:
    video=dialog.locator('video')
    await video.evaluate('e=>e.play()')
    await page.wait_for_function("document.querySelector('#resource-dialog video').videoWidth>0&&document.querySelector('#resource-dialog video').currentTime>0.05")
   await page.keyboard.press('Escape');await dialog.wait_for(state='hidden');assert await button.evaluate('e=>document.activeElement===e')
  await page.goto('http://localhost:8765/#controller-pretraining',wait_until='domcontentloaded')
  await page.wait_for_function("document.querySelector('#spot-curriculum').dataset.body==='g1'")
  for body in ['g1','spot','spot_arm']:
   await page.locator(f'[data-loco-body="{body}"]').click()
   await page.wait_for_function('(body)=>document.querySelector("#spot-curriculum").dataset.body===body',arg=body)
   panel=page.locator('#spot-curriculum');viewer=panel.locator('.scratch-viewer')
   await viewer.evaluate('e=>window.layoutViewer=e')
   controls=panel.locator('.loco-metrics');assert await controls.locator('button').all_text_contents()==['PPO losses','Training progress','Evaluation']
   await panel.locator('[data-policy-evaluation]').click()
   evaluation=panel.locator('#policy-evaluation');assert await evaluation.is_visible()
   assert await evaluation.locator('svg').count()==3
   await evaluation.locator('svg').first.focus();await evaluation.locator('svg').first.press('Home')
   inspected=json.loads(await evaluation.locator('figure').first.get_attribute('data-inspected'))
   key='g1_scratch' if body=='g1' else body
   expected=await page.evaluate('(key)=>window.CLEAR_POLICY_EVALUATION.bodies[key].rows[0].tracking.mean',key)
   assert inspected['mean']==expected and inspected['update']==0
   if body=='g1' and await page.evaluate("window.CLEAR_POLICY_EVALUATION.bodies.g1_scratch.trainingState==='stopped'"):
    assert 'Training stopped' in await evaluation.locator('.eval-disclosure').inner_text()
    assert 'Evaluation in progress' not in await evaluation.locator('.eval-disclosure').inner_text()
   await panel.locator('[data-curriculum-metrics="task"]').click();assert not await evaluation.is_visible()
   assert await viewer.evaluate('e=>e===window.layoutViewer')
   assert await controls.locator('[aria-pressed="true"]').count()==1
  assert await page.get_by_text('Evaluating locomotion progress',exact=True).count()==0
  await page.goto('http://localhost:8765/#experiment-grid',wait_until='domcontentloaded')
  grid=page.locator('#experiment-grid')
  assert await grid.locator('.paper-results tbody tr:visible').count()==3
  await grid.locator('.all-methods-toggle').click();assert await grid.locator('.paper-results tbody tr:visible').count()==6
  await grid.locator('.result-protocol-details > summary').click()
  await grid.locator('#grid-family').select_option('branch')
  assert await grid.locator('[data-family="branch"]').is_visible()
  assert not await grid.locator('[data-family="chain"]').is_visible()
  for width in [1440,768,390]:
   await page.set_viewport_size({'width':width,'height':1000})
   await page.locator('.research-logo').click()
   assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
   assert await page.locator('.research-links').is_visible()
   assert await page.locator('.research-code span').is_visible()
   assert await page.locator('.research-code').get_attribute('href')=='code/index.html'
   if width==390:
    assert not await page.locator('#resource-menu-toggle').is_visible()
    assert await page.locator('.research-resources').is_visible()
    for kind in ['paper','video']:
     control=page.locator(f'[data-resource="{kind}"]')
     assert await control.locator('span').is_visible()
     icon=await control.locator('svg').bounding_box();label=await control.locator('span').bounding_box()
     assert label['y']>=icon['y']+icon['height']
    await page.locator('[data-resource="paper"]').click()
    assert await page.locator('#resource-dialog').is_visible()
    await page.keyboard.press('Escape')
    assert not await page.locator('#resource-dialog').is_visible()
   await page.screenshot(path=f'/tmp/clear-research-{width}.png')
  assert not errors,errors
  await browser.close()
 print('PASS chapters, preserved hero, anonymous resources, metric tabs and values, replay continuity, result methods, deep links and responsive navigation')

if __name__=='__main__':asyncio.run(main())
