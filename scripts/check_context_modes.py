"""Check distinct inference/training paths against the saved numerical trace."""
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'assets/maze-method-trace.js').read_text().split(' = ',1)[1].rstrip(';\n'))
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':1440,'height':1050},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:8765',wait_until='domcontentloaded');root=page.locator('#context-formation');await root.scroll_into_view_if_needed()
  assert await root.locator('.context-inference').is_visible() and await root.locator('.context-training').is_hidden()
  for i in range(3):
   row=root.locator('.context-sampling-row').nth(i);text=await row.inner_text();assert f"{d['traces'][0]['selectionDraw'][i]:.3f}" in text;assert f"{d['traces'][0]['priority'][i]:.2f}" in text
   assert ('Excluded' if not d['traces'][0]['selected'][i] else 'Rank '+str(d['traces'][0]['rank'][i]+1)) in text
  await root.screenshot(path='/tmp/context-inference-final.png')
  await page.locator('.ordering-main svg [data-object="2"]').focus();assert await root.get_attribute('data-object')=='2';assert await root.locator('.context-token[data-object="2"]').evaluate('e=>e.classList.contains("context-selected")')
  await root.get_by_role('button',name='Training signal').click();assert await root.locator('.context-inference').is_hidden();assert await root.locator('.context-training').is_visible();assert await root.locator('.context-target-comparison tbody tr').count()==3;assert await root.locator('.context-update').is_visible();await root.screenshot(path='/tmp/context-training-final.png')
  await root.get_by_role('button',name='Inference',exact=True).click();await page.locator('#maze-order-next').click();assert f"{d['traces'][1]['priority'][1]:.2f}" in await root.locator('.context-sampling-row').nth(1).inner_text()
  for width in [768,390]:
   await page.set_viewport_size({'width':width,'height':1000})
   for label in ['Inference','Training signal']:
    await root.get_by_role('button',name=label,exact=True).click();await root.scroll_into_view_if_needed();assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');await root.screenshot(path=f'/tmp/context-{label.split()[0]}-{width}.png')
  assert not errors,errors;await b.close();print('PASS distinct modes, saved selection draws and priorities, reference targets, shared object highlighting, updated draw synchronization, responsive layouts')
asyncio.run(main())
