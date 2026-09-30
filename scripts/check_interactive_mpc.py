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
   await slider.evaluate('e=>{e.value=1;e.dispatchEvent(new Event("input"))}');assert await root.get_attribute('data-elapsed')=='40.000';assert 'After contact loss' in await root.locator('[data-process=baseline] .mpc-recording-status').inner_text()
   await root.locator('#mpc-full-rollout').uncheck();assert await root.get_attribute('data-elapsed')=='15.000'
   await slider.evaluate('e=>{e.value=.95;e.dispatchEvent(new Event("input"))}');await root.locator('#mpc-process-play').click();await page.wait_for_timeout(700);assert await root.get_attribute('data-elapsed')=='15.000';assert await root.locator('#mpc-process-play').inner_text()=='Play'
   for view in ['2d','3d']:
    await root.locator('[data-mpc-view="'+view+'"]').click();assert await root.get_attribute('data-elapsed')=='15.000'
   objective=page.locator('#training-objective .paper-equation-row');assert await objective.locator('.katex-error').count()==0
   assert await objective.locator('.katex').count()==1
   groups=page.locator('#method-execution .controller-galleries>.controller-gallery');left=await groups.nth(0).bounding_box();right=await groups.nth(1).bounding_box();assert right['x']>left['x']+left['width']
   assert await page.locator('#method-execution .controller-galleries').evaluate('e=>e.getBoundingClientRect().width<=innerWidth*.85')
   assert await page.locator('#controller-additional').count()==0
   assert await page.locator('#method-execution .media-unavailable').count()==0
   for i in [0,1]:
    assert await groups.nth(i).locator('.media-tile').count()==2
    assert await groups.nth(i).locator('.media-tile>span').all_text_contents()==['G1','Spot + arm']
    boxes=[await tile.bounding_box() for tile in await groups.nth(i).locator('.media-tile').all()]
    assert abs(boxes[0]['y']-boxes[1]['y'])<1,'Both embodiments must occupy one row'
    assert boxes[1]['x']>=boxes[0]['x']+boxes[0]['width']
    tile=groups.nth(i).locator('.media-tile').first
    await tile.scroll_into_view_if_needed()
    await page.mouse.move(2,2)
    await page.wait_for_timeout(200)
    tile_box=await tile.bounding_box()
    await page.mouse.move(tile_box['x']+tile_box['width']/2,tile_box['y']+tile_box['height']/2)
    overlay=groups.nth(i).locator('.grid-focus')
    await overlay.wait_for()
    assert await overlay.get_attribute('data-pinned')=='false'
    assert await overlay.locator('video').evaluate('e=>getComputedStyle(e).pointerEvents')=='auto'
    enlarged=await overlay.locator('.focus-viewer').bounding_box()
    assert abs(enlarged['width']/enlarged['height']-4/3)<.03,'Expanded video must preserve its full view'
    # The enlarged surface itself must remain hoverable and clickable.
    await page.mouse.move(enlarged['x']+enlarged['width']/2,enlarged['y']+enlarged['height']-25)
    await page.wait_for_timeout(250)
    assert await overlay.is_visible()
    await overlay.locator('video').click(position={'x':enlarged['width']/2,'y':enlarged['height']/2})
    assert await groups.nth(i).locator('.grid-focus').is_visible()
    assert await overlay.get_attribute('data-pinned')=='true'
    await groups.nth(i).locator('.focus-close').click()
   await root.screenshot(path='/tmp/interactive-mpc-final.png');await page.locator('#method-execution .controller-galleries').screenshot(path='/tmp/comparison-layout-final.png');await objective.screenshot(path='/tmp/paper-objective-final.png')
   for width in [768,390]:
    await page.set_viewport_size({'width':width,'height':1000});assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');await root.scroll_into_view_if_needed();await root.screenshot(path=f'/tmp/interactive-mpc-{width}.png')
   assert not errors,errors;await b.close();print('PASS interactive 3D, follow inset, event pin, contact/full windows, fixed time across views, two embodiments in one row per controller, full enlarged videos, KaTeX objective, responsive layout')
asyncio.run(main())
