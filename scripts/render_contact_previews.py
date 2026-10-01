"""Render unchanged native recordings from a side view with saved palm anchors.

Time is prescribed at 20 fps. Native messages, candidate forecasts and palm
markers are used without modifying the robot motion or reported outcomes.
"""
import argparse, subprocess, tempfile
from pathlib import Path
import imageio_ffmpeg
from playwright.sync_api import sync_playwright
from check_research_visuals import FIND, SEEK
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--scenes',nargs='+',default=['mpc-optimized','mpc-baseline']);a=p.parse_args()
CAMERA='''()=>{const v=testViewer,m=v.mutable.current,q=v.useSceneTree.get("").wxyz,r=m.camera.quaternion.clone().set(q[1],q[2],q[3],q[0]);const eye=m.camera.position.clone().set(2.6,-1.8,1.5).applyQuaternion(r),at=m.camera.position.clone().set(0,.5,.7).applyQuaternion(r);m.cameraControl.setLookAt(...eye.toArray(),...at.toArray(),false)}'''
with sync_playwright() as pw:
 b=pw.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist'])
 for scene in a.scenes:
  page=b.new_page(viewport={'width':640,'height':480});page.goto('http://localhost:8765/assets/viser/index.html?playbackPath=/assets/recordings/'+scene+'.viser')
  page.locator('input').first.wait_for(timeout=60000);assert page.evaluate(FIND)
  page.evaluate(SEEK,0);page.wait_for_timeout(200);page.evaluate(CAMERA)
  page.add_style_tag(content='body *:not(:has(canvas)):not(canvas){visibility:hidden!important} canvas{visibility:visible!important}')
  duration=14 if scene=='mpc-optimized' else 40;fps=20
  tmp=Path(tempfile.mktemp(prefix='clear-contact-',suffix='.mp4'))
  proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','image2pipe','-framerate',str(fps),'-vcodec','png','-i','-','-an','-map_metadata','-1','-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(tmp)],stdin=subprocess.PIPE)
  try:
   for i in range(duration*fps):
    page.evaluate(SEEK,i/fps)
    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    frame=page.screenshot(timeout=15000);proc.stdin.write(frame)
    if i==0:(ROOT/'assets/media'/f'{scene}-contact.png').write_bytes(frame)
    if i%100==0:print(scene,i,'/',duration*fps,flush=True)
  finally:proc.stdin.close();code=proc.wait();page.close()
  assert code==0;tmp.replace(ROOT/'assets/media'/f'{scene}-contact.mp4')
 b.close()
