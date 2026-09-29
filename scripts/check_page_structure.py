"""Verify chapter navigation, deep disclosure links, reading width and preserved media."""
import asyncio
from playwright.async_api import async_playwright

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  page=await browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce')
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765',wait_until='domcontentloaded')
  nav=page.locator('#page-contents')
  assert await nav.locator('li[data-depth="3"]').count()>=4
  assert await page.locator('.reading-detail[open]').count()==0
  await page.locator('#method-grounding').scroll_into_view_if_needed()
  await page.wait_for_timeout(150)
  await nav.locator('a[href="#grounding-samples"]').click()
  await page.wait_for_timeout(200)
  assert await page.locator('#grounding-samples').get_attribute('open') is not None
  assert await nav.locator('a[aria-current]').get_attribute('href')=='#grounding-samples'
  assert await nav.locator('li[data-current-branch]').count()==3
  await nav.locator('a[href="#training-objective"]').click()
  await page.wait_for_timeout(200)
  await page.locator('#training-losses .loss-content').wait_for()
  assert await nav.locator('a[aria-current]').get_attribute('href')=='#training-objective'
  rail=await nav.bounding_box();objective=await page.locator('#training-objective').bounding_box()
  assert objective['x']+objective['width']<rail['x'],(objective,rail)
  await page.screenshot(path='/tmp/page-contents-desktop.png')
  await nav.locator('a[href="#controller-trajectories"]').click()
  await page.locator('#mpc-process .mpc-process-content').wait_for()
  assert await page.locator('#controller-trajectories').get_attribute('open') is not None
  assert await nav.locator('a[aria-current]').get_attribute('href')=='#controller-trajectories'
  await page.go_back();await page.wait_for_timeout(200)
  assert page.url.endswith('#training-objective')
  await page.goto('http://localhost:8765/#learning-ordering',wait_until='domcontentloaded')
  await page.wait_for_timeout(400)
  assert await page.locator('#ordering-samples').get_attribute('open') is not None
  for width in [1440,1280,1024,768,390]:
   await page.set_viewport_size({'width':width,'height':1000})
   await page.wait_for_timeout(150)
   assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
   if width<1200:
    button=page.locator('#contents-toggle');await button.click()
    assert await button.get_attribute('aria-expanded')=='true'
    await page.locator('#page-contents a[href="#method-flow"]').click()
    assert await button.get_attribute('aria-expanded')=='false'
    await button.click();await page.keyboard.press('Escape')
    assert await button.get_attribute('aria-expanded')=='false'
   if width==390:await page.screenshot(path='/tmp/page-contents-mobile.png')
  assert not errors,errors
  await browser.close()
 print('PASS hierarchical contents, scroll position, deep-link reveal, history, compact details, rail separation and mobile menu')
asyncio.run(main())
