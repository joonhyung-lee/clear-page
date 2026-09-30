"""Verify native teaser geometry and generated ghost motion in the browser."""
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright
from browser_diagnostics import browser_diagnostics

ROOT=Path(__file__).resolve().parents[1]
FIND=r'''() => {
 const root=document.querySelector('#root');
 const key=Object.keys(root).find(k=>k.startsWith('__reactContainer'));
 const queue=[root[key],root[key]?.stateNode?.current],seen=new Set();
 while(queue.length){
  const f=queue.pop();if(!f||seen.has(f))continue;seen.add(f);
  const v=f.memoizedProps?.value;
  if(v?.useSceneTree?.getAll){window.testViewer=v;return true;}
  queue.push(f.child,f.sibling,f.alternate);
 }
 return false;
}'''


async def main():
    data=json.loads((ROOT/'assets/teaser-flow-data.js').read_text().split(' = ',1)[1].rstrip(';\n'))
    async with async_playwright() as p:
        browser=await p.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan',
            '--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist'])
        for label,selector in [('ordering','#ordering-context .viewer'),('flow','.maze-flow-viewer')]:
            page=await browser.new_page(viewport={'width':1440,'height':1050},reduced_motion='reduce')
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            try:
                async with browser_diagnostics(page,'teaser-'+label):
                    print('PROGRESS native teaser',label,'loading',flush=True)
                    await page.goto('http://localhost:8765/#'+('ordering-context' if label=='ordering' else 'flow-learning'),wait_until='domcontentloaded')
                    viewer=page.locator(selector);await viewer.scroll_into_view_if_needed()
                    await viewer.locator('.launch').click()
                    await viewer.locator('iframe.scene-ready').wait_for(timeout=90000)
                    frame=await (await viewer.locator('iframe').element_handle()).content_frame()
                    assert await frame.evaluate(FIND)
                    await viewer.evaluate("v=>v.querySelector('iframe').contentWindow.postMessage({type:'clear-playback-command',time:0,playing:false},'*')")
                    await frame.locator('.tabler-icon-player-play-filled').wait_for(state='attached',timeout=15000)
                    await frame.wait_for_function('()=>testViewer.mutable.current.messageQueue.length===0',timeout=30000)
                    await frame.wait_for_function(r'''() => {
                      const refs=testViewer.mutable.current.nodeRefFromName;
                      const names=Object.keys(testViewer.useSceneTree.getAll()).filter(n=>n.startsWith('/observed/part-'));
                      return names.length===148 && names.every(name=>{
                        let ready=false;refs[name]?.traverse(o=>{if(o.geometry?.index?.count>0&&o.material)ready=true;});
                        return ready && refs[name].visible;
                      });
                    }''',timeout=30000)
                    text=await frame.evaluate("()=>Object.values(testViewer.useSceneTree.getAll()).filter(n=>n.message?.type==='LabelMessage').map(n=>n.message.props.text)")
                    assert all(t in text for t in ['Stairs 1','Stairs 2','Slope','Object 0','Object 4','Start','Goal'])
                    if label=='flow':
                        original=await frame.evaluate("()=>testViewer.mutable.current.nodeRefFromName['/ghost-0-1'].position.toArray()")
                        # Repeated rewinds reuse native message objects. They must
                        # retain mounted refs, then apply both ghost poses again.
                        for time,index in [(6.,-1),(0,0),(0,0),(6.,-1)]:
                            expected=data['referenceFlow'][0]['states'][index][0]['poses']
                            expected=[expected[len(expected)//2][:2],expected[-1][:2]]
                            await viewer.evaluate("(v,time)=>v.querySelector('iframe').contentWindow.postMessage({type:'clear-playback-command',time,playing:false},'*')",time)
                            await frame.wait_for_function(r'''({time,expected})=>{
                              const refs=testViewer.mutable.current.nodeRefFromName;
                              const names=Object.keys(testViewer.useSceneTree.getAll()).filter(n=>n.startsWith('/observed/part-'));
                              return Math.abs(Number(document.querySelector('input').value)-time)<.02
                                && testViewer.mutable.current.messageQueue.length===0
                                && names.length===148 && names.every(n=>refs[n]?.visible)
                                && expected.every((xy,i)=>{
                                  const node=refs['/ghost-0-'+i];
                                  return node?.visible && Math.abs(node.position.x-xy[0])<1e-4
                                    && Math.abs(node.position.y-xy[1])<1e-4;
                                });
                            }''',arg=dict(time=time,expected=expected),timeout=15000)
                        expected=expected[-1]
                        assert any(abs(a-b)>1e-3 for a,b in zip(original[:2],expected))
                        ghosts=await frame.evaluate("()=>Object.keys(testViewer.useSceneTree.getAll()).filter(n=>n.startsWith('/ghost-'))")
                        assert sorted(ghosts)==[f'/ghost-{i}-{j}' for i in range(3) for j in range(2)]
                    # Lazy sections above can change height during startup.
                    # Bring the iframe back onscreen before checking rendered
                    # labels: Chromium throttles offscreen animation frames.
                    await viewer.scroll_into_view_if_needed()
                    await frame.wait_for_function(r'''() => {
                      const v=testViewer.mutable.current;
                      const root=v.nodeRefFromName[''];
                      if(!root || Math.abs(root.matrixWorld.elements[2]+1)>1e-5)return false;
                      const pose=v.nodePoseData['/label-0'].position;
                      const expected=root.position.clone().set(...pose).applyMatrix4(root.matrixWorld);
                      let ready=false;
                      v.scene.traverse(o=>{
                        if(!o._members)return;
                        for(const text of o._members.keys()){
                          if(text.text==='Object 0' && text.textRenderInfo
                             && text.position.distanceTo(expected)<1e-5)ready=true;
                        }
                      });
                      return ready;
                    }''',timeout=15000)
                    await viewer.screenshot(path=f'/tmp/teaser-native-{label}.png')
                    assert not errors,errors
                    print('PASS native teaser',label,'148 source meshes, five objects, two stairs, one slope'+(' and actual ghost seek' if label=='flow' else ''),flush=True)
            finally:
                await page.close()
        await browser.close()


asyncio.run(main())
