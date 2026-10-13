"""Capture native Viser checkpoint videos with an illustrative radial arrangement.

One recorded motion is replayed in four directions on a representative terrain.
Display rotations/translations do not represent new multi-agent simulations.
Original recordings and measured curves remain unchanged. Soft terrain colors
and thin black robot outlines improve legibility. Outputs replace videos atomically.
"""
import argparse
import copy
import hashlib
import fcntl
import io
import json
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import imageio_ffmpeg
import numpy as np
import trimesh
from PIL import Image
from playwright.sync_api import sync_playwright
from recording_io import read_recording, write_recording, compact_buffers
from policy_matrix_scene import arrange, MATRIX, annotate
from policy_tracking_overlay import TrackingReplay
from design_tokens import font_path
from style_recorded_palette import restyle
from check_research_visuals import FIND, SEEK

ROOT = Path(__file__).resolve().parents[1]
CAMERA = '''({eye,target})=>{
 const v=testViewer,m=v.mutable.current,c=m.camera,q=v.useSceneTree.get('').wxyz;
 const rotation=c.quaternion.clone().set(q[1],q[2],q[3],q[0]);
 c.up.set(0,0,1).applyQuaternion(rotation);m.cameraControl.updateCameraUp();
 const from=c.position.clone().fromArray(eye).applyQuaternion(rotation);
 const to=c.position.clone().fromArray(target).applyQuaternion(rotation);
 m.cameraControl.setLookAt(...from.toArray(),...to.toArray(),false);
 c.fov=50;c.updateProjectionMatrix();
}'''
SETTLE = '()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))'


def data(name):
    return json.loads((ROOT/f'assets/{name}.js').read_text().split(' = ',2)[-1].strip().removesuffix(';'))


def write_poster(video):
    png=subprocess.check_output([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-ss','0.1',
        '-i',str(video),'-frames:v','1','-f','image2pipe','-vcodec','png','-'])
    Image.open(io.BytesIO(png)).save(video.with_suffix('.webp'),quality=82)


def compact_overview(video, size=960):
    """Keep the matrix lightweight; detail clips retain the native resolution."""
    with tempfile.TemporaryDirectory(prefix='clear-overview-') as temporary:
        output=Path(temporary)/video.name
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-i',str(video),
            '-vf',f'scale={size}:-2:flags=lanczos','-an','-c:v','libx264','-preset','fast',
            '-crf','22','-pix_fmt','yuv420p','-movflags','+faststart','-map_metadata','-1',str(output)],check=True)
        staged=video.with_suffix('.mp4.tmp');staged.write_bytes(output.read_bytes());staged.replace(video)
    write_poster(video)


def write_details(video, views, size, only=None, tracking=None, start=0, canvas_height=None):
    canvas_height=canvas_height or size
    rows=(len(views)+1)//2;scale=size/960
    for index,view in enumerate(views):
        if only is not None and index!=only:continue
        x=round(index%2*(size//2)+8*scale);y=round(index//2*(canvas_height//rows)+36*scale)
        width=size//2-round(16*scale)
        if len(views)%2 and index==len(views)-1:x=(size-width)//2
        height=canvas_height//rows-round(44*scale)
        # Even dimensions retain standard H.264 playback on mobile browsers.
        width-=width%2;height-=height%2
        output=video.with_name(video.stem+'-'+view['key']+'.mp4')
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-i',str(video),
            '-vf',f'crop={width}:{height}:{x}:{y}','-an','-c:v','libx264','-preset','fast',
            '-crf','20','-pix_fmt','yuv420p','-movflags','+faststart','-map_metadata','-1',str(output)],check=True)
        if tracking is not None and len(views)%2 and index==len(views)-1:
            write_detail_metrics(output,tracking,start,index,size)
        write_poster(output)


def write_detail_metrics(video, tracking, start, index, render_size=1920):
    """Keep metrics visible when the final wide overview cell is center-cropped."""
    from PIL import ImageDraw,ImageFont
    frames=imageio_ffmpeg.read_frames(str(video),pix_fmt='rgb24')
    meta=next(frames);width,height=meta['size'];fps=meta['fps'];scale=render_size/960
    font=ImageFont.truetype(font_path(mono=True),round(render_size/74))
    with tempfile.TemporaryDirectory(prefix='clear-detail-metrics-') as temporary:
        output=Path(temporary)/video.name
        proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo',
            '-pix_fmt','rgb24','-s',f'{width}x{height}','-r',str(fps),'-i','-','-an','-c:v','libx264',
            '-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart','-map_metadata','-1',str(output)],stdin=subprocess.PIPE)
        try:
            for frame,pixels in enumerate(frames):
                image=Image.frombytes('RGB',(width,height),pixels);draw=ImageDraw.Draw(image)
                row=tracking['replay'].metrics(start+frame/fps,tracking['layout'])[index]
                draw.rectangle((0,0,width,round(42*scale)),fill='white')
                draw.text((round(6*scale),round(7*scale)),f"Target {row['target']:.2f}  /  Actual {row['actual']:.2f} m/s",font=font,fill='#39434a')
                draw.text((round(6*scale),round(23*scale)),f"Velocity error {row['velocityError']:.2f} m/s  ·  Heading error {row['headingErrorDegrees']:.1f}°",font=font,fill='#637079')
                proc.stdin.write(image.tobytes())
        finally:
            proc.stdin.close();code=proc.wait();frames.close()
        assert code==0
        staged=video.with_suffix('.mp4.tmp');staged.write_bytes(output.read_bytes());staged.replace(video)


