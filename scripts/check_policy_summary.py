"""Check real checkpoint previews, incomplete finals and explicit replay launch."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--use-angle=vulkan', '--enable-features=Vulkan',
            '--disable-vulkan-surface', '--enable-gpu', '--ignore-gpu-blocklist'])
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
        await page.goto('http://localhost:8765/#learning-policy-summary', wait_until='domcontentloaded')
        summary = page.locator('#learning-policy-summary')
        training = page.locator('#controller-pretraining')
        assert await summary.locator('.policy-summary-checkpoint:visible').count() == 3
        assert await summary.locator('[data-policy-summary-panel="g1"] button').last.is_disabled()
        assert not await training.is_visible()
        await training.evaluate('e=>e.closest("details").open=true')
        await training.scroll_into_view_if_needed()
        await page.wait_for_function("document.querySelector('#spot-curriculum').dataset.body==='g1'")
        assert await training.locator('iframe').count() == 0, 'Opening learning details must not launch a native scene'
        await summary.locator('[data-policy-summary-body="spot"]').click()
        card = summary.locator('[data-policy-summary-panel="spot"] [data-summary-stage="locomotion"]')
        scene = await card.get_attribute('data-summary-scene')
        await card.click()
        await page.wait_for_function("document.querySelector('#spot-curriculum').dataset.body==='spot'")
        viewer = training.locator('#spot-curriculum .viewer')
        await page.wait_for_function('(scene)=>document.querySelector("#spot-curriculum .viewer")?.dataset.scene===scene', arg=scene)
        await viewer.locator('iframe.scene-ready').wait_for(timeout=90000)
        assert '3,000' in await training.locator('[data-curriculum-caption]').inner_text()
        await page.screenshot(path='/tmp/clear-policy-summary-replay.png')
        await page.set_viewport_size({'width': 390, 'height': 900})
        await summary.scroll_into_view_if_needed()
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        await summary.screenshot(path='/tmp/clear-policy-summary-mobile.png')
        await browser.close()
    print('PASS three checkpoint summaries, unavailable final, body-specific replay selection, click-only native startup and mobile layout')


if __name__ == '__main__':
    asyncio.run(main())
