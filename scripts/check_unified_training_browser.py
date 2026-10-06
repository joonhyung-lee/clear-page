"""Check compact training metrics and the selected training lineage's native replays."""
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
from check_learning_replay_support import FIND

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist'])
  page=await browser.new_page(viewport={'width':1440,'height':1100},reduced_motion='reduce');errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765/#controller-pretraining',wait_until='domcontentloaded')
  section=page.locator('#controller-pretraining');await section.scroll_into_view_if_needed()
  assert await section.locator('[data-loco-source],#policy-evaluation,[data-policy-evaluation],[data-policy-recorded]').count()==0
  root=section.locator('#spot-curriculum')
  for body in ['g1','spot','spot_arm']:
   await section.locator(f'[data-loco-body="{body}"]').click()
   await page.wait_for_function('body=>document.querySelector("#spot-curriculum").dataset.body===body&&document.querySelector(".scratch-viewer")',arg=body)
   data=await page.evaluate('body=>window.CLEAR_BODY_CURRICULA[body]',body)
   checkpoints=data.get('checkpoints') or [s for s in data['stages'] if s['replay']]
   selected=next((s for s in checkpoints if s['id']==data.get('defaultCheckpoint')),checkpoints[0])
   viewer=root.locator('.scratch-viewer');assert await viewer.get_attribute('data-scene')==selected['replay']['scene']
   assert await root.get_attribute('data-replay-updates')==str(selected['replay']['cumulativeUpdates'])
   assert [s.strip() for s in await root.locator('.loco-metrics button').all_text_contents()]==['PPO losses','Training progress']
   assert await root.locator('.curriculum-phase').count()==len([s for s in data['stages'] if s['id']!='initialization'])
   body_buttons=await root.locator('.loco-bodies').bounding_box()
   metric_buttons=await root.locator('.loco-metrics').bounding_box()
   assert abs(body_buttons['y']-metric_buttons['y'])<1,'Robot and metric controls must share the top row'
   assert await root.locator('.curriculum-notes').get_attribute('open') is None
   charts=root.locator('.loco-chart')
   first=await charts.first.bounding_box();last=await charts.last.bounding_box()
   assert last['y']+last['height']-first['y']<560,'All three plots should form a compact stack'
   box=await viewer.bounding_box();assert box['width']<=390.5 and abs(box['width']-box['height'])<2,box
   await viewer.evaluate('v=>window.originalTrainingViewer=v')
   for mode in ['optimization','task']:
    await root.locator(f'[data-curriculum-metrics="{mode}"]').click()
    for chart in await root.locator('.loco-chart').all():
     canvas=chart.locator('canvas');await canvas.focus();await canvas.press('End')
     actual=json.loads(await chart.get_attribute('data-inspected'))
     expected=data['curves'][-1]
     assert actual['step']==expected['update'] and actual['value']==expected.get(actual['metric'])
     assert await canvas.get_attribute('aria-description')
     values=sorted(abs(r[actual['metric']]) for r in data['curves'] if r.get(actual['metric']))
     expected_scale='symlog' if values and values[-1]/values[len(values)//2]>10000 else 'linear'
     assert await chart.get_attribute('data-scale')==expected_scale
     assert await chart.locator('.curriculum-scale-note').is_visible()==(expected_scale=='symlog')
     assert await chart.evaluate('e=>e._plot.maximum')==max(1,data['curves'][-1]['update'])
     assert (await canvas.bounding_box())['height']==128
    assert await viewer.evaluate('v=>v===window.originalTrainingViewer'),'Metric switch must preserve the replay'
   if any(s['state'] in ['failed','stopped'] for s in data['stages']):
    assert 'stopped' in await root.locator('[data-curriculum-status]').inner_text()
   if any(s['state']=='pending' for s in data['stages']):
    pending=root.locator('.curriculum-phase[data-state="pending"]').first
    assert 'Not started' in await pending.inner_text()
    await pending.focus()
    assert 'No recorded updates' in await root.locator('[data-curriculum-explanations]').inner_text()
   await viewer.locator('.launch').click();await viewer.locator('iframe.scene-ready').wait_for(timeout=120000)
   frame=await (await viewer.locator('iframe').element_handle()).content_frame()
   await frame.evaluate(FIND)
   await frame.wait_for_function("()=>!!testViewer.useSceneTree.get('/agents/2')?.message")
   async def seek(time):
    await viewer.evaluate("(v,t)=>v.querySelector('iframe').contentWindow.postMessage({type:'clear-playback-command',time:t,playing:false},'*')",time)
    await page.wait_for_function('(v)=>Math.abs(v.node._lastReplayTime-v.time)<.08',arg={'node':await viewer.element_handle(),'time':time})
    await frame.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    return await frame.evaluate("()=>Array.from(testViewer.useSceneTree.get('/agents/2').message.props.batched_positions)")
   start=selected['replay'].get('startTime',0)
   initial=await seek(start);later=await seek(start+3)
   assert len(initial)==96 and max(abs(a-b) for a,b in zip(initial,later))>.2,'Recorded motion must remain visible'
   if data.get('source')=='archived-controller':
    from check_learning_replay import recording,positions_at
    record,buffers=recording(body)
    for checkpoint in checkpoints:
     await root.locator(f'[data-checkpoint-stage="{checkpoint["id"]}"]').click()
     replay=checkpoint['replay'];time=replay['startTime']
     await page.wait_for_function('(v)=>Math.abs(v.node._lastReplayTime-v.time)<.08',arg={'node':await viewer.element_handle(),'time':time})
     expected=positions_at(record,buffers,time+.001)
     await frame.wait_for_function('(expected)=>{const p=testViewer.useSceneTree.get("/agents/2").message.props.batched_positions;return expected.every((v,i)=>Math.abs(v-p[i])<1e-5)}',arg=expected)
     assert await root.get_attribute('data-replay-updates')==str(replay['cumulativeUpdates'])
     assert await viewer.evaluate('v=>v===window.originalTrainingViewer'),'Checkpoint seeks must reuse the archived viewer'
   await root.locator('[data-curriculum-reset]').click()
   await page.wait_for_function('v=>v._lastReplayTime<1',arg=await viewer.element_handle())
   assert await viewer.evaluate('v=>v===window.originalTrainingViewer')
   await section.screenshot(path=f'/tmp/clear-unified-training-{body}.png')
   print('PASS',body,'matching training lineage, real motion, native checkpoint selection, exact losses and compact view',flush=True)
  for width in [768,390]:
   await page.set_viewport_size({'width':width,'height':1000})
   assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
   box=await root.locator('.scratch-viewer').bounding_box();assert box['width']<=340.5
  assert not errors,errors
  await browser.close()
 print('PASS unified training with two metric views and matching physical replays for all bodies')

if __name__=='__main__':asyncio.run(main())
