"""Validate object annotations and paired contact fields in native playback."""
import asyncio
from pathlib import Path
import numpy as np
import msgpack,zstandard
from playwright.async_api import async_playwright
from object_motion import sample_object, STARTS, ENDS
from contact_surface import paired_palm_field

FIND="""()=>{const root=document.querySelector('#root'),r=root[Object.keys(root).find(k=>k.startsWith('__reactContainer'))],q=[r,r?.stateNode?.current],seen=new Set();while(q.length){const f=q.pop();if(!f||seen.has(f))continue;seen.add(f);const v=f.memoizedProps?.value;if(v?.sceneTreeActions&&v?.useSceneTree){window.testViewer=v;return true;}q.push(f.child,f.sibling,f.alternate);}return false;}"""
SEEK="""t=>{const el=document.querySelector('[role=slider]');let f=el[Object.keys(el).find(k=>k.startsWith('__reactFiber'))];while(f){const p=f.memoizedProps;if(p&&p.step===.0001&&typeof p.onChange==='function'){p.onChange(t);return;}f=f.return;}throw new Error('Missing native timeline');}"""
NODES="""()=>Object.entries(window.testViewer.useSceneTree.getAll()).filter(([n,o])=>o?.message).map(([name,o])=>({name,props:o.message.props,visible:o.visibility,position:o.poseUpdateState?.position||o.message.props.position}))"""

def numeric_checks():
    for j in range(4):
        targets=[]
        for time in np.linspace(0,12,721):
            state=sample_object(j,time)
            if state['ghost_visible']:
                vector=np.array([np.cos(state['heading']),np.sin(state['heading'])])
                assert np.dot(state['target'][:2]-state['position'][:2],vector)>0
                targets.append(tuple(state['target']))
        assert set(targets)=={tuple(STARTS[j]),tuple(ENDS[j])}
    # Two well-separated palm projections must give two peaks, not one central field.
    x=np.linspace(-.5,.5,101);world=np.column_stack([x,np.full_like(x,-.5),np.zeros_like(x)])
    palms=np.array([[-.28,-.57,0],[.28,-.57,0]])
    heat,centers=paired_palm_field(world,palms,np.zeros(3),np.eye(3),np.full(3,.5))
    assert np.allclose(centers,[[-.28,-.5,0],[.28,-.5,0]])
    assert heat[22]>.99 and heat[78]>.99 and heat[50]<.01
    print('Both round-trip targets, aligned force directions and two distinct palm regions: PASS',flush=True)

async def main():
    numeric_checks()
    async with async_playwright() as p:
        browser=await p.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist'])
        page=await browser.new_page(viewport={'width':720,'height':560})
        for scene in ['objects','mpc-optimized','mpc-baseline']:
            await page.goto('http://localhost:8765/assets/viser/index.html?playbackPath=/assets/recordings/'+scene+'.viser')
            await page.locator('input').first.wait_for(timeout=60000)
            await page.locator('button').first.click();assert await page.evaluate(FIND)
            nodes=await page.evaluate(NODES)
            if scene=='objects':
                for j in range(4):
                    anchors=next(n for n in nodes if n['name']==f'/waypoints-{j}')
                    assert anchors['props']['point_size']==.045
                    assert any(n['name']==f'/lane-{j}-outline' for n in nodes)
                    assert any(n['name']==f'/force-{j}/fill' for n in nodes)
                positions=[]
                for t in [1.,4.]:
                    await page.evaluate(SEEK,t);await page.wait_for_timeout(150)
                    n=next(n for n in await page.evaluate(NODES) if n['name']=='/future-0')
                    assert n['visible']
                    packed=zstandard.ZstdDecompressor().decompress(Path('assets/recordings/objects.viser').read_bytes()[8:])
                    record=msgpack.unpackb(packed[8:8+int.from_bytes(packed[:8],'little')],raw=False)
                    positions.append([m['position'] for stamp,m in record['messages'] if stamp<=t and m.get('name')=='/future-0' and m['type']=='SetPositionMessage'][-1])
                assert positions[0]!=positions[1]
            else:
                assert len([n for n in nodes if '/contact-field/surface-' in n['name']])==6
                assert len([n for n in nodes if '/palm-contact-field/surface-' in n['name']])==6
                markers=next(n for n in nodes if n['name']=='/tracking/palm-centers')
                assert len(markers['props']['points'])==6
            await page.evaluate(SEEK,0);await page.wait_for_timeout(250)
            await page.add_style_tag(content='body *:not(:has(canvas)):not(canvas){visibility:hidden!important}canvas{visibility:visible!important}')
            await page.locator('canvas').last.screenshot(path='/tmp/'+scene+'-paired-poster.png')
            await page.evaluate(SEEK,4.2);await page.wait_for_timeout(250)
            await page.locator('canvas').last.screenshot(path='/tmp/'+scene+'-paired-active.png')
            print(scene+': native annotation checks PASS',flush=True)
        await browser.close()

if __name__=='__main__':asyncio.run(main())
