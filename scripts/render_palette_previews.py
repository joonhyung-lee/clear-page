"""Re-render archived Viser scenes with the shared palette and original cameras."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
import imageio_ffmpeg
from playwright.sync_api import sync_playwright
from recording_io import read_recording,write_recording,compact_buffers
from style_recorded_palette import restyle
from check_research_visuals import FIND,SEEK

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenes',nargs='+',required=True)
    parser.add_argument('--base-url',default='http://localhost:8773')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    experiment_scenes={entry['scene'] for name in ('maze-experiments.json','manipulation-experiments.json')
                       for entry in json.loads((ROOT/'assets'/name).read_text())}
    if any(scene in experiment_scenes for scene in args.scenes):
        raise ValueError('Experiment recordings are excluded from the palette refresh')
    with sync_playwright() as pw:
        browser=pw.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist'])
        for scene in args.scenes:
            if scene.startswith(('teaser','tldr')): raise ValueError('Teaser is excluded')
            old=ROOT/f'assets/media/{scene}.mp4'
            reader=imageio_ffmpeg.read_frames(str(old));meta=next(reader);reader.close()
            source=ROOT/f'assets/recordings/{scene}.viser'
            record,buffers=read_recording(source);record,buffers=restyle(record,buffers)
            record,buffers=compact_buffers(record,buffers)
            fps=meta['fps'];frames=round(meta['duration']*fps)
            with tempfile.TemporaryDirectory(prefix='clear-palette-') as tmp:
                replay=Path(tmp)/'render.viser';write_recording(replay,record,buffers);raw=replay.read_bytes()
                page=browser.new_page(viewport=dict(zip(('width','height'),meta['size'])))
                def serve(route):
                    if urlsplit(route.request.url).path=='/palette.viser':
                        route.fulfill(body=raw,content_type='application/octet-stream')
                    else:
                        route.continue_()
                page.route('**/*',serve)
                page.goto(args.base_url+'/assets/viser/index.html?playbackPath=/palette.viser')
                page.locator('input').first.wait_for(timeout=90000)
                if not page.evaluate(FIND):raise RuntimeError('Native replay is not ready')
                pause=page.locator('.tabler-icon-player-pause-filled')
                if pause.count():pause.locator('..').click()
                page.add_style_tag(content='body *:not(:has(canvas)):not(canvas){visibility:hidden!important}canvas{visibility:visible!important}')
                dest=Path(tmp)/(scene+'.mp4')
                proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','image2pipe','-framerate',str(fps),'-vcodec','mjpeg','-i','-','-an','-map_metadata','-1','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],stdin=subprocess.PIPE)
                try:
                    for frame in range(frames):
                        page.evaluate(SEEK,min(frame/fps,record['durationSeconds']))
                        page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                        picture=page.screenshot(type='jpeg',quality=95,timeout=30000)
                        proc.stdin.write(picture)
                        if frame==0:page.screenshot(path=str(args.output/(scene+'.png')))
                        if frame%120==0:print(scene,frame,'/',frames,flush=True)
                finally:
                    proc.stdin.close();code=proc.wait();page.close()
                if code:raise RuntimeError('Video encoding failed')
                target=args.output/dest.name;target.write_bytes(dest.read_bytes())
                report=dict(scene=scene,sourceSHA256=hashlib.sha256(source.read_bytes()).hexdigest(),fps=fps,frames=frames,size=meta['size'],palette='design-tokens.json',motion='archived poses; unchanged')
                (args.output/(scene+'.json')).write_text(json.dumps(report,indent=2)+'\n')
                print('Rendered',target.name,flush=True)
        browser.close()

if __name__=='__main__':main()
