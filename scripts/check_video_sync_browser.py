"""Measure real decoder clocks in all four controller tiles and enlarged players."""
import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
SAMPLE='''v=>{const m=v.querySelector('video'),e=v.querySelector('.ego-inset video');return {main:m.currentTime,ego:e.currentTime,paused:e.paused,rate:e.playbackRate,seeks:e._seekCount||0,quality:e.getVideoPlaybackQuality().totalVideoFrames,dropped:e.getVideoPlaybackQuality().droppedVideoFrames,ready:e.readyState}}'''

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
