"""Measure real decoder clocks in all four controller tiles and enlarged players."""
import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
FIND_VIEWER="""()=>{const root=document.querySelector('#root'),key=Object.keys(root).find(k=>k.startsWith('__reactContainer')),stack=[root[key],root[key]?.stateNode?.current],seen=new Set();while(stack.length){const f=stack.pop();if(!f||seen.has(f))continue;seen.add(f);const v=f.memoizedProps?.value;if(v?.useSceneTree&&v?.mutable?.current?.cameraControl){window.chaseTestViewer=v;return true;}stack.push(f.child,f.sibling,f.alternate);}return false;}"""
CAMERA_STATE="""()=>{const v=window.chaseTestViewer,m=v.mutable.current,q=v.useSceneTree.get('').wxyz,rotation=m.camera.quaternion.clone().set(q[1],q[2],q[3],q[0]),up=m.camera.position.clone().set(0,0,1).applyQuaternion(rotation),n=m.nodeRefFromName['/body-1'];n.updateWorldMatrix(true,false);const base=n.getWorldPosition(m.camera.position.clone());base.addScaledVector(up,-base.dot(up));return {base:base.toArray(),eye:m.cameraControl.getPosition(m.camera.position.clone()).sub(base).toArray(),target:m.cameraControl.getTarget(m.camera.position.clone()).sub(base).toArray()};}"""
SAMPLE='''v=>{const m=v.querySelector('video'),e=v.querySelector('.ego-inset video');return {main:m.currentTime,ego:e.currentTime,paused:e.paused,rate:e.playbackRate,seeks:e._seekCount||0,quality:e.getVideoPlaybackQuality().totalVideoFrames,dropped:e.getVideoPlaybackQuality().droppedVideoFrames,ready:e.readyState}}'''

def check_body_chase(page,viewer):
 frame=viewer.locator('iframe').element_handle().content_frame()
 frame.wait_for_function(FIND_VIEWER)
 def seek(t):
  viewer.evaluate("(v,t)=>v.querySelector('iframe').contentWindow.postMessage({type:'clear-playback-command',time:t,playing:false},'*')",t)
  page.wait_for_function("([v,t])=>Math.abs(v._lastReplayTime-t)<.08",arg=[viewer.element_handle(),t])
  frame.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
  return frame.evaluate(CAMERA_STATE)
 def close(a,b):return max(abs(x-y) for x,y in zip(a,b))<.025
 first=seek(2);later=seek(10)
 assert sum((a-b)**2 for a,b in zip(first['base'],later['base']))>.01
 assert close(first['eye'],later['eye']) and close(first['target'],later['target']),(first,later)
 box=frame.locator('canvas').first.bounding_box();x=box['x']+box['width']*.5;y=box['y']+box['height']*.5
 page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+45,y+25,steps=8);page.mouse.up();page.wait_for_timeout(250)
 orbit=frame.evaluate(CAMERA_STATE);assert not close(orbit['eye'],later['eye']),'Drag must change the camera'
 moved=seek(15)
 assert close(orbit['eye'],moved['eye']) and close(orbit['target'],moved['target']),'Body chase must preserve the user camera'
 rewind=seek(4)
 assert close(moved['eye'],rewind['eye']) and close(moved['target'],rewind['target']),'Backward seek must retain the relative camera'
 frame.evaluate('()=>window.chaseTestViewer.mutable.current.resetCameraPose(false)')
 frame.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
 reset=frame.evaluate(CAMERA_STATE)
 assert close(reset['eye'],first['eye']) and close(reset['target'],first['target']),'Reset must return to the current body, not the initial world position'
 print('PASS native G1 chase follows body, preserves drag and supports backward seeks',flush=True)
 return [first,later,orbit,moved,rewind]

def measure(page,viewer,seconds=3):
 rows=[]
 for _ in range(int(seconds*5)):
  page.wait_for_timeout(200);rows.append(viewer.evaluate(SAMPLE))
 return rows

def check(rows,label):
 assert rows[-1]['quality']>rows[0]['quality'],(label,'no decoded frames',rows)
 assert all(not r['paused'] for r in rows[3:]),(label,'Ego paused',rows)
 assert max(abs(r['main']-r['ego']) for r in rows[3:])<.3,(label,'drift',rows)
 assert rows[-1]['seeks']-rows[0]['seeks']<=2,(label,'repeated seek',rows)
 print('PASS',label,'max drift',round(max(abs(r['main']-r['ego']) for r in rows[3:]),3),flush=True)

