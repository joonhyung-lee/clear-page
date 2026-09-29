"""Check original CLEAR data, local deviation, interactive inspection and both layouts."""
import asyncio
import json
import math
import statistics
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / 'assets/training-loss-data.js').read_text().split('=', 1)[1].rstrip(';\n'))
keys = ['loss', 'selection', 'order', 'kl', 'flow', 'affordance']
assert set(data) == {'samples', 'maxStep', 'window'}
assert len(data['samples']) == 1001
for row in data['samples']:
    assert set(row) == {'step', *keys}
    assert math.isclose(row['loss'], row['selection'] + row['order'] + .001 * row['kl'] + row['flow'] + row['affordance'], abs_tol=2e-6)

def verify(entry, key):
    i = next(i for i, r in enumerate(data['samples']) if r['step'] == entry['step'])
    local = [r[key] for r in data['samples'][max(0, i - 10):i + 11]]
    assert entry['raw'] == data['samples'][i][key]
    assert math.isclose(entry['mean'], statistics.mean(local), rel_tol=1e-12)
    assert math.isclose(entry['std'], statistics.pstdev(local), rel_tol=1e-12)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 1050}, reduced_motion='reduce', has_touch=True)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.goto('http://localhost:8765', wait_until='domcontentloaded')
        root = page.locator('#training-losses')
        await root.scroll_into_view_if_needed()
        await root.locator('.loss-content').wait_for()
        assert await page.locator('#training-objective').evaluate('e=>!e.closest("details")')
        assert await root.locator('[data-loss]').count() == 6
        assert await root.locator('[data-loss-run]').count() == 0
        assert await page.locator('.katex-error').count() == 0
        assert 'across seeds' in await root.locator('.loss-band-note').inner_text()
        canvas = root.locator('#loss-loss canvas')
        for keypress in ['Home', 'ArrowRight', 'End']:
            await canvas.focus()
            await canvas.press(keypress)
            for chart in await root.locator('[data-loss]').all():
                verify(json.loads(await chart.get_attribute('data-inspected')), await chart.get_attribute('data-loss'))
        assert await root.locator('#loss-loss').get_attribute('data-inspected-step') == '100000'
        term = root.locator('[data-loss-term=flow]')
        await term.click()
        flow = root.locator('#loss-flow')
        await page.wait_for_timeout(100)
        assert 'loss-term-active' in await flow.get_attribute('class')
        assert await flow.locator('canvas').evaluate('e=>e===document.activeElement')
        box = await flow.locator('canvas').bounding_box()
        await page.mouse.move(box['x'] + box['width'] * .6, box['y'] + 110)
        await page.wait_for_timeout(100)
        assert await flow.locator('.loss-tooltip').is_visible()
        for chart in await root.locator('[data-loss]').all():
            verify(json.loads(await chart.get_attribute('data-inspected')), await chart.get_attribute('data-loss'))
        same = await root.locator('[data-loss]').evaluate_all('es=>es.map(e=>e.dataset.inspectedStep)')
        assert len(set(same)) == 1
        await page.locator('#training-objective').screenshot(path='/tmp/training-losses-desktop.png')
        await flow.screenshot(path='/tmp/training-loss-hover.png')
        for width in [1600, 1440, 1024, 768, 390]:
            await page.set_viewport_size({'width': width, 'height': 1050})
            await page.wait_for_timeout(150)
            assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth'), width
            if width > 900:
                plots = await root.locator('.loss-chart-grid canvas').evaluate_all('es=>es.map(e=>e.getBoundingClientRect().top)')
                assert max(plots) - min(plots) < 1, (width, plots)
                videos = await page.locator('.mpc-scenes-grid .experiment-viewer').evaluate_all('es=>es.map(e=>e.getBoundingClientRect().top)')
                assert len(videos) == 4 and max(videos) - min(videos) < 1, (width, videos)
                w = (await page.locator('#training-objective').bounding_box())['width']
                expected = width - 280 if width >= 1200 else width * .85
                assert abs(w - expected) < 1
            if width in [1440, 390]:
                await page.locator('.mpc-scenes-grid').screenshot(path=f'/tmp/comparison-layout-{width}.png')
                await page.locator('#training-objective').screenshot(path=f'/tmp/training-losses-{width}.png')
        await canvas.focus()
        await canvas.press('Home')
        await canvas.press('ArrowRight')
        assert await root.locator('#loss-loss').get_attribute('data-inspected-step') == '100'
        assert 'step 100' in await root.locator('.loss-keyboard-status').inner_text()
        await flow.locator('canvas').scroll_into_view_if_needed()
        box = await flow.locator('canvas').bounding_box()
        await page.touchscreen.tap(box['x'] + box['width'] * .6, box['y'] + 100)
        await page.wait_for_timeout(100)
        assert await flow.locator('.loss-tooltip').is_visible()
        assert not errors, errors
        await browser.close()
        print('PASS original objective, exact raw values and local deviation, synchronized hover, formula links, keyboard/touch, five component and four video rows, responsive layout')

asyncio.run(main())
