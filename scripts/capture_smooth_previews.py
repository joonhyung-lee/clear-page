"""Render prescribed playback times, avoiding real-time screen-recording jitter."""
import argparse,subprocess,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
import imageio_ffmpeg
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--scenes',nargs='+',required=True);p.add_argument('--fps',type=int,default=60);a=p.parse_args()
with sync_playwright() as pw:
 for scene in a.scenes:
  browser=pw.chromium.launch(headless=True,args=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist'])
  page=browser.new_page(viewport={'width':560,'height':440},device_scale_factor=1)
  page.goto('http://localhost:8765/assets/viser/index.html?playbackPath=/assets/recordings/'+scene+'.viser')
  timeline=page.locator('input').first;timeline.wait_for(timeout=60000)
  page.locator('button').first.click()
  timeline.fill('0');timeline.press('Tab');page.wait_for_timeout(150)
  first=timeline.input_value();page.wait_for_timeout(150);assert timeline.input_value()==first,'Playback must be paused'
  page.add_style_tag(content='body *:not(:has(canvas)):not(canvas){visibility:hidden!important} canvas{visibility:visible!important}')
  duration=12
  output=Path(tempfile.mktemp(prefix='clear-smooth-',suffix='.mp4'))
  proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','image2pipe','-framerate',str(a.fps),'-vcodec','png','-i','-','-an','-map_metadata','-1','-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(output)],stdin=subprocess.PIPE)
  try:
   for i in range(duration*a.fps):
    # Use the player slider callback. The formatted number input rounds to 0.1 s.
    page.evaluate("""t=>{const el=document.querySelector('[role=slider]');let f=el[Object.keys(el).find(k=>k.startsWith('__reactFiber'))];while(f){const p=f.memoizedProps;if(p&&p.step===0.0001&&typeof p.onChange==='function'){p.onChange(t);return;}f=f.return;}throw new Error('Playback slider callback missing');}""",i/a.fps)
    page.evaluate('()=>Promise.race([new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))),new Promise((_,reject)=>setTimeout(()=>reject(new Error("Renderer frame timeout")),10000))])')
    frame=page.screenshot(timeout=15000)
    if i==0:(root/'assets/media'/f'{scene}.png').write_bytes(frame)
    proc.stdin.write(frame)
    if i%60==0:print(scene,i,'/',duration*a.fps,flush=True)
  finally:proc.stdin.close();code=proc.wait();page.close()
  assert code==0
  output.replace(root/'assets/media'/f'{scene}.mp4');print('completed',scene,flush=True)
  browser.close()