def main():
 results={}
 with sync_playwright() as p:
  b=p.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist'])
  page=b.new_page(viewport={'width':1440,'height':1000})
  page.goto('http://localhost:8765',wait_until='domcontentloaded')
  galleries=page.locator('#method-execution .controller-gallery')
  for group in range(2):
   gallery=galleries.nth(group)
   for body in range(2):
    tile=gallery.locator('.media-tile').nth(body);scene=tile.get_attribute('data-scene')
    tile.scroll_into_view_if_needed();page.wait_for_timeout(1800);tile.evaluate("v=>v.scrollIntoView({block:'center'})");page.mouse.move(2,2);page.wait_for_timeout(500)
    tile.evaluate("v=>{const m=v.querySelector('video'),e=v.querySelector('.ego-inset video');e._seekCount=0;e.addEventListener('seeking',()=>e._seekCount++);m.preload='auto';m.play();}")
    page.wait_for_timeout(1500)
    rows=measure(page,tile);results[scene+' tile']=rows;check(rows,scene+' tile')
    tile.focus();tile.press('Enter');viewer=gallery.locator('.focus-viewer');page.wait_for_timeout(700)
    viewer.evaluate("v=>{const m=v.querySelector('video'),e=v.querySelector('.ego-inset video');e._seekCount=0;e.addEventListener('seeking',()=>e._seekCount++);m.currentTime=2;m.playbackRate=2;m.play();}")
    page.wait_for_timeout(600);rows=measure(page,viewer);results[scene+' expanded 2x']=rows;check(rows,scene+' expanded 2x')
    viewer.evaluate("v=>v.querySelector('video').pause()")
    page.wait_for_timeout(300);assert viewer.evaluate("v=>v.querySelector('.ego-inset video').paused")
    viewer.locator('.launch').click();viewer.locator('iframe.scene-ready').wait_for(timeout=90000)
    viewer.evaluate("v=>v.querySelector('iframe').contentWindow.postMessage({type:'clear-playback-command',time:2,playing:true},'*')")
    page.wait_for_timeout(1000)
    native=[]
    for i in range(15):
     page.wait_for_timeout(200)
     native.append(viewer.evaluate("v=>{const e=v.querySelector('.ego-inset video');return {time:v._lastReplayTime,ego:e.currentTime,paused:e.paused,seeks:e._seekCount,quality:e.getVideoPlaybackQuality().totalVideoFrames}}"))
    assert native[-1]['quality']>native[0]['quality'],(scene,'native no frames',native)
    assert max(abs(r['time']-r['ego']) for r in native)<.35,(scene,'native drift',native)
    assert native[-1]['seeks']-native[0]['seeks']<=2,(scene,'native seeks',native)
    results[scene+' native']=native;print('PASS',scene,'native continuous Ego',flush=True)
    viewer.evaluate("v=>v.querySelector('iframe').contentWindow.postMessage({type:'clear-playback-command',time:4,playing:false},'*')")
    page.wait_for_timeout(600)
    state=viewer.evaluate("v=>({time:v.querySelector('.ego-inset video').currentTime,paused:v.querySelector('.ego-inset video').paused})")
    assert state['paused'] and abs(state['time']-4)<.08,(scene,'native paused seek',state)
    if scene=='mpc-g1-native':results['native G1 body chase']=check_body_chase(page,viewer)
    viewer.locator('.viewer-tools').click();page.wait_for_timeout(500)
    viewer.evaluate("v=>{v.querySelector('video').currentTime=3;v.querySelector('video').play();}")
    page.wait_for_timeout(400);check(measure(page,viewer,1.5),scene+' return to video')
    page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(600)
    assert viewer.evaluate("v=>v.querySelector('.ego-inset video').paused"),(scene,'offscreen Ego keeps playing')
    viewer.evaluate("v=>v.scrollIntoView({block:'center'})");page.wait_for_timeout(500)
    check(measure(page,viewer,1.5),scene+' viewport resume')
    gallery.locator('.focus-close').click();page.mouse.move(2,2)
  # A first paused seek must load the Ego decoder, even without a play event.
  page.goto('http://localhost:8765',wait_until='domcontentloaded')
  page.evaluate("document.dispatchEvent(new CustomEvent('clear-mpc-clock',{detail:{time:8,playing:false,speed:2}}))")
  page.wait_for_timeout(1500)
  external=page.locator('[data-execution-clock]').evaluate_all("vs=>vs.map(v=>({main:v.querySelector('video').currentTime,ego:v.querySelector('.ego-inset video').currentTime,paused:v.querySelector('.ego-inset video').paused,ready:v.querySelector('.ego-inset video').readyState}))")
  assert all(v['ready']>=2 and abs(v['main']-8)<.05 and abs(v['ego']-8)<.05 and v['paused'] for v in external),external
  results['paused external timeline']=external
  print('PASS first paused external seek loads and aligns both Ego decoders',flush=True)
  b.close()
 Path('/tmp/clear-video-sync-browser.json').write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__':main()
