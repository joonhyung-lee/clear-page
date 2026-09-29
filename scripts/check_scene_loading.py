"""Browser regression checks for scene recovery. Run with serve.py on port 8765.

Requires Playwright and Chromium. Faults are injected into local requests only.
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

BASE = 'http://localhost:8765'
FIXTURE = '''<!doctype html><link rel="stylesheet" href="/assets/site.css">
<video id="teaser"></video><button id="hero-toggle"></button>
<article><h3>Scene</h3><div class="viewer" data-scene="objects">
<img class="preview-image" alt="Preview"><button class="launch">Play in 3D</button>
</div></article><script src="/assets/site.js"></script>'''
RUNTIME = '<!doctype html><head></head><body><canvas></canvas><input aria-label="Playback"></body>'.encode().hex()

async def scenario(browser, fault):
    page = await browser.new_page(reduced_motion='reduce')
    counts = {'runtime': 0, 'recording': 0}
    recover = False
    await page.route(BASE + '/', lambda route: route.fulfill(body=FIXTURE, content_type='text/html'))
    async def runtime(route):
        counts['runtime'] += 1
        await route.fulfill(body=f'window.CLEAR_VIEWER_HEX="{RUNTIME}";', content_type='text/javascript')
    async def recording(route):
        counts['recording'] += 1
        if fault == 'cancel':
            await asyncio.sleep(.3)
        if fault == 'exhausted' and not recover:
            await route.fulfill(status=429, body='Temporarily unavailable')
        elif counts['recording'] == 1 and fault == 'network':
            await route.abort('failed')
        elif counts['recording'] == 1 and fault == 'incomplete':
            await route.fulfill(body='/* incomplete response */', content_type='text/javascript')
        else:
            await route.fulfill(body='window.CLEAR_RECORDINGS={objects:"00"};', content_type='text/javascript')
    await page.route('**/runtime-hex.js*', runtime)
    await page.route('**/objects.hex.js*', recording)
    await page.goto(BASE + '/')
    viewer = page.locator('.viewer')
    await viewer.locator('.launch').click()
    if fault == 'cancel':
        await viewer.evaluate("v=>v.dispatchEvent(new Event('reset-viewer'))")
        await page.wait_for_timeout(600)
        assert await viewer.locator('iframe,.viewer-status').count() == 0
        assert await viewer.locator('.launch').is_enabled()
    else:
        if fault == 'exhausted':
            await page.get_by_role('button', name='Retry 3D', exact=True).wait_for(timeout=10000)
            assert counts['recording'] == 3, counts
            assert await viewer.locator('.preview-image').is_visible()
            assert await viewer.locator('.viewer-status').is_visible()
            recover = True
            # A real click catches overlays that cover the recovery control.
            await page.get_by_role('button', name='Retry 3D', exact=True).click()
        await viewer.frame_locator('iframe').locator('input').wait_for(timeout=10000)
        await page.wait_for_function("!document.querySelector('.viewer-status')")
        assert counts['runtime'] == 1, counts
        assert counts['recording'] == (4 if fault == 'exhausted' else 2), counts
        await viewer.locator('.viewer-tools').click()
        await viewer.locator('.launch').click()
        await viewer.frame_locator('iframe').locator('input').wait_for()
        assert counts['runtime'] == 1, counts
        assert counts['recording'] == (4 if fault == 'exhausted' else 2), counts
    await page.close()
    print(f'{fault}: PASS', flush=True)

async def shared_loads(browser):
    page = await browser.new_page(reduced_motion='reduce')
    await page.route(BASE + '/', lambda route: route.fulfill(body=FIXTURE, content_type='text/html'))
    active = maximum = requests = 0
    async def slow(route):
        nonlocal active, maximum, requests
        active += 1; requests += 1; maximum = max(maximum, active)
        await asyncio.sleep(.08)
        key = Path(route.request.url).name
        await route.fulfill(body=f'window[{repr("loaded_"+key)}]=true;', content_type='text/javascript')
        active -= 1
    await page.route('**/test-load-*', slow)
    await page.goto(BASE + '/')
    await page.evaluate('''async () => {
      await Promise.all(Array.from({length:8},(_,i)=>{
        const key='test_load_'+(i%4);
        return loadScript('/test-load-'+key,()=>window['loaded_test-load-'+key]===true);
      }));
    }''')
    assert requests == 4 and maximum <= 2, (requests, maximum)
    await page.close()
    print('Shared requests and concurrency bound: PASS', flush=True)

async def media_requests(browser):
    page = await browser.new_page(reduced_motion='reduce')
    videos = []
    page.on('request', lambda r: videos.append(r.url) if '.mp4' in r.url else None)
    await page.goto(BASE + '/', wait_until='networkidle')
    assert not [u for u in videos if '/teaser.mp4' not in u], videos
    grid = page.locator('.media-grid').first
    preview = grid.locator('.grid-focus video')
    await preview.evaluate("v=>{window.previewStarts=0;v.addEventListener('loadstart',()=>window.previewStarts++)}")
    tile = grid.locator('.media-tile').first
    await tile.focus()
    await page.keyboard.press('Enter')
    await page.wait_for_function("document.querySelector('.grid-focus video').readyState>=1")
    await grid.locator('.focus-close').click()
    await tile.focus()
    await page.keyboard.press('Enter')
    await page.wait_for_timeout(300)
    assert await page.evaluate('window.previewStarts') == 1
    await page.close()
    print('Offscreen videos stay unloaded; repeat preview reuses its source: PASS', flush=True)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for fault in ('network', 'incomplete', 'exhausted', 'cancel'):
            await scenario(browser, fault)
        await shared_loads(browser)
        await media_requests(browser)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
