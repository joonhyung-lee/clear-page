"""Browser acceptance of shared paper examples and synchronized controller videos.

Run outside a sandbox that denies Chromium's socket operations. CLEAR_CODE_URL
may point to an existing preview; otherwise the local page is opened directly.
"""
import asyncio,json,os,traceback
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
REPORT=Path('/tmp/clear-code-story-report.json')

async def main():
 report=dict(status='running',passed=[],failed=None)
 try:
  async with async_playwright() as p:
   args=['--single-process','--no-zygote','--disable-crash-reporter','--disable-breakpad'] if os.environ.get('CLEAR_BROWSER_SINGLE_PROCESS') else []
   browser=await p.chromium.launch(args=args,timeout=30000)
   page=await browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce');errors=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   await page.goto(os.environ.get('CLEAR_CODE_URL',(ROOT/'code/index.html').as_uri()),wait_until='domcontentloaded')
   await page.locator('[data-grounding-tab]').first.wait_for()
   for module,section in [('representation','grounding'),('order','ordering'),('flow','generation'),('verification','validation'),('control','execution')]:
    report['checking']=section;print('PROGRESS',section,'shared example',flush=True)
    await page.locator(f'[data-flow-node="{module}"]').click()
    figure=page.locator(f'#{section} .result');await figure.scroll_into_view_if_needed();viewer=figure.locator('.viewer')
    if section=='grounding':
     for kind,count in [('embodiment',4),('objects',1),('scene',4)]:
      await figure.locator(f'[data-grounding-tab={kind}]').click()
      assert await figure.locator('[data-grounding-panel]:visible').count()==1
      assert await figure.locator(f'[data-grounding-panel={kind}] video').count()==count
    elif section=='ordering':
     assert await figure.locator('.selection-ring').count()==2
     assert 'o₂ → o₃' in await figure.locator('.illustration-order-summary').inner_text()
     await figure.locator('[data-selection-toggle]').click()
     before=await figure.get_attribute('data-selection-time')
     await page.wait_for_function("before=>document.querySelector('[data-method-illustration=ordering]').dataset.selectionTime!==before",arg=before)
     await figure.locator('[data-selection-toggle]').click()
    elif section=='generation':
     await figure.locator('input').fill('0')
     before=await figure.locator('svg').first.inner_html()
     await figure.locator('input').fill('1')
     assert await figure.locator('svg').first.inner_html()!=before
     assert await figure.locator('.generated-path').count()==2
     assert await figure.locator('.flow-ghost').count()==4
     await figure.locator('[data-illustration-view=3d]').click()
     assert await figure.get_attribute('data-view')=='3d'
     await figure.locator('[data-attention-mask]').click()
     assert await figure.locator('.rank-mask').is_visible()
    elif section=='validation':
     for step,blocked in [(0,2),(1,1),(2,0),(0,2)]:
      await figure.locator(f'[data-validation-step="{step}"]').click()
      assert await figure.locator('.clearance-route[data-clear=false]').count()==blocked
     await figure.locator('[data-validation-play]').click()
     await page.wait_for_function("Number(document.querySelector('[data-shared-validation]').dataset.progress)>.05")
     await figure.locator('[data-validation-play]').click()
    elif section=='execution':
     for body in ['g1','spot_arm']:
      await figure.locator(f'[data-execution-tab={body}]').click()
      assert await figure.locator('[data-execution-panel]:visible').count()==1
      panel=figure.locator(f'[data-execution-panel={body}]')
      main=panel.locator('.preview-video')
      await main.evaluate('(v)=>{v.load();}')
      await main.evaluate('(v)=>v.play()')
      await page.wait_for_function("body=>document.querySelector('[data-execution-panel='+body+'] .preview-video').currentTime>.2",arg=body)
      await main.evaluate('(v)=>{v.pause();v.currentTime=2;}')
      await page.wait_for_function("body=>Math.abs(document.querySelector('[data-execution-panel='+body+'] .ego-inset video').currentTime-2)<.1",arg=body)
    await figure.screenshot(path=f'/tmp/clear-code-{section}.png')
    report['passed'].append(section);print('PASS',section,flush=True)
   await page.set_viewport_size({'width':390,'height':844})
   for module in ['representation','order','flow','verification','control']:
    await page.locator('#pipeline-select').select_option(module)
    assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),module
   assert not errors,errors
   await browser.close();report['status']='passed';report.pop('checking',None)
 except Exception:
  report['status']='failed';report['failed']=traceback.format_exc();raise
 finally:
  REPORT.write_text(json.dumps(report,indent=2));print('Report:',REPORT,flush=True)
if __name__=='__main__':asyncio.run(main())
