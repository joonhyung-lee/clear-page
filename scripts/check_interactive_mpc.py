"""Exercise orbit, pan, wheel, touch, tracking inset, event pin, and comparison layout."""
import asyncio,json,math
from playwright.async_api import async_playwright
from browser_diagnostics import browser_diagnostics
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  async with browser_diagnostics(page, 'interactive-mpc'):
   await page.goto('http://localhost:8765/#mpc-process',wait_until='domcontentloaded');root=page.locator('#mpc-process');await root.scroll_into_view_if_needed();await root.locator('.mpc-process-content').wait_for()
   assert await root.get_attribute('data-play-limit')=='15'
   slider=root.locator('#mpc-process-update');await slider.evaluate('e=>{e.value=.5;e.dispatchEvent(new Event("input"))}')
   canvas=root.locator('canvas').first
   async def camera():return json.loads(await canvas.get_attribute('data-camera'))
   first=await camera();await canvas.scroll_into_view_if_needed();box=await canvas.bounding_box();x,y=box['x']+120,box['y']+200
   pixels=await canvas.evaluate('e=>e.toDataURL()');await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+60,y+30,steps=5);await page.mouse.up();await page.wait_for_timeout(250)
   rotated=await camera();assert rotated['yaw']<first['yaw'];assert await canvas.evaluate('e=>e.toDataURL()')!=pixels;assert await root.get_attribute('data-elapsed')=='7.500'
   await page.mouse.wheel(0,-250);await page.wait_for_timeout(200);assert (await camera())['zoom']>rotated['zoom']
   await page.keyboard.down('Shift');await page.mouse.down();await page.mouse.move(x+90,y+50,steps=3);await page.mouse.up();await page.keyboard.up('Shift');await page.wait_for_timeout(200);assert (await camera())['pan']!=[0,0]
   await canvas.focus();await page.keyboard.press('Home');await page.wait_for_timeout(200);assert await camera()==first
   await page.keyboard.press('ArrowLeft');await page.wait_for_timeout(150);assert (await camera())['yaw']>first['yaw'];await page.keyboard.press('Home');await page.wait_for_timeout(150)
   before=await camera();box=await canvas.bounding_box();cdp=await page.context.new_cdp_session(page)
   points=[{'x':box['x']+100,'y':box['y']+180,'id':1},{'x':box['x']+200,'y':box['y']+180,'id':2}]
   await cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':points});points[1]['x']+=50
   await cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':points});await cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
   await page.wait_for_timeout(200);assert (await camera())['zoom']>before['zoom'];await page.keyboard.press('Home');await page.wait_for_timeout(150)
   for t in [3,8,14]:
    await slider.evaluate('(e,t)=>{e.value=t/15;e.dispatchEvent(new Event("input"))}',t)
    for c in await root.locator('canvas').all():
     assert math.isclose(float(await c.get_attribute('data-detail-time')),t,abs_tol=.001)
     assert float(await c.get_attribute('data-detail-scale'))>0
     box=json.loads(await c.get_attribute('data-detail-box'));assert box[2]>=10 and box[3]>=10
   await root.locator('.mpc-time-pin').click();assert await root.get_attribute('data-elapsed')=='14.000';assert await root.locator('[data-process=optimized]').get_attribute('data-complete')=='true'
   pin=await root.locator('.mpc-time-pin').evaluate('e=>parseFloat(e.style.left)');assert math.isclose(pin,14/15*100,abs_tol=.001)
   await root.locator('#mpc-full-rollout').check();assert await root.get_attribute('data-play-limit')=='40';assert math.isclose(await root.locator('.mpc-time-pin').evaluate('e=>parseFloat(e.style.left)'),35)
   await slider.evaluate('e=>{e.value=1;e.dispatchEvent(new Event("input"))}');assert await root.get_attribute('data-elapsed')=='40.000';assert 'Contact lost' in await root.locator('[data-process=baseline] .mpc-recording-status').inner_text()
   await root.locator('#mpc-full-rollout').uncheck();assert await root.get_attribute('data-elapsed')=='15.000'
   await slider.evaluate('e=>{e.value=.95;e.dispatchEvent(new Event("input"))}');await root.locator('#mpc-process-play').click();await page.wait_for_timeout(700);assert await root.get_attribute('data-elapsed')=='15.000';assert await root.locator('#mpc-process-play').inner_text()=='Play'
   for view in ['2d','3d']:
    await root.locator('[data-mpc-view="'+view+'"]').click();assert await root.get_attribute('data-elapsed')=='15.000'
   objective=page.locator('#training-objective .paper-equation-row');assert await objective.locator('.katex-error').count()==0
   assert await objective.locator('.katex').count()==1
   for selector in ['#mpc-process','#spot-process']:
    groups=page.locator(selector+' .execution-controller')
    assert await groups.count()==2
    assert await groups.evaluate_all("nodes=>nodes.map(n=>document.getElementById(n.getAttribute('aria-labelledby')).textContent)")==['MPC w/ optimization (ours)','MPC (naive)']
    figures=page.locator(selector+' .execution-controller-panels>figure')
    boxes=[await figure.bounding_box() for figure in await figures.all()]
    assert len(boxes)==4 and max(box['y'] for box in boxes)-min(box['y'] for box in boxes)<2
    assert all(boxes[i+1]['x']>=boxes[i]['x']+boxes[i]['width'] for i in range(3))
    assert await groups.locator('.execution-body-viewer .ego-inset').count()==2
   assert await page.locator('#method-execution .pushing-gallery').count()==0
   await root.screenshot(path='/tmp/interactive-mpc-final.png')
   await page.locator('#spot-process').screenshot(path='/tmp/spot-comparison-layout-final.png')
   await objective.screenshot(path='/tmp/paper-objective-final.png')
   for width in [768,390]:
    await page.set_viewport_size({'width':width,'height':1000});assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');await root.scroll_into_view_if_needed();await root.screenshot(path=f'/tmp/interactive-mpc-{width}.png')
   assert not errors,errors;await b.close();print('PASS interactive 3D, follow inset, event pin, contact/full windows, fixed time across views, one four-panel row per body, paired robot and EEF views, KaTeX objective, responsive layout')
asyncio.run(main())
