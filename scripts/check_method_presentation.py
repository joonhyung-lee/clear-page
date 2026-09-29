import asyncio
from playwright.async_api import async_playwright
FIND='''()=>{const root=document.querySelector('#root'),r=root[Object.keys(root).find(k=>k.startsWith('__reactContainer'))],q=[r,r?.stateNode?.current],seen=new Set();while(q.length){const f=q.pop();if(!f||seen.has(f))continue;seen.add(f);const v=f.memoizedProps?.value;if(v?.sceneTreeActions&&v?.useSceneTree){window.__testViewer=v;return true;}q.push(f.child,f.sibling,f.alternate);}return false;}'''
SEEK='''t=>{const el=document.querySelector('[role=slider]');let f=el[Object.keys(el).find(k=>k.startsWith('__reactFiber'))];while(f){const p=f.memoizedProps;if(p&&p.step===0.0001&&typeof p.onChange==='function'){p.onChange(t);return;}f=f.return;}throw new Error('No slider');}'''

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist']);page=await browser.new_page(viewport={'width':1440,'height':1050},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765',wait_until='domcontentloaded')
  for key in ['mpc-stock-optimized','mpc-stock-baseline','mpc-optimized','mpc-baseline']:
   v=page.locator('[data-scene='+key+']');await v.scroll_into_view_if_needed();assert await v.locator('.ego-inset').is_visible();assert await v.locator('iframe').count()==0
   main=v.locator('.preview-video');await main.evaluate('(e)=>{e.load();e.play()}');await page.wait_for_function('(e)=>e.readyState>=2',arg=await main.element_handle(),timeout=20000)
   await main.evaluate('(e)=>{e.currentTime=3}');await page.wait_for_timeout(900)
   t=await v.locator('.ego-inset video').evaluate('(e)=>e.currentTime');m=await main.evaluate('(e)=>e.currentTime');assert abs(t-m)<.2,(key,t,m)
   await main.evaluate('(e)=>e.pause()');await v.screenshot(path='/tmp/'+key+'-always-inset.png')
  sample=page.locator('#learning-grounding');await sample.scroll_into_view_if_needed();await sample.locator('.learning-content').wait_for();await sample.locator('.sample-scatter circle').nth(87).focus();movie=sample.locator('.sample-video')
  await page.wait_for_function('(e)=>e.readyState>=2',arg=await movie.element_handle(),timeout=20000);assert 'attempt-087' in await movie.get_attribute('src');assert await movie.is_visible()
  await sample.locator('.sample-play').click();await page.wait_for_timeout(700);assert await movie.evaluate('(e)=>e.currentTime')>.2
  await sample.screenshot(path='/tmp/learning-robot-mesh.png');await page.evaluate('scrollTo(0,0)');await page.wait_for_timeout(250);assert await movie.evaluate('(e)=>e.paused')
  context=page.locator('#context-formation');await context.scroll_into_view_if_needed();assert await context.locator('.context-token').count()==7;assert await context.locator('.context-token i').count()==84
  await context.get_by_role('button',name='Training signal').click();assert await context.locator('.context-training').is_visible();assert await context.locator('.context-inference').is_hidden();await context.screenshot(path='/tmp/context-training.png')
  root=page.locator('#mpc-process');await root.scroll_into_view_if_needed();await root.locator('.mpc-process-content').wait_for();await root.locator('input').evaluate("e=>{e.value=.2;e.dispatchEvent(new Event('input'))}");await root.screenshot(path='/tmp/mpc-internal-insets.png')
  await page.emulate_media(reduced_motion='no-preference');overview=page.locator('#clear-overview');await overview.scroll_into_view_if_needed();assert await page.locator('#overview-execution>span').count()==0
  await page.locator('#overview-grounding').hover();await page.wait_for_timeout(800);assert await page.locator('#overview-preview>div:not([hidden]) video').first.evaluate('(e)=>e.currentTime')>0
  await page.locator('#overview-ordering').hover();plot=page.locator('.overview-ordering .ordering-distribution');await plot.locator('svg').wait_for();before=await plot.get_attribute('data-sample');await page.wait_for_timeout(2300);assert await plot.get_attribute('data-sample')!=before
  for stage in ['generation','execution']:
   await page.locator('#overview-'+stage).hover();v=page.locator('#overview-preview>div:not([hidden]) .viewer');await v.locator('iframe.scene-ready').wait_for(timeout=60000)
   f=await (await v.locator('iframe').element_handle()).content_frame();assert await f.evaluate(FIND)
   before=await f.locator('[role=slider]').get_attribute('aria-valuenow');await page.wait_for_timeout(500);after=await f.locator('[role=slider]').get_attribute('aria-valuenow');assert before!=after,(stage,before,after)
   await v.screenshot(path='/tmp/overview-live-'+stage+'.png')
  await page.locator('.ordering-spatial>summary').click();order=page.locator('.ordering-spatial .viewer');await order.scroll_into_view_if_needed();await order.locator('.launch').click(force=True);await order.locator('iframe.scene-ready').wait_for(timeout=60000)
  f=await (await order.locator('iframe').element_handle()).content_frame();assert await f.evaluate(FIND)
  await page.locator('.context-output[data-object="1"]').hover();await page.wait_for_timeout(200)
  flags=await f.evaluate(r'()=>Object.entries(window.__testViewer.useSceneTree.getAll()).filter(([n])=>/^\/order\/sample-0\/uncertainty-\d-[123]$/.test(n)).map(([n,v])=>[n,v.visibility])')
  assert len(flags)==9 and sum(bool(v) for _,v in flags)==3,flags
  await overview.screenshot(path='/tmp/overview-playing.png')
  for width in [768,390]:
   await page.set_viewport_size({'width':width,'height':1000});await context.scroll_into_view_if_needed();assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');await context.screenshot(path=f'/tmp/context-{width}.png');await root.scroll_into_view_if_needed();await root.screenshot(path=f'/tmp/inset-{width}.png');await sample.scroll_into_view_if_needed();assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  assert not errors,errors;await browser.close();print('PASS initial synchronized insets, physical sample movie, H values and training mode, internal plot insets, all hover replays, mobile')
asyncio.run(main())
