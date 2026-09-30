"""Check measured data provenance in the UI and synchronized checkpoint inspection."""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]


async def main():
    text = (ROOT/'assets/policy-evaluation-data.js').read_text()
    evidence = json.loads(text.split('=', 1)[1].strip().rstrip(';'))
    assert set(evidence['bodies']) == {'g1', 'spot', 'spot_arm'}
    assert all(body['complete'] for body in evidence['bodies'].values())
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 1050}, reduced_motion='reduce')
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.goto('http://localhost:8765/', wait_until='domcontentloaded')
        root = page.locator('#policy-evaluation')
        for body in ['g1', 'spot', 'spot_arm']:
            await page.locator(f'[data-loco-body="{body}"]').evaluate('(b)=>b.click()')
            if body == 'g1':
                await page.locator('[data-loco-source="recorded"]').evaluate('(b)=>b.click()')
            assert await root.get_attribute('data-mode') == 'measured'
            assert await root.get_attribute('data-body') == body
            assert await root.locator('[data-eval-example]').is_hidden()
            assert await root.locator('polyline').count() == 3
            assert '60 episodes per checkpoint' in await root.locator('.eval-disclosure').inner_text()
            rows = evidence['bodies'][body]['rows']
            svg = root.locator('figure svg').first
            await svg.focus()
            for key, index in [('Home', 0), ('ArrowRight', 1), ('End', len(rows)-1)]:
                await svg.press(key)
                # Lazy loading the same body must not reset an inspected point.
                await page.locator('#controller-pretraining').evaluate(
                    "n=>n.dispatchEvent(new CustomEvent('policy-body-change', {detail:{body:n.dataset.body,recorded:n.dataset.source==='recorded'}}))")
                row = rows[index]
                for figure in await root.locator('figure').all():
                    point = json.loads(await figure.get_attribute('data-inspected'))
                    assert point['source'] == 'measured'
                    assert point['update'] == row['update']
                    for field in ['mean', 'low', 'high']:
                        assert point[field] == row[point['metric']][field]
                    assert 'example' not in await figure.locator('.unit').inner_text()
            await svg.evaluate('(n)=>n.blur()')
            await root.screenshot(path=f'/tmp/clear-policy-measured-{body}.png')
            # Real updates are nonuniform. Hover should pick the nearest saved
            # update, not an evenly spaced invented sample.
            box = await svg.bounding_box()
            await page.mouse.move(box['x']+box['width']*.5, box['y']+box['height']*.5)
            points = [json.loads(await f.get_attribute('data-inspected')) for f in await root.locator('figure').all()]
            assert len({p['update'] for p in points}) == 1
            assert points[0]['update'] in {r['update'] for r in rows}
        await page.locator('[data-loco-source="recorded"]').evaluate('(b)=>b.click()')
        assert await root.get_attribute('data-mode') == 'unmeasured'
        assert await root.locator('polyline').count() == 0
        assert await root.locator('.value').all_text_contents() == ['—']*3
        await page.locator('[data-loco-source="new"]').evaluate('(b)=>b.click()')
        assert await root.get_attribute('data-mode') == 'measured'
        await page.set_viewport_size({'width': 390, 'height': 844})
        bounds = [await f.bounding_box() for f in await root.locator('figure').all()]
        assert all(b['y'] >= a['y']+a['height'] for a, b in zip(bounds, bounds[1:]))
        assert all(b['x'] >= 0 and b['x']+b['width'] <= 391 for b in bounds)
        assert not errors, errors
        await browser.close()
    print('PASS measured evaluation for three bodies, exact values and bands, initial comparison, synchronized inspection, lineage separation, mobile layout')


if __name__ == '__main__':
    asyncio.run(main())
