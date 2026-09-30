"""Keep the random G1 lineage separate from the archived warm start in the UI."""
import asyncio
import json
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width':1440, 'height':1050}, reduced_motion='reduce')
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.goto('http://localhost:8765/#controller-pretraining', wait_until='domcontentloaded')
        section = page.locator('#controller-pretraining')
        await section.scroll_into_view_if_needed()
        await page.wait_for_function("document.querySelector('#spot-curriculum').dataset.body==='g1'")
        assert await section.get_attribute('data-source') == 'new'
        scratch = section.locator('#spot-curriculum')
        assert await scratch.is_visible()
        assert 'random initialization' in await scratch.locator('[data-curriculum-intro]').inner_text()
        assert await page.evaluate('window.CLEAR_BODY_CURRICULA.g1.curves[0].update') == 1
        scene = await scratch.locator('.scratch-viewer').get_attribute('data-scene')
        assert scene == 'learning-g1-scratch-initialization-000000'
        assert '0 cumulative PPO updates' in await scratch.locator('[data-curriculum-caption]').inner_text()
        await scratch.locator('[data-policy-evaluation]').click()
        evaluation = page.locator('#policy-evaluation')
        assert await evaluation.get_attribute('data-body') == 'g1_scratch'
        svg = evaluation.locator('figure svg').first
        await svg.focus(); await svg.press('Home')
        point = json.loads(await evaluation.locator('figure').first.get_attribute('data-inspected'))
        expected = await page.evaluate('window.CLEAR_POLICY_EVALUATION.bodies.g1_scratch.rows[0]')
        assert point['update'] == 0 and point['mean'] == expected['tracking']['mean']
        assert expected['success']['count'] == 0
        await section.locator('[data-loco-source="recorded"]').evaluate('(n)=>n.click()')
        assert await scratch.is_hidden()
        assert await evaluation.get_attribute('data-body') == 'g1'
        await section.locator('[data-loco-source="new"]').evaluate('(n)=>n.click()')
        assert await evaluation.get_attribute('data-body') == 'g1_scratch'
        assert await scratch.locator('.scratch-viewer').get_attribute('data-scene') == scene
        await section.screenshot(path='/tmp/clear-g1-from-scratch.png')
        assert not errors, errors
        # A robot switch during a pending request must load the new body
        # immediately, rather than waiting for the 30-second refresh timer.
        racing = await browser.new_page(viewport={'width':1440, 'height':1050})
        pending, release = asyncio.Event(), asyncio.Event()
        async def delay_g1(route):
            pending.set()
            await release.wait()
            await route.continue_()
        await racing.route('**/g1-curriculum-data.js?*', delay_g1)
        await racing.goto('http://localhost:8765/#controller-pretraining', wait_until='domcontentloaded')
        await racing.locator('#controller-pretraining').scroll_into_view_if_needed()
        await asyncio.wait_for(pending.wait(), timeout=15)
        await racing.locator('[data-loco-body="spot"]').click()
        release.set()
        await racing.wait_for_function("document.querySelector('#spot-curriculum').dataset.body==='spot'", timeout=5000)
        assert 'spot-scratch' in await racing.locator('.scratch-viewer').get_attribute('data-scene')
        await browser.close()
    print('PASS G1 random initialization, update 0 replay, genuine evaluation, live losses, archived lineage separation and robot switching during loading')


if __name__ == '__main__':
    asyncio.run(main())
