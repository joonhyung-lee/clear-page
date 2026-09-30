"""Verify that input highlighting follows recorded sample metadata in both explorers."""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.goto('http://localhost:8765', wait_until='domcontentloaded')
        for kind in ['grounding', 'ordering']:
            root = page.locator('#learning-' + kind)
            await root.scroll_into_view_if_needed()
            await root.locator('.learning-content').wait_for()
            assert await root.locator('.sample-factors button').count() == 4
            for key in ['body', 'objects', 'scene', 'query']:
                await root.locator(f'.sample-factors [data-factor="{key}"]').focus()
                result = await root.evaluate('''(root, args) => {
                    const [kind, key] = args;
                    const dots = [...root.querySelectorAll('.sample-scatter circle')];
                    const samples = CLEAR_LEARNING_SAMPLES[kind];
                    const index = dots.findIndex(d => d.classList.contains('selected'));
                    const sig = s => JSON.stringify(key === 'body' ? [s.body,s.links] : key === 'objects' ? s.scene.objects : key === 'scene' ? [s.scene.walls,s.scene.terrain] : s.query || [s.scene.start,s.scene.goal]);
                    return {expected:samples.map(s=>sig(s)===sig(samples[index])),actual:dots.map(d=>d.classList.contains('factor-match'))};
                }''', [kind, key])
                assert result['actual'] == result['expected'], (kind, key)
                assert any(result['actual'])
            await root.locator('.sample-next').click()
            assert await root.locator('.factor-match').count() == 0
            assert await root.locator('details').count() == 0
        assert await page.locator('.context-mode, .context-training').count() == 0
        assert await page.locator('#ordering-context .selection-object').count() == 5
        assert await page.locator('#ordering-context .ordering-context-flow>section').count() == 2
        assert await page.locator('#ordering-context .ordering-scene-slot .viewer').count() == 1
        assert await page.locator('#ordering-context .selection-probability').count() == 0
        assert await page.locator('#ordering-context .ordering-main').count() == 1
        await page.locator('#grounding-samples').screenshot(path='/tmp/grounding-inputs.png')
        assert not errors, errors
        await browser.close()
    print('PASS sample input matching, keyboard highlighting, visible supervision and unified ordering context')

asyncio.run(main())
