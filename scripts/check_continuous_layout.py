"""Exercise visible evidence, continuous playback and matching method geometry."""
import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright
GPU=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist']
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=GPU)
  page=await browser.new_page(viewport={'width':1600,'height':1100},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765/',wait_until='domcontentloaded')
  assert await page.locator('.research-links a').all_text_contents()==['Method','Training','Experiment']
  assert await page.locator('.hero-copy').evaluate("e=>getComputedStyle(e).backgroundColor")=='rgba(255, 255, 255, 0.88)'
  assert await page.locator('.overview-stages').count()==0
  assert await page.locator('.overview-column>[data-overview-stage]').count()==4
  assert await page.locator('.grounding-columns>*').count()==3
  assert await page.locator('#embodiment-demo .embodiment-gallery>figure:visible').count()==4
  assert await page.locator('#method-order .waypoint').count()==0
  assert await page.locator('#method-order .selection-ring').count()==2
  assert await page.locator('.planning-scope').count()==0
  assert await page.locator('#generation-rule .katex').count()==1
  tabs=await page.locator('#encoding .input-tabs').bounding_box()
  modes=await page.locator('#embodiment-demo .embodiment-controls').bounding_box()
  assert abs(tabs['y']-modes['y'])<1,(tabs,modes)
  for section,rule in [('method-order','ordering-rule'),('method-flow','generation-rule')]:
   parts=await page.locator('#'+section).evaluate("(e,id)=>[e.querySelector('figure'),e.querySelector('#'+id),e.querySelector('.method-lead')].map(n=>n.getBoundingClientRect().top)",rule)
   assert parts==sorted(parts),parts
  for para in await page.locator('#method-execution>p').all():
   widths=await para.evaluate('(e)=>[e.getBoundingClientRect().width,e.parentElement.getBoundingClientRect().width]')
   assert abs(widths[0]-widths[1])<2,widths
  assert await page.locator('#method-flow .flow-ghost').count()==4
  for target in ['#method-order','#method-flow']:
   assert await page.locator(target+' .maze-wall').count()==8
   assert await page.locator(target+' [data-object] text').all_text_contents()==['o₁','o₂','o₃']
  await page.locator('#method-flow input').fill('1')
  assert await page.locator('#method-flow .sequence-explanation').get_attribute('data-flow-time')=='1.00'
  assert await page.locator('#method-execution>details').count()==0
  assert await page.locator('#method-execution>.controller-details').is_visible()
  for selector in ['[data-sample-panels]','#controller-pretraining','#training-losses .loss-content']:
   assert await page.locator(selector).evaluate("e=>!e.closest('details:not([open])')")
  assert await page.locator('#learning .supervision-map').count()==0
  assert await page.locator('#experiments .experiment-supervision').count()==0
  assert await page.locator('.experiment-scenes figure').count()==4
  assert await page.locator('#experiments>.chapter-links').count()==0
  scenes=await page.locator('.experiment-scenes figure').evaluate_all('nodes=>nodes.map(n=>n.getBoundingClientRect().top)')
  assert abs(scenes[0]-scenes[1])<1 and abs(scenes[2]-scenes[3])<1 and scenes[2]>scenes[0]
  panels=await page.locator('.horizon-scenes .experiment-viewer').evaluate_all('nodes=>nodes.map(n=>n.getBoundingClientRect().top)')
  assert len(panels)==4 and max(panels)-min(panels)<2,panels
  for selector in ['.chapter-links','.failure-example p','.paper-results p','.record-scope']:
   sizes=await page.locator(selector).evaluate_all('nodes=>nodes.map(n=>parseFloat(getComputedStyle(n).fontSize))')
   assert min(sizes)>=14,(selector,sizes)
  await page.locator('#mpc-process').evaluate("e=>e.scrollIntoView({block:'start'})")
  await page.wait_for_function("document.querySelector('#mpc-process').dataset.elapsed!==undefined")
  await page.locator('#mpc-process-update').fill('0.3333')
  await page.wait_for_function("[...document.querySelectorAll('.execution-body-viewer>.preview-video')].every(v=>Math.abs(v.currentTime-5)<.2&&v.readyState>=2)")
  for v in await page.locator('.execution-body-viewer').all():
   assert await v.locator('.ego-inset video').get_attribute('poster')
  await page.locator('#mpc-full-rollout').check()
  await page.locator('#mpc-process-update').fill('0.75')
  await page.wait_for_function("[...document.querySelectorAll('.execution-body-viewer video')].every(v=>v.duration>=39.95&&Math.abs(v.currentTime-30)<.2&&v.readyState>=2)")
  await page.locator('#mpc-full-rollout').uncheck()
  await page.screenshot(path='/tmp/clear-continuous-execution-final.png')
  await page.locator('#failure-cases').scroll_into_view_if_needed()
  await page.wait_for_function("document.querySelector('[data-failure-map]').dataset.overlapSegments!==undefined")
  assert len(json.loads(await page.locator('[data-failure-map]').get_attribute('data-overlap-segments')))>0
  await page.locator('[data-failure-example="transfer"] input').fill('1')
  assert 'Clearance failed' in await page.locator('[data-failure-example="transfer"] .failure-stage').inner_text()
  await page.wait_for_function("document.querySelector('[data-planning-failure]').dataset.source==='archived-planning-decisions'")
  await page.locator('[data-failure-example="planning"] input').fill('1')
  assert 'No valid plan' in await page.locator('[data-failure-example="planning"] .failure-stage').inner_text()
  assert await page.locator('.failure-status').count()==0
  visuals=await page.locator('.failure-gallery .failure-visual').evaluate_all('nodes=>nodes.map(n=>n.getBoundingClientRect().top)')
  assert max(visuals)-min(visuals)<2,visuals
  for width in [1600,768,390]:
   await page.set_viewport_size({'width':width,'height':1000})
   assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
  await page.close()
  page=await browser.new_page(viewport={'width':1600,'height':1100});page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765/',wait_until='domcontentloaded')
  await page.locator('#method-flow').scroll_into_view_if_needed();await page.wait_for_timeout(500)
  before=await page.locator('#method-flow .sequence-explanation').get_attribute('data-flow-time');await page.wait_for_timeout(250)
  assert await page.locator('#method-flow .sequence-explanation').get_attribute('data-flow-time')!=before
  selection=page.locator('#method-order .sequence-explanation')
  before=await selection.get_attribute('data-selection-time');await page.wait_for_timeout(300)
  assert await selection.get_attribute('data-selection-time')!=before
  await page.locator('[data-selection-toggle]').click()
  stopped=await selection.get_attribute('data-selection-time');await page.wait_for_timeout(200)
  assert await selection.get_attribute('data-selection-time')==stopped
  await page.locator('#embodiment-demo').scroll_into_view_if_needed()
  await page.wait_for_function("document.querySelectorAll('#embodiment-demo iframe.scene-ready').length===4",timeout=120000)
  await page.evaluate("window.originalFrames=[...document.querySelectorAll('#embodiment-demo iframe')]")
  for mode in ['traversability','manipulation','structure']:
   await page.locator(f'[data-embodiment-mode="{mode}"]').click()
   assert await page.evaluate("[...document.querySelectorAll('#embodiment-demo iframe')].every((f,i)=>f===originalFrames[i])")
  print('PASS four native embodiments and mode switches without reload',flush=True)
  await page.locator('#experiment-grid .experiment-viewer:visible:not([data-no-execution])').first.scroll_into_view_if_needed()
  view=page.locator('#experiment-grid .experiment-viewer:visible:not([data-no-execution])').first
  await view.locator('iframe.scene-ready').wait_for(timeout=90000)
  await view.evaluate('v=>window.liveExperiment=v')
  await page.wait_for_function('window.liveExperiment._lastReplayTime>0',timeout=30000)
  t=await view.evaluate('v=>v._lastReplayTime');await page.wait_for_timeout(300)
  assert await view.evaluate('v=>v._lastReplayTime')!=t
  assert await page.locator('.viewer iframe').count()<=7
  print('PASS automatic experiment rollout and bounded offscreen scene contexts',flush=True)
  assert not errors,errors
  await browser.close()
 print('PASS shared maze, selection without anchors, paired ghosts, continuous layout, synchronized body/trajectory times, visible failures and mobile widths')
if __name__=='__main__':asyncio.run(main())