def outlined_recording(record, buffers, width=0.008):
    """Add back-face outline shells; keep original messages and arrays intact."""
    result=copy.deepcopy(record)
    buffers=list(buffers)
    def pack(array):
        array=np.ascontiguousarray(array)
        buffers.append(array.tobytes())
        return {'__binary_index':len(buffers)-1,'dtype':array.dtype.str}
    def array(ref, columns):
        return np.frombuffer(buffers[ref['__binary_index']],dtype=ref['dtype']).reshape(-1,columns)
    names={message['name'] for _,message in record['messages']
           if message['type']=='BatchedMeshesMessage' and message['name'].startswith('/agents/')}
    black=pack(np.zeros(3,dtype='u1'))
    messages=[]
    for timestamp,message in result['messages']:
        messages.append((timestamp,message))
        if message.get('name') not in names:continue
        outline=copy.deepcopy(message)
        outline['name']=message['name'].replace('/agents/','/agent-outlines/',1)
        if message['type']=='BatchedMeshesMessage':
            props=outline['props']
            vertices=array(props['vertices'],3);faces=array(props['faces'],3)
            normals=trimesh.Trimesh(vertices,faces,process=False).vertex_normals
            props['vertices']=pack((vertices+width*normals).astype('<f4'))
            props.update(batched_colors=dict(black),side='back',cast_shadow=False,receive_shadow=False)
        elif 'updates' in outline and 'batched_colors' in outline['updates']:
            outline['updates']['batched_colors']=dict(black)
        messages.append((timestamp,outline))
    result['messages']=messages
    with tempfile.TemporaryDirectory(prefix='clear-outline-') as temporary:
        path=Path(temporary)/'outlined.viser'
        result,buffers=compact_buffers(result,buffers)
        write_recording(path,result,buffers)
        return path.read_bytes()


