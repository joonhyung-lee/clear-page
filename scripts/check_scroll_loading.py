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
        await asyncio.sleep(.4)
        await route.fulfill(body=f'window.CLEAR_VIEWER_HEX="{RUNTIME}";',content_type='text/javascript')
    async def recording(route):
        name = route.request.url.split('/')[-1].split('.hex')[0]
        calls.append(name)
        await route.fulfill(body=f'window.CLEAR_RECORDINGS ??= {{}}; window.CLEAR_RECORDINGS["{name}"]="00";',content_type='text/javascript')
    await page.route('**/runtime-hex.js*',runtime)
    await page.route('**/recordings/*.hex.js*',recording)
    await page.goto(BASE,wait_until='networkidle')
    root = page.locator('#embodiment-demo')
    await root.evaluate("e=>e.scrollIntoView({block:'start'})")
    await page.wait_for_timeout(100)
    await page.evaluate('window.scrollTo(0,0)')
    await page.wait_for_timeout(750)
    assert calls == [], calls
    await root.evaluate("e=>e.scrollIntoView({block:'start'})")
    await page.wait_for_function("document.querySelector('#embodiment-demo iframe')")
    scene = await root.locator('iframe').first.evaluate('f=>f.parentElement.dataset.scene')
    first = root.locator(f'.viewer[data-scene="{scene}"]')
    # HTML exists, but a poster still covers the not-yet-ready player.
    assert await first.locator('.preview-image').is_visible()
    assert await first.locator('iframe').evaluate('f=>getComputedStyle(f).opacity') == '0'
    assert len([c for c in calls if c.startswith('structure-')]) == 1, calls
    await page.wait_for_function("document.querySelectorAll('#embodiment-demo iframe.scene-ready').length===4")
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
    await first.frame_locator('iframe').locator('.tabler-icon-player-pause-filled').wait_for(state='attached',timeout=5000)
    # An intentional pause survives leaving and returning to the section.
    await first.frame_locator('iframe').locator('button').click()
    await page.evaluate('window.scrollTo(0,0)')
    await page.wait_for_timeout(200)
    await first.scroll_into_view_if_needed()
    await page.wait_for_timeout(200)
    assert await first.frame_locator('iframe').locator('.tabler-icon-player-pause-filled').count() == 0
    await first.scroll_into_view_if_needed()
    await page.wait_for_timeout(150)
    # A graphics context loss restarts locally once, without new downloads.
    await first.frame_locator('iframe').locator('canvas').evaluate("c=>c.dispatchEvent(new Event('webglcontextlost'))")
    await page.wait_for_function("!document.querySelector('#embodiment-demo iframe[data-identity]')")
    await first.locator('iframe.scene-ready').wait_for()
    assert len(calls) == count, calls
    await first.frame_locator('iframe').locator('canvas').evaluate("c=>c.dispatchEvent(new Event('webglcontextlost'))")
    await first.get_by_role('button',name='Retry 3D',exact=True).wait_for()
    assert await first.locator('.preview-image').is_visible()
    assert await first.locator('iframe').count() == 0
    await page.close()
    print('Scroll dwell, serial native startup, ready-only reveal, pause/resume, iframe reuse and bounded graphics recovery: PASS',flush=True)

async def cancel_automatic(browser):
    page = await browser.new_page(viewport={'width':1440,'height':900})
    started = asyncio.Event()
    recordings = []
    async def runtime(route):
        started.set()
        await asyncio.sleep(.6)
        await route.fulfill(body=f'window.CLEAR_VIEWER_HEX="{RUNTIME}";',content_type='text/javascript')
    await page.route('**/runtime-hex.js*',runtime)
    page.on('request',lambda r:recordings.append(r.url) if '/recordings/' in r.url else None)
    await page.goto(BASE,wait_until='networkidle')
    await page.locator('#embodiment-demo').scroll_into_view_if_needed()
    await asyncio.wait_for(started.wait(),5)
    await page.evaluate('window.scrollTo(0,0)')
    await page.wait_for_timeout(900)
    assert recordings == [], recordings
    assert await page.locator('#embodiment-demo .viewer-status').count() == 0
    await page.close()
    print('Leaving during shared runtime loading cancels automatic recording requests: PASS',flush=True)

