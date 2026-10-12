"""Verify early autoplay, packed data, checkpoint videos and static code UI."""
import argparse
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--base-url',default='http://localhost:8773');args=parser.parse_args()
BASE=args.base_url.rstrip('/')

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  early=await browser.new_page();release=asyncio.Event()
  async def hold(route):await release.wait();await route.continue_()
  await early.route('**/assets/page-bundle.js?*',hold)
  await early.goto(BASE+'/',wait_until='commit')
  await early.wait_for_function("document.querySelector('#teaser')?.currentTime>.2")
  assert await early.evaluate('typeof clearAssetURL')=='undefined'
  await early.locator('#hero-toggle').click();assert await early.locator('#teaser').evaluate('(v)=>v.paused')
  await early.locator('#hero-toggle').click();await early.wait_for_function("!document.querySelector('#teaser').paused")
  release.set();await early.wait_for_function('window.CLEAR_APP_READY===true')
  await early.close();print('PASS autoplay and pause/resume before application download completes',flush=True)
  page=await browser.new_page(viewport={'width':1440,'height':1000});errors=[];requests=[]
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url))
  await page.goto(BASE+'/',wait_until='networkidle')
  for selector,lines in [('#tldr .academic-copy',1),('#motivation .academic-copy',2)]:
   ratio=await page.locator(selector).evaluate('(e)=>e.clientHeight/parseFloat(getComputedStyle(e).lineHeight)')
   assert abs(ratio-lines)<.1,(selector,ratio)
  for kind in ['grounding','ordering']:
   if kind=='ordering':await page.get_by_role('button',name='Reference plans',exact=True).click()
   root=page.locator('.learning-explorer[data-kind='+kind+']');await root.scroll_into_view_if_needed()
   await root.locator('.learning-content').wait_for(state='visible')
  expected=json.loads((ROOT/'assets/learning-samples.js').read_text().split('=',1)[1].strip().removesuffix(';'))
  assert await page.evaluate('window.CLEAR_LEARNING_SAMPLES')==expected
  print('PASS sentence layout and both sample explorers; packed samples match source',flush=True)
  section=page.locator('#controller-pretraining');await section.scroll_into_view_if_needed()
  for body,label in [('g1','G1'),('spot','Spot'),('spot_arm','Spot + arm')]:
   await section.get_by_role('button',name=label,exact=True).click()
   await page.wait_for_function('(body)=>document.querySelector("#spot-curriculum").dataset.body===body',arg=body)
   buttons=section.locator('[data-checkpoint-stage]');count=await buttons.count()
   for index in range(count):
    await buttons.nth(index).click()
    await page.wait_for_function("document.querySelector('[data-checkpoint-video]')?.currentTime>.2")
    state=await section.locator('[data-checkpoint-video]').evaluate('(v)=>({error:v.error?.message,paused:v.paused,src:v.currentSrc})')
    assert not state['error'] and not state['paused'],state
   print(f'PASS {body}: all {count} checkpoint videos advance',flush=True)
  assert not [r for r in requests if '.hex.js' in r],requests
  await page.close()
  static=await browser.new_page(java_script_enabled=False);await static.goto(BASE+'/code/index.html')
  assert await static.locator('[data-archive-tree="source"] .archive-row').count()>50
  assert await static.locator('.component:visible').count()==1
  assert await static.locator('.component:visible .code-line').count()>10
  await static.close();print('PASS code tree and source excerpt without JavaScript',flush=True)
  for legacy in [False,True]:
   page=await browser.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
   if legacy:await page.add_init_script('window.DecompressionStream=undefined')
   await page.goto(BASE+'/code/index.html',wait_until='networkidle');await page.wait_for_function('window.CLEAR_APP_READY===true')
   for button in await page.locator('[data-flow-node]').all():
    await button.click();await page.locator('.component:visible .code-line').first.wait_for()
   await page.get_by_role('button',name='Example',exact=True).click()
   await page.locator('.component:visible .result').scroll_into_view_if_needed()
   await page.wait_for_function('window.CLEAR_PAGE_PREVIEWS_READY===true')
   await page.close()
  print('PASS Code / Example views and uncompressed browser fallback',flush=True)
  page=await browser.new_page(viewport={'width':390,'height':844})
  await page.goto(BASE+'/',wait_until='networkidle')
  for anchor in ['#tldr','#motivation','#controller-pretraining']:
   await page.locator(anchor).scroll_into_view_if_needed()
   assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),anchor
  await page.close();assert not errors,errors
  await browser.close();print('PASS mobile layout; no application exceptions',flush=True)
asyncio.run(main())