def render(browser, scene, checkpoints, args, camera_stages=None, camera_cache=None):
    source = (args.recordings_dir or ROOT/'assets/recordings')/f'{scene}.hex.js'
    body='g1' if scene=='learning-g1' else ('spot_arm' if scene=='learning-spot_arm' else 'spot')
    if body!='spot_arm':
        font_path()  # Captioned videos require the requested rendering font.
    tracking_path=args.tracking_dir/body/f'{body}-tracking.npz' if args.tracking_dir else None
    tracking=TrackingReplay(tracking_path) if tracking_path and tracking_path.exists() else None
    if any(stage['replay'].get('headingTracking') for stage in checkpoints) and (tracking is None or args.recordings_dir is None):
        raise ValueError('Heading evaluations require --recordings-dir and --tracking-dir; refusing to overwrite measured videos with an unmeasured replay')
    raw = bytes.fromhex(json.loads(source.read_text().rsplit(' = ',1)[1].strip().removesuffix(';')))
    with tempfile.NamedTemporaryFile() as file:
        file.write(raw);file.flush();record,buffers=read_recording(file.name)
    record,buffers=restyle(record,buffers)
    counts=set()
    for _,message in record['messages']:
        if message['type']=='BatchedMeshesMessage':
            ref=message['props']['batched_positions']
            counts.add(len(np.frombuffer(buffers[ref['__binary_index']],dtype=ref['dtype']))//3)
    assert len(counts)==1, counts
    agents=counts.pop()
    # Use one motion envelope for each body/terrain across every checkpoint.
    # Keep stage-specific geometry and overlays, but never refit the camera on
    # index changes (early falls otherwise produce a much tighter zoom).
    if camera_cache is None:
        camera_cache = {}
    if scene not in camera_cache:
        shared = {}
        for stage in camera_stages or checkpoints:
            _, _, stage_views, _ = arrange(record, buffers, stage['replay'].get('startTime', 0), tracking)
            for view in stage_views:
                entry = shared.setdefault(view['key'], dict(
                    eye=view['eye'], target=view['target'], fitPoints=[]))
                entry['fitPoints'].extend(view['fitPoints'])
        camera_cache[scene] = shared
    record,buffers,views,layout=arrange(record,buffers,checkpoints[-1]['replay'].get('startTime',0),tracking)
    for view in views:
        view.update(copy.deepcopy(camera_cache[scene][view['key']]))
    render_raw=outlined_recording(record,buffers)
    page=browser.new_page(viewport={'width':args.size,'height':args.height},device_scale_factor=1)
    def route(request):
        path=urlsplit(request.request.url).path
        if path=='/policy.viser':
            request.fulfill(body=render_raw,content_type='application/octet-stream')
        elif path=='/assets/viser/index.html':
            request.fulfill(body=(ROOT/'assets/viser/index.html').read_bytes(),content_type='text/html')
        else:
            request.continue_()
    page.route('**/*',route)
    page.goto(args.base_url.rstrip('/')+'/assets/viser/index.html?playbackPath=/policy.viser')
    page.locator('input').first.wait_for(timeout=90000)
    assert page.evaluate(FIND),'Native Viser scene unavailable'
    pause=page.locator('.tabler-icon-player-pause-filled')
    if pause.count():pause.locator('..').click()
    page.add_style_tag(content='body *:not(:has(canvas)):not(canvas){visibility:hidden!important}canvas{visibility:visible!important}')
    page.evaluate(MATRIX,views)
    results=[]
    try:
        for stage in checkpoints:
            replay=stage['replay'];step=replay['cumulativeUpdates'];start=replay.get('startTime',0)+replay.get('videoStartOffset',0)
            name=f'{scene}-update-{step:05d}.mp4';dest=args.output/name
            frames=round(replay.get('duration',8)*args.fps)
            with tempfile.TemporaryDirectory(prefix='clear-policy-') as temporary:
                output=Path(temporary)/name
                proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error',
                    '-f','image2pipe','-framerate',str(args.fps),'-vcodec','mjpeg','-i','-',
                    '-an','-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p',
                    '-movflags','+faststart','-map_metadata','-1',str(output)],stdin=subprocess.PIPE)
                try:
                    for frame in range(frames):
                        page.evaluate(SEEK,start+frame/args.fps+1e-6)
                        page.evaluate(SETTLE)
                        picture=page.screenshot(type='jpeg',quality=95,timeout=30000)
                        if body!='spot_arm':picture=annotate(picture,views,args.size,tracking.metrics(start+frame/args.fps,layout) if tracking else None)
                        proc.stdin.write(picture)
                        if frame==min(72,frames-1):
                            (Path('/tmp')/(name+'.jpg')).write_bytes(picture)
                        if frame%48==0:print(name,frame,'/',frames,flush=True)
                finally:
                    proc.stdin.close()
                    code=proc.wait()
                assert code==0,name
                # Replace only a completely rendered and encoded output.
                staged=dest.with_suffix('.mp4.tmp');staged.write_bytes(output.read_bytes());staged.replace(dest)
            write_poster(dest)
            write_details(dest,views,args.size,tracking={'replay':tracking,'layout':layout} if tracking and body!='spot_arm' else None,start=start,canvas_height=args.height)
            if args.size>960:compact_overview(dest)
            results.append(dict(file=name,scene=scene,agents=agents,startTime=start,
                duration=frames/args.fps,fps=args.fps,width=min(args.size,960),height=round(args.height*min(args.size,960)/args.size),renderWidth=args.size,renderHeight=args.height,
                renderer='Native Viser',cameraPolicy='Fixed per body and terrain across all checkpoint motion envelopes',displayGround='Visual flat continuation outside the recorded tile',velocityOverlay=['target','actual'],trackingMeasured=tracking is not None,trackingEvidence=f'assets/policy-tracking-{body}.json' if tracking else None,displayMode='radial-heading-evaluation' if tracking else 'radial-replay-illustration',uniqueRecordedAgentsShown=len({item['sourceAgent'] for item in layout}),views=views,displayLayout=layout,displayedAgents=len(layout),outline={'color':'black','widthMeters':0.008,'method':'back-face shell'},sourceSHA256=hashlib.sha256(raw).hexdigest()))
            print('Rendered',name,agents,'recorded agents',dest.stat().st_size,'bytes',flush=True)
    finally:
        page.close()
    return results


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene',action='append')
    parser.add_argument('--recordings-dir',type=Path)
    parser.add_argument('--tracking-dir',type=Path)
    parser.add_argument('--size',type=int,default=1920)
    parser.add_argument('--height',type=int,help='Canvas height; defaults to 21:16 for larger unclipped terrain views')
    parser.add_argument('--fps',type=int,default=24)
    parser.add_argument('--base-url',default='http://localhost:8772')
    parser.add_argument('--output',type=Path,default=ROOT/'assets/media')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    args.height=args.height or round(args.size*21/16)
    scenes={}
    for name in ['g1-restored-data','spot_arm-restored-data','spot-curriculum-data']:
        body=data(name)
        for stage in body.get('checkpoints',body['stages']):
            if stage.get('replay'):
                scene=stage['replay']['scene']
                if args.scene is None or scene in args.scene:scenes.setdefault(scene,[]).append(stage)
    results=[]
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan',
            '--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist'])
        try:
            camera_cache = {}
            for scene,stages in scenes.items():
                for stage in stages:results.extend(render(browser,scene,[stage],args,stages,camera_cache))
        finally:
            browser.close()
    provenance=ROOT/'assets/policy-video-provenance.json' if args.output==ROOT/'assets/media' else args.output/'policy-video-provenance.json'
    with (Path(tempfile.gettempdir())/'clear-policy-provenance.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        previous=json.loads(provenance.read_text()) if provenance.exists() else []
        names={item['file'] for item in results}
        provenance.write_text(json.dumps([item for item in previous if item['file'] not in names]+results,indent=2)+'\n')


if __name__=='__main__':
    main()
