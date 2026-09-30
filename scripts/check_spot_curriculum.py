"""Check the new curriculum UI, honest pending stages and native initial replay."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--use-angle=vulkan', '--enable-features=Vulkan',
            '--disable-vulkan-surface', '--enable-gpu', '--ignore-gpu-blocklist'])
        page = await browser.new_page(viewport={'width':1440, 'height':1000}, reduced_motion='reduce')
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.goto('http://localhost:8765/#controller-pretraining', wait_until='domcontentloaded')
        section = page.locator('#controller-pretraining')
        assert await section.locator('#pretraining-title').inner_text() == 'Low-level policy training'
        assert await section.locator('[data-loco-body]').count() == 3
        root = page.locator('#spot-curriculum')
        assert await root.locator('..').get_attribute('id') == 'controller-pretraining'
        await section.locator('[data-loco-body="spot_arm"]').click()
        await root.locator('[data-checkpoint-stage="initialization"]').wait_for()
        assert await root.is_visible()
        assert await root.locator('[data-curriculum-stages]').count() == 0
        assert await root.locator('[data-curriculum-phases] span').count() == 3
        assert await page.evaluate('window.CLEAR_BODY_CURRICULA.spot_arm.body') == 'spot_arm'
        arm_scene = await root.locator('.scratch-viewer').get_attribute('data-scene')
        await section.locator('[data-loco-source="recorded"]').click()
        assert await root.is_hidden()
        assert await section.locator('[data-loco-viewer="spot_arm"]').is_visible()
        await section.locator('[data-loco-body="spot"]').click()
        await page.wait_for_function('document.querySelector("#spot-curriculum").dataset.body==="spot"')
        await root.locator('[data-checkpoint-stage="initialization"]').wait_for()
        assert await root.locator('[data-curriculum-stages]').count() == 0
        assert await root.locator('[data-curriculum-phases] span').count() == 2
        assert await section.locator('[data-policy-recorded]').is_hidden()
        assert (await root.locator('.scratch-viewer').get_attribute('data-scene')).startswith('learning-spot-scratch-initialization-')
        assert await section.locator('.policy-sources').is_hidden()
        assert await root.locator('.scratch-viewer').get_attribute('data-scene') != arm_scene
        assert await root.locator('[data-curriculum-curves] canvas').count() == 3
        assert await page.evaluate('window.CLEAR_BODY_CURRICULA.spot.body') == 'spot'
        assert await root.locator('iframe').count() == 0
        assert '0 cumulative PPO updates' in await root.locator('[data-curriculum-caption]').inner_text()
        viewer = root.locator('.scratch-viewer')
        await viewer.locator('.launch').click()
        await viewer.locator('iframe.scene-ready').wait_for(timeout=90000)
        frame = await (await viewer.locator('iframe').element_handle()).content_frame()
        from check_learning_replay_support import FIND
        await frame.evaluate(FIND)
        await frame.wait_for_function("() => Object.values(testViewer.useSceneTree.getAll()).filter(n=>n.message?.type==='BatchedMeshesMessage').length===18")
        meshes = await frame.evaluate("() => Object.values(testViewer.useSceneTree.getAll()).filter(n=>n.message?.type==='BatchedMeshesMessage').map(n=>({positions:n.message.props.batched_positions.length,faces:n.message.props.faces.length/3}))")
        assert len(meshes)==18 and all(m['positions']==96 for m in meshes)
        assert sum(m['faces'] for m in meshes)==127509, 'Arm-free visual geometry must match physics'
        await viewer.scroll_into_view_if_needed()
        for time in (0, 3, 0):
            await viewer.evaluate("(v,time)=>v.querySelector('iframe').contentWindow.postMessage({type:'clear-playback-command',time,playing:false},'*')", time)
            await frame.wait_for_function('(time)=>Math.abs(Number(document.querySelector("input").value)-time)<.03', arg=time, timeout=15000)
        await root.screenshot(path='/tmp/spot-curriculum-desktop.png')
        for width in (768, 390):
            await page.set_viewport_size({'width':width, 'height':1000})
            await root.scroll_into_view_if_needed()
            assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert not errors, errors
        await browser.close()
    print('PASS distinct physical Spot/Spot+arm lineages, independent training curves, training lineage, pending states, exact update zero, native replay and responsive layout')


if __name__ == '__main__':
    asyncio.run(main())
