"""Re-render archived Viser scenes with the shared palette and original cameras."""
import argparse
import hashlib
import json
import subprocess
import tempfile
import copy
from pathlib import Path
from urllib.parse import urlsplit
import imageio_ffmpeg
from playwright.sync_api import sync_playwright
from recording_io import read_recording,write_recording,compact_buffers
from style_recorded_palette import restyle
from design_tokens import rgb
from check_research_visuals import FIND,SEEK

ROOT=Path(__file__).resolve().parents[1]

def presentation(record, zoom=1, mode='structure'):
    record=copy.deepcopy(record)
    target=next((m['look_at'] for _,m in record['messages'] if m['type']=='SetCameraLookAtMessage'),None)
    for _,message in record['messages']:
        name=message.get('name','')
        if message['type']=='MeshMessage' and ('/field/support-' in name or name.endswith('/contact-field')):
            message['props'].update(color=rgb('green',600),cast_shadow=False,receive_shadow=False)
        if target is not None and message['type']=='SetCameraPositionMessage':
            message['position']=[t+(p-t)/zoom for p,t in zip(message['position'],target)]
        if message['type']=='SetSceneNodeVisibilityMessage':
            name=message.get('name','')
            if '/field/support-' in name:message['visible']=mode=='traversability'
            elif name.endswith('/contact-field'):message['visible']=mode=='manipulation'
            elif name.startswith('/field/carpet/') or '/locomotion-shell-' in name:message['visible']=mode=='traversability'
            elif '/interaction-shell-' in name:message['visible']=mode=='manipulation'
            elif name.endswith('/kinematics') or name.endswith('/joints'):message['visible']=mode=='structure'
    # Some original skeletons relied on default visibility.
    for _,message in list(record['messages']):
        name=message.get('name','')
        if message['type'] in ['LineSegmentsMessage','PointCloudMessage'] and (name.endswith('/kinematics') or name.endswith('/joints')):
            record['messages'].append([0.,dict(type='SetSceneNodeVisibilityMessage',name=name,visible=mode=='structure')])
    record['messages'].sort(key=lambda pair:pair[0])
    return record

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenes',nargs='+',required=True)
    parser.add_argument('--base-url',default='http://localhost:8773')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-dir',type=Path,default=ROOT/'assets/recordings')
    parser.add_argument('--zoom',type=float,default=1)
    parser.add_argument('--scale',type=int,default=1)
    parser.add_argument('--width',type=int,help='Absolute output width; preserves the original aspect ratio')
    parser.add_argument('--embodiment-modes',action='store_true')
    parser.add_argument('--current-recording',action='store_true')
    parser.add_argument('--sample',type=float)
    parser.add_argument('--fps',type=int,help='Output frame rate; sample the original recorded clock')
    parser.add_argument('--modes',nargs='+',choices=['structure','traversability','manipulation'])
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    experiment_scenes={entry['scene'] for name in ('maze-experiments.json','manipulation-experiments.json')
                       for entry in json.loads((ROOT/'assets'/name).read_text())}
    if any(scene in experiment_scenes for scene in args.scenes):
        raise ValueError('Experiment recordings are excluded from the palette refresh')
    with sync_playwright() as pw:
        browser=pw.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist'])
        jobs=[(scene,scene,'structure') for scene in args.scenes]
        if args.modes:
            jobs=[(scene,source,mode) for scene,source,mode in jobs if 'structure' in args.modes]
        if args.embodiment_modes or args.modes:
            modes=args.modes or ('traversability','manipulation')
            jobs += [(f'affordance-{mode}-{scene.removeprefix("structure-")}',scene,mode)
                     for scene in args.scenes if scene.startswith('structure-')
                     for mode in modes if mode!='structure']
        for scene,source_scene,mode in jobs:
            if scene.startswith(('teaser','tldr')): raise ValueError('Teaser is excluded')
            old=ROOT/f'assets/media/{source_scene}.mp4'
            if source_scene.startswith('highlight-'):
                old=ROOT/f'assets/media/{source_scene.removeprefix("highlight-")}.mp4'
            reader=imageio_ffmpeg.read_frames(str(old));meta=next(reader);reader.close()
            source=args.source_dir/f'{source_scene}.viser'
            record,buffers=read_recording(source)
            if not args.current_recording:record,buffers=restyle(record,buffers)
            zoom=args.zoom if source_scene=='objects' or source_scene.startswith('scene-') else 1
            record=presentation(record,zoom,mode)
            record,buffers=compact_buffers(record,buffers)
            fps=args.fps or meta['fps'];frames=round(meta['duration']*fps)
            if source_scene.startswith('highlight-'):
                frames=round(record['durationSeconds']*fps)
            size=tuple(value*args.scale for value in meta['size'])
            if args.width:size=(args.width,2*round(args.width*meta['size'][1]/meta['size'][0]/2))
            with tempfile.TemporaryDirectory(prefix='clear-palette-') as tmp:
                replay=Path(tmp)/'render.viser';write_recording(replay,record,buffers);raw=replay.read_bytes()
                page=browser.new_page(viewport=dict(zip(('width','height'),size)))
                def serve(route):
                    if urlsplit(route.request.url).path=='/palette.viser':
                        route.fulfill(body=raw,content_type='application/octet-stream')
                    else:
                        route.continue_()
                page.route('**/*',serve)
                page.goto(args.base_url+'/assets/viser/index.html?playbackPath=/palette.viser')
                page.locator('input').first.wait_for(timeout=90000)
                page.wait_for_function(FIND,timeout=90000)
                pause=page.locator('.tabler-icon-player-pause-filled')
                if pause.count():pause.locator('..').click()
                page.add_style_tag(content='body *:not(:has(canvas)):not(canvas){visibility:hidden!important}canvas{visibility:visible!important}')
                dest=Path(tmp)/(scene+'.mp4')
                proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','image2pipe','-framerate',str(fps),'-vcodec','png','-i','-','-an','-map_metadata','-1','-c:v','libx264','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],stdin=subprocess.PIPE)
                try:
                    for frame in range(1 if args.sample is not None else frames):
                        page.evaluate(SEEK,min(args.sample if args.sample is not None else frame/fps,record['durationSeconds']))
                        page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                        picture=page.screenshot(type='png',timeout=30000)
                        proc.stdin.write(picture)
                        if frame==0:page.screenshot(path=str(args.output/(scene+'.png')))
                        if frame%120==0:print(scene,frame,'/',frames,flush=True)
                finally:
                    proc.stdin.close();code=proc.wait();page.close()
                if code:raise RuntimeError('Video encoding failed')
                target=args.output/dest.name;target.write_bytes(dest.read_bytes())
                (args.output/(scene+'.viser')).write_bytes(raw)
                report=dict(scene=scene,sourceScene=source_scene,sourceSHA256=hashlib.sha256(source.read_bytes()).hexdigest(),currentRecording=args.current_recording,fps=fps,frames=1 if args.sample is not None else frames,size=size,zoom=zoom,mode=mode,robotMaterials='original recorded colors',palette='design-tokens.json',motion='archived poses; unchanged')
                (args.output/(scene+'.json')).write_text(json.dumps(report,indent=2)+'\n')
                print('Rendered',target.name,flush=True)
        browser.close()

if __name__=='__main__':main()
