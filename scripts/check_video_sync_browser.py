"""Exercise both body rows, real video decoders, measured EEF plots and native 3D."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
SAMPLE='''v=>{const m=v.querySelector('.preview-video'),e=v.querySelector('.ego-inset video');return {main:m.currentTime,ego:e.currentTime,paused:e.paused,quality:e.getVideoPlaybackQuality().totalVideoFrames,seeks:e._seekCount||0,ready:e.readyState}}'''


def main():
 results={}
 with sync_playwright() as p:
  browser=p.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist'])
  page=browser.new_page(viewport={'width':1600,'height':1100},reduced_motion='reduce')
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://localhost:8765',wait_until='domcontentloaded')
  assert page.locator('#method-execution .pushing-gallery').count()==0
  for name,root_selector,slider_selector,play_selector in [
   ('g1','#mpc-process','#mpc-process-update','#mpc-process-play'),
   ('spot','#spot-process','#spot-process input','[data-spot-play]'),
  ]:
   root=page.locator(root_selector);root.scroll_into_view_if_needed()
   page.wait_for_function('(selector)=>document.querySelector(selector).dataset.elapsed!==undefined',arg=root_selector)
   panels=root.locator('.execution-controller-panels>figure')
   boxes=panels.evaluate_all('nodes=>nodes.map(n=>{const b=n.getBoundingClientRect();return {x:b.x,y:b.y,width:b.width};})')
   assert len(boxes)==4 and max(b['y'] for b in boxes)-min(b['y'] for b in boxes)<2,boxes
   assert all(boxes[i+1]['x']>=boxes[i]['x']+boxes[i]['width'] for i in range(3)),boxes
   assert root.locator('.execution-controller').evaluate_all("nodes=>nodes.map(n=>document.getElementById(n.getAttribute('aria-labelledby')).textContent)")==['MPC w/ optimization (ours)','MPC (naive)']
   duration=15 if name=='g1' else 21.78
   def seek(t):
    page.locator(slider_selector).fill(str(t/duration))
   views=root.locator('.execution-body-viewer')
   seek(4)
   page.wait_for_function('selector=>[...document.querySelectorAll(selector+" .execution-body-viewer video")].every(v=>v.readyState>=2&&Math.abs(v.currentTime-4)<.15)',arg=root_selector)
   for viewer in views.all():
    viewer.evaluate("v=>{const e=v.querySelector('.ego-inset video');e._seekCount=0;e.addEventListener('seeking',()=>e._seekCount++);}")
   root.locator(play_selector).click();page.wait_for_timeout(600)
   samples=[[] for _ in range(2)]
   for _ in range(6):
    page.wait_for_timeout(200)
    for i,view in enumerate(views.all()):samples[i].append(view.evaluate(SAMPLE))
   for i,values in enumerate(samples):
    assert values[-1]['quality']>values[0]['quality'],(name,i,'Ego does not decode',values)
    assert all(not r['paused'] for r in values),(name,i,'Ego stopped',values)
    assert max(abs(r['main']-r['ego']) for r in values)<.35,(name,i,'Ego drift',values)
    assert values[-1]['seeks']-values[0]['seeks']<=2,(name,i,'Ego repeatedly seeks',values)
   results[name+' video']=samples
   root.locator(play_selector).click();seek(3)
   if name=='spot':
    plot=root.locator('[data-spot-process="optimized"] canvas')
    before=plot.get_attribute('data-eef')
    root.locator('[data-spot-view="2d"]').click();assert plot.get_attribute('data-eef')==before
    root.locator('[data-spot-view="3d"]').click();assert plot.get_attribute('data-eef')==before
    pixels=plot.evaluate('c=>c.toDataURL()');plot.focus();plot.press('ArrowLeft');assert plot.evaluate('c=>c.toDataURL()')!=pixels
    plot.press('Home');assert plot.evaluate('c=>c.toDataURL()')==pixels
    seek(18)
    page.wait_for_function("[...document.querySelectorAll('#spot-process [data-clock-group=spot] video')].every(v=>v.readyState>=2&&Math.abs(v.currentTime-Math.min(18,v.duration-.04))<.15)")
    assert abs(float(root.locator('[data-spot-process="baseline"] canvas').get_attribute('data-time'))-10.5)<1e-6
    assert 'Toppled' in root.locator('[data-spot-process="baseline"] .mpc-recording-status').inner_text()
    seek(3)
   # The row clock continues to drive the rendered native replay and Ego RGB.
   for viewer in views.all():
    scene=viewer.get_attribute('data-scene')
    viewer.locator('.launch').click();viewer.locator('iframe.scene-ready').wait_for(timeout=120000)
    seek(2)
    page.wait_for_function('([v,t])=>Math.abs(v._lastReplayTime-t)<.15',arg=[viewer.element_handle(),2])
    page.wait_for_function('v=>Math.abs(v.querySelector(".ego-inset video").currentTime-2)<.15',arg=viewer.element_handle())
    root.locator(play_selector).click();page.wait_for_timeout(1000)
    state=viewer.evaluate('v=>({time:v._lastReplayTime,ego:v.querySelector(".ego-inset video").currentTime})')
    assert state['time']>2.5 and abs(state['time']-state['ego'])<.4,(scene,state)
    root.locator(play_selector).click();seek(1)
    page.wait_for_function('v=>Math.abs(v._lastReplayTime-1)<.15',arg=viewer.element_handle())
    viewer.locator('.viewer-tools').click()
    page.wait_for_function('v=>[...v.querySelectorAll("video")].every(m=>m.paused&&Math.abs(m.currentTime-1)<.15)',arg=viewer.element_handle())
    seek(4)
    page.wait_for_function('v=>Math.abs(v.querySelector(".preview-video").currentTime-4)<.15',arg=viewer.element_handle())
    print('PASS',scene,'video/Ego/native seek and return to preview',flush=True)
   root.screenshot(path='/tmp/clear-'+name+'-body-row.png')
   # Scrolling away pauses this body's clock and decoders.
   root.locator(play_selector).click();page.wait_for_timeout(200);page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(400)
   stopped=root.get_attribute('data-elapsed');page.wait_for_timeout(300)
   assert root.get_attribute('data-elapsed')==stopped
   assert all(v.evaluate("v=>v.querySelector('.ego-inset video').paused") for v in views.all())
   root.scroll_into_view_if_needed();page.wait_for_timeout(500);assert root.get_attribute('data-elapsed')!=stopped
   root.locator(play_selector).click()
  # A Spot seek must never rewind the G1 record.
  g1=page.locator('#mpc-process').get_attribute('data-elapsed')
  page.locator('#spot-process input').fill('.25');assert page.locator('#mpc-process').get_attribute('data-elapsed')==g1
  for width in [1600,768,390]:
   page.set_viewport_size({'width':width,'height':1000})
   assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
   for selector in ['#mpc-process','#spot-process']:
    row=page.locator(selector+' .execution-process-grid')
    dims=row.evaluate('e=>({client:e.clientWidth,scroll:e.scrollWidth})')
    assert dims['scroll']>=dims['client']
    row.evaluate('e=>e.scrollLeft=e.scrollWidth')
    assert page.locator(selector+' .execution-controller').count()==2
  assert not errors,errors
  browser.close()
 (Path('/tmp')/'clear-video-sync-browser.json').write_text(json.dumps(results,indent=2)+'\n')
 print('PASS two body rows, four views each, synchronized actual decoders and native meshes, independent clocks and mobile scrolling')


if __name__=='__main__':main()
