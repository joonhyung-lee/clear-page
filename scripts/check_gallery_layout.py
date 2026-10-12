"""Check gallery frame bounds, playback, and hover/touch dismissal in Chromium."""
import argparse
import asyncio
from playwright.async_api import async_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-url', default='http://localhost:8773')
BASE = parser.parse_args().base_url.rstrip('/')

async def check_frame(viewer):
    result = await viewer.evaluate('''e => {
      const v=e.querySelector(':scope > video'), b=e.querySelector('.launch');
      const r=e.getBoundingClientRect(), vr=v.getBoundingClientRect(), br=b.getBoundingClientRect();
      return {contained:vr.left>=r.left-1&&vr.right<=r.right+1&&vr.top>=r.top-1&&vr.bottom<=r.bottom+1,
        separate:vr.bottom<=br.top+1, fit:getComputedStyle(v).objectFit,
        transform:getComputedStyle(v).transform};
    }''')
    assert result == dict(contained=True, separate=True, fit='contain', transform='none'), result

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for width in [1440, 1024, 768, 390]:
            page = await browser.new_page(viewport={'width':width,'height':1000}, has_touch=width==390, is_mobile=width==390)
            errors=[]
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.goto(BASE+'/', wait_until='networkidle')
            objects=page.locator('#input-objects > .viewer > video')
            await objects.scroll_into_view_if_needed()
            assert await objects.evaluate('(v)=>getComputedStyle(v).transform')=='none'
            await objects.evaluate('(v)=>v.play()')
            await page.wait_for_function("document.querySelector('#input-objects video').currentTime>.1")
            await page.locator('[data-input-panel=scene]').click()
            assert await objects.evaluate('(v)=>v.paused')
            grid = page.locator('#input-scene .media-grid')
            for tile in await grid.locator('.media-tile').all():
                await page.mouse.move(0,0)
                await tile.scroll_into_view_if_needed()
                if width==390:
                    await tile.tap()
                else:
                    # The hover overlay replaces the hit target as soon as the pointer enters.
                    await tile.hover(force=True)
                await grid.locator('.grid-focus').wait_for(state='visible')
                await page.wait_for_timeout(200)
                await check_frame(grid.locator('.focus-viewer'))
                video=grid.locator('.focus-viewer > video')
                await video.evaluate('(v)=>v.play()')
                await page.wait_for_function("document.querySelector('#input-scene .focus-viewer > video').currentTime>.1")
                assert await grid.locator('.grid-focus').get_attribute('data-pinned')=='true'
                await video.evaluate('(v)=>v.pause()')
                # Clicking the native pause control must not bubble into an unconditional play().
                await video.dispatch_event('click')
                assert await video.evaluate('(v)=>v.paused')
                await grid.locator('.focus-close').click()
                assert await grid.locator('.grid-focus').is_hidden()
                assert await video.evaluate('(v)=>v.paused')
            await grid.locator('.media-tile').first.focus()
            await page.keyboard.press('Enter')
            await grid.locator('.grid-focus').wait_for(state='visible')
            await page.keyboard.press('Escape')
            assert await grid.locator('.grid-focus').is_hidden()
            await grid.locator('.media-tile').first.focus()
            await page.keyboard.press('Enter')
            await page.locator('[data-input-panel=objects]').click()
            await page.locator('[data-input-panel=scene]').click()
            assert await grid.locator('.grid-focus').is_hidden()
            assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert not errors, errors
            print(f'PASS {width}px: four scenes, video playback/pause, close, keyboard, tab reset, page width', flush=True)
            if width==1440:
                await page.locator('details').evaluate_all('(nodes)=>nodes.forEach(n=>n.open=true)')
                count=0
                for other in await page.locator('.media-grid').all():
                    if not await other.is_visible(): continue
                    tile=other.locator('.media-tile').first
                    if not await tile.count(): continue
                    await page.mouse.move(0,0)
                    await tile.focus()
                    await page.keyboard.press('Enter')
                    await other.locator('.grid-focus').wait_for(state='visible')
                    await page.wait_for_timeout(200)
                    await check_frame(other.locator('.focus-viewer'))
                    await other.locator('.focus-close').click()
                    count+=1
                print(f'PASS {count} visible galleries: frame and control bounds',flush=True)
            await page.close()
        await browser.close()

if __name__=='__main__':
    asyncio.run(main())