async def previews(browser, exhausted=False):
    page = await browser.new_page(viewport={'width':1440,'height':900})
    requests = []
    failed = False
    async def video(route):
        nonlocal failed
        requests.append(route.request.url)
        if exhausted or not failed:
            failed = True
            await route.fulfill(status=503,body='Temporary media failure')
        else:
            await route.continue_()
    await page.route('**/objects.mp4*',video)
    await page.goto(BASE,wait_until='networkidle')
    assert requests == [], requests
    target = page.locator('.viewer[data-scene="objects"] video')
    await target.scroll_into_view_if_needed()
    if exhausted:
        await page.wait_for_function("""() => {
          const video=document.querySelector('.viewer[data-scene=objects] video');
          const state=mediaStates.get(video);return state.attempts===3 && !state.loading;
        }""",timeout=15000)
        count = len(requests)
        await page.wait_for_timeout(1200)
        # A browser may issue its own range retry within one preparation.
        assert len(requests) == count and 3 <= count <= 6, requests
        assert await target.is_visible()
        assert await target.get_attribute('poster')
        assert await page.locator('.viewer[data-scene="objects"] .launch').is_enabled()
        await page.close()
        print('Persistent media failures retain the poster and stop after three attempts: PASS',flush=True)
        return
    await page.wait_for_function("document.querySelector('.viewer[data-scene=objects] video').currentTime>0",timeout=15000)
    assert len(requests) >= 2, requests
    assert await target.evaluate("v=>v.classList.contains('media-ready')")
    await page.evaluate('window.scrollTo(0,0)')
    await page.wait_for_timeout(200)
    assert await target.evaluate('v=>v.paused')
    await target.evaluate("v=>{window.videoReloads=0;v.addEventListener('loadstart',()=>window.videoReloads++)}")
    await target.scroll_into_view_if_needed()
    await page.wait_for_timeout(500)
    assert not await target.evaluate('v=>v.paused')
    assert await page.evaluate('window.videoReloads') == 0
    await page.close()
    print('Near-only preview preparation, transient video recovery, offscreen pause and no scroll reload: PASS',flush=True)

async def exact_viewport(browser):
    page = await browser.new_page(viewport={'width':1000,'height':800})
    calls=[]
    fixture=FIXTURE.replace('<article>', '<div style="height:1200px"></div><article>')+'<script>observeAutomaticScene(document.querySelector(".viewer"));</script>'
    await page.route(BASE+'/',lambda r:r.fulfill(body=fixture,content_type='text/html'))
    async def runtime(route):
        calls.append('runtime');await route.fulfill(body=f'window.CLEAR_VIEWER_HEX="{RUNTIME}";',content_type='text/javascript')
    async def recording(route):
        calls.append('recording');await route.fulfill(body='window.CLEAR_RECORDINGS={objects:"00"};',content_type='text/javascript')
    await page.route('**/runtime-hex.js*',runtime)
    await page.route('**/objects.hex.js*',recording)
    await page.goto(BASE+'/',wait_until='domcontentloaded')
    viewer=page.locator('.viewer')
    await viewer.evaluate('e=>scrollBy(0,e.getBoundingClientRect().top-innerHeight-40)')
    await page.wait_for_timeout(900)
    assert not calls,calls
    await viewer.scroll_into_view_if_needed()
    await viewer.locator('iframe.scene-ready').wait_for()
    assert calls==['runtime','recording'],calls
    await page.close()
    print('A scene 40 px outside the viewport stays inactive until it enters: PASS',flush=True)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        await exact_viewport(browser)
        await gallery(browser)
        await cancel_automatic(browser)
        await previews(browser)
        await previews(browser, exhausted=True)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
