"""Viewport loading, readiness and playback regressions against the local page.

Run serve.py on port 8765 first. Uses Playwright Chromium and local fault injection.
"""
import asyncio
from playwright.async_api import async_playwright
from check_scene_loading import BASE, FIXTURE

# Delay canvas creation to distinguish HTML load from native playback readiness.
RUNTIME = '''<!doctype html><head></head><body><script>
setTimeout(()=>{document.body.innerHTML='<div id=root></div><canvas></canvas><input value="0"><button><i class="tabler-icon-player-pause-filled"></i></button>';
const view={useSceneTree:{getAll:()=>({'/mesh':{message:{name:'/mesh',type:'MeshMessage'}}})},mutable:{current:{nodeRefFromName:{'/mesh':{traverse:f=>f({geometry:{attributes:{position:{count:3}}},visible:true})}}}}};document.querySelector('#root').__reactContainerMock={memoizedProps:{value:view}};const button=document.querySelector('button');button.onclick=()=>{const playing=button.firstChild.classList.toggle('tabler-icon-player-pause-filled');button.firstChild.classList.toggle('tabler-icon-player-play-filled',!playing);};},500);
</script></body>'''.encode().hex()

async def gallery(browser):
    page = await browser.new_page(viewport={'width':1440,'height':900})
    calls = []
    async def runtime(route):
        calls.append('runtime')
        await route.fulfill(body=f'window.CLEAR_VIEWER_HEX="{RUNTIME}";',content_type='text/javascript')
    async def recording(route):
        name = route.request.url.split('/')[-1].split('.hex')[0]
        calls.append(name)
        await route.fulfill(body=f'window.CLEAR_RECORDINGS ??= {{}}; window.CLEAR_RECORDINGS["{name}"]="00";',content_type='text/javascript')
    await page.route('**/runtime-hex.js*',runtime)
    await page.route('**/recordings/*.hex.js*',recording)
    await page.goto(BASE,wait_until='networkidle')
    root = page.locator('#embodiment-demo')
    await root.scroll_into_view_if_needed()
    await page.wait_for_timeout(1200)
    assert calls == [], calls
    first = root.locator('.viewer').first
    await first.locator('.launch').click()
    await first.locator('iframe').wait_for()
    assert await first.locator('.preview-image').is_visible()
    assert await first.locator('iframe').evaluate('f=>getComputedStyle(f).opacity') == '0'
    await first.locator('iframe.scene-ready').wait_for()
    assert calls == ['runtime',await first.get_attribute('data-scene')],calls
    for viewer in (await root.locator('.viewer').all())[1:]:
        await viewer.locator('.launch').click()
        await viewer.locator('iframe.scene-ready').wait_for()
    assert calls.count('runtime') == 1, calls
    await first.locator('iframe').evaluate("f=>f.dataset.identity='retained'")
    await page.wait_for_timeout(400)
    assert await first.locator('.preview-image').is_hidden()
    await page.evaluate('window.scrollTo(0,0)')
    await page.wait_for_timeout(200)
    for frame in await root.locator('iframe').element_handles():
        native = await frame.content_frame()
        assert await native.locator('.tabler-icon-player-pause-filled').count() == 0
    count = len(calls)
    await first.scroll_into_view_if_needed()
    await page.wait_for_timeout(200)
    assert len(calls) == count, calls
    assert await first.locator('iframe').get_attribute('data-identity') == 'retained'
    await first.frame_locator('iframe').locator('.tabler-icon-player-pause-filled').wait_for(state='attached')
    await first.frame_locator('iframe').locator('button').click()
    await page.evaluate('window.scrollTo(0,0)')
    await page.wait_for_timeout(200)
    await first.scroll_into_view_if_needed()
    await page.wait_for_timeout(200)
    assert await first.frame_locator('iframe').locator('.tabler-icon-player-pause-filled').count() == 0
    await first.frame_locator('iframe').locator('canvas').evaluate("c=>c.dispatchEvent(new Event('webglcontextlost'))")
    await page.wait_for_function("!document.querySelector('#embodiment-demo iframe[data-identity]')")
    await first.locator('iframe.scene-ready').wait_for()
    assert len(calls) == count, calls
    await first.frame_locator('iframe').locator('canvas').evaluate("c=>c.dispatchEvent(new Event('webglcontextlost'))")
    await first.get_by_role('button',name='Retry 3D',exact=True).wait_for()
    assert await first.locator('.preview-image').is_visible()
    assert await first.locator('iframe').count() == 0
    await page.close()
    print('PASS scroll performs no 3D downloads; manual readiness, pause/resume, cache reuse and local graphics recovery',flush=True)

async def previews(browser):
    page = await browser.new_page(viewport={'width':1440,'height':900})
    requests = []; recover = False
    async def video(route):
        requests.append(route.request.url)
        if recover: await route.continue_()
        else: await route.fulfill(status=429,body='Rate limited')
    await page.route('**/objects.mp4*',video)
    await page.goto(BASE,wait_until='networkidle')
    target = page.locator('.viewer[data-scene="objects"] video')
    await target.scroll_into_view_if_needed()
    await page.wait_for_timeout(800)
    assert requests == [], requests
    await target.evaluate("v=>{v.play().catch(()=>{});}")
    retry=page.locator('.viewer[data-scene="objects"] .media-retry')
    await retry.wait_for()
    count=len(requests)
    await page.wait_for_timeout(6000)
    assert len(requests)==count,requests
    assert await target.is_visible() and await target.get_attribute('poster')
    recover=True
    await retry.click()
    await page.wait_for_function("document.querySelector('.viewer[data-scene=objects] video').currentTime>0")
    await page.evaluate('window.scrollTo(0,0)')
    await page.wait_for_timeout(200)
    assert await target.evaluate('v=>v.paused')
    await target.evaluate("v=>{window.videoReloads=0;v.addEventListener('loadstart',()=>window.videoReloads++)}")
    await target.scroll_into_view_if_needed()
    await page.wait_for_timeout(500)
    assert not await target.evaluate('v=>v.paused')
    assert await page.evaluate('window.videoReloads') == 0
    await page.close()
    print('PASS video 429 retains preview; only Retry reloads; user-started playback resumes without reloading',flush=True)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        await gallery(browser)
        await previews(browser)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
