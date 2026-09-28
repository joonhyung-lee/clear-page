"""Capture local Viser previews; run the localhost preview server first."""
import argparse,asyncio,subprocess,tempfile
from pathlib import Path
from playwright.async_api import async_playwright
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--scenes',nargs='+',default=['structure-g1','structure-spot','structure-spot_arm','structure-husky','objects','scene-stairs','scene-steps','scene-slope','scene-maze'])
args=parser.parse_args()
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(headless=True,args=['--no-sandbox','--enable-unsafe-swiftshader'])
  for name in args.scenes:
   folder=Path(tempfile.mkdtemp(prefix='clear-preview-'))
   context=await b.new_context(viewport={'width':560,'height':440},device_scale_factor=1,record_video_dir=str(folder),record_video_size={'width':560,'height':440})
   page=await context.new_page()
   await page.goto('http://localhost:8765/assets/viser/index.html?playbackPath=/assets/recordings/'+name+'.viser')
   await page.locator('input').first.wait_for(timeout=30000)
   await page.wait_for_timeout(1500)
   # Keep the WebGL scene visible while hiding HTML notifications and controls.
   await page.add_style_tag(content='body *:not(:has(canvas)):not(canvas){visibility:hidden!important} canvas{visibility:visible!important}')
   await page.wait_for_timeout(500)
   await page.screenshot(path=str(ROOT/'assets/media'/f'{name}.png'),timeout=60000)
   await page.wait_for_timeout(8000)
   video=await page.video.path()
   await context.close()
   subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-sseof','-7','-i',str(video),'-an','-map_metadata','-1','-vf','fps=20','-c:v','libx264','-pix_fmt','yuv420p','-crf','22','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(ROOT/'assets/media'/f'{name}.mp4')],check=True)
   print(name,flush=True)
  await b.close()
asyncio.run(main())
