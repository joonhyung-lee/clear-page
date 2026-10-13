"""Render synchronized native main/Ego views from interpolated archived poses.

SLERP and linear position interpolation improve display cadence only. They do
not add measured samples or resimulate physics. Original archive stays intact.
"""
import argparse,copy,hashlib,json,subprocess,tempfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit
import numpy as np
import imageio_ffmpeg
from scipy.spatial.transform import Rotation,Slerp
from playwright.sync_api import sync_playwright
from recording_io import read_recording,write_recording
from style_recorded_palette import restyle
from check_research_visuals import FIND,SEEK
ROOT=Path(__file__).resolve().parents[1]
CAMERA=r'''({ego,spot,recordedCamera})=>{
 const v=testViewer,m=v.mutable.current,c=m.camera;
 const root=v.useSceneTree.get('').wxyz;
 const rotation=c.quaternion.clone().set(root[1],root[2],root[3],root[0]);
 const up=c.up.clone().set(0,0,1).applyQuaternion(rotation);
 if(ego){
  const node=m.nodeRefFromName[spot?'/body-1':'/tracking/body-16'];node.updateWorldMatrix(true,false);
  const offset=spot?[.38,0,.10]:[.14,0,.30];
  const eye=node.localToWorld(c.position.clone().fromArray(offset));
  const at=node.localToWorld(c.position.clone().set(offset[0]+1,offset[1],offset[2]));
  up.set(0,0,1).transformDirection(node.matrixWorld);
  c.up.copy(up);m.cameraControl.updateCameraUp();
  m.cameraControl.setLookAt(...eye.toArray(),...at.toArray(),false);c.fov=60;
 }else if(!spot&&!recordedCamera){
  c.up.copy(up);m.cameraControl.updateCameraUp();
  const eye=c.position.clone().set(2.6,-1.8,1.5).applyQuaternion(rotation);
  const at=c.position.clone().set(0,.5,.7).applyQuaternion(rotation);
  m.cameraControl.setLookAt(...eye.toArray(),...at.toArray(),false);c.fov=.85*180/Math.PI;
 }
 c.near=.005;c.updateProjectionMatrix();
 for(const [name,node] of Object.entries(v.useSceneTree.getAll())){
  if(name.includes('WorldAxes')||(ego&&/candidate|waypoint|palm-centers|reference-path|reference-overlay|eef-overlay|object-overlay|native-overlay|reference-ghost|object-motion/.test(name)))
   v.sceneTreeActions.updateNodeAttributes(name,{visibility:false});
 }
}'''

def interpolate(record,fps):
 result=copy.deepcopy(record);tracks=defaultdict(dict)
 for t,m in record['messages']:
  if m['type'] in ['SetPositionMessage','SetOrientationMessage']:
   tracks[(m['name'],m['type'])][t]=m
 dynamic={key:values for key,values in tracks.items() if len(values)>1}
 result['messages']=[(t,m) for t,m in result['messages'] if (m.get('name'),m['type']) not in dynamic]
 samples=np.arange(round(record['durationSeconds']*fps)+1)/fps
 for (name,kind),values in dynamic.items():
  times=np.array(sorted(values));key='position' if kind=='SetPositionMessage' else 'wxyz'
  data=np.array([values[t][key] for t in times]);at=np.clip(samples,times[0],times[-1])
  out=Slerp(times,Rotation.from_quat(data,scalar_first=True))(at).as_quat(scalar_first=True) if key=='wxyz' else np.array([np.interp(at,times,data[:,i]) for i in range(3)]).T
  for t,value in zip(samples,out):result['messages'].append((float(t),dict(type=kind,name=name,**{key:value.tolist()})))
 result['messages'].sort(key=lambda item:item[0]);return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scene',default='mpc-optimized');p.add_argument('--output',type=Path,required=True);p.add_argument('--sample',type=float)
 p.add_argument('--base-url',default='http://localhost:8773');p.add_argument('--fps',type=int,default=30)
 p.add_argument('--main-width',type=int,default=1120);p.add_argument('--ego-width',type=int,default=640)
 p.add_argument('--current-recording',action='store_true',help='Render the current published recording exactly, including repaired overlays')
 p.add_argument('--recorded-camera',action='store_true',help='Retain the original main camera and field of view')
 p.add_argument('--views',nargs='+',choices=['main','ego'],default=['main','ego'])
 a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 source=ROOT/f'.git/visual-refresh/original-recordings/{a.scene}.viser'
 if a.current_recording or not source.exists():source=ROOT/f'assets/recordings/{a.scene}.viser'
 source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
 r,b=read_recording(source) if a.current_recording else restyle(*read_recording(source));fps=a.fps
 with tempfile.TemporaryDirectory(prefix='clear-camera-') as tmp,sync_playwright() as pw:
  recording=Path(tmp)/'render.viser';write_recording(recording,interpolate(r,fps),b)
  browser=pw.chromium.launch(args=['--use-angle=vulkan','--enable-features=Vulkan','--disable-vulkan-surface','--enable-gpu','--ignore-gpu-blocklist'])
  pages={};writers={}
  for ego in [view=='ego' for view in a.views]:
   width=a.ego_width if ego else a.main_width
   page=browser.new_page(viewport={'width':width,'height':2*round(width*.75/2)})
   page.route('**/*',lambda route:route.fulfill(body=recording.read_bytes(),content_type='application/octet-stream') if urlsplit(route.request.url).path=='/render.viser' else route.continue_())
   page.goto(a.base_url+'/assets/viser/index.html?playbackPath=/render.viser');page.locator('input').first.wait_for(timeout=90000);page.wait_for_function(FIND,timeout=90000)
   if a.scene.startswith('mpc-spot-'):page.evaluate((ROOT/'assets/eef-overlay.js').read_text())
   pause=page.locator('.tabler-icon-player-pause-filled');
   if pause.count():pause.locator('..').click()
   page.add_style_tag(content='body *:not(:has(canvas)):not(canvas){visibility:hidden!important} canvas{visibility:visible!important}')
   pages[ego]=page
   if a.sample is None:
    suffix='-ego' if ego else '-contact'
    writers[ego]=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','image2pipe','-framerate',str(fps),'-vcodec','png','-i','-','-an','-map_metadata','-1','-c:v','libx264','-crf','19','-pix_fmt','yuv420p','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(a.output/f'{a.scene}{suffix}.mp4')],stdin=subprocess.PIPE)
  times=[a.sample] if a.sample is not None else np.arange(round(r['durationSeconds']*fps))/fps
  try:
   for i,t in enumerate(times):
    for ego,page in pages.items():
     page.evaluate(SEEK,float(t));page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
     page.evaluate(CAMERA,dict(ego=ego,spot=a.scene.startswith('mpc-spot-'),recordedCamera=a.recorded_camera));page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
     if not ego and a.scene.startswith('mpc-spot-'):
      page.evaluate('()=>window.CLEAR_EEF_OVERLAY(testViewer)');page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
     png=page.screenshot(timeout=20000);suffix='-ego' if ego else '-contact'
     if i%150==0:(a.output/f'{a.scene}{suffix}-{i}.png').write_bytes(png)
     if ego in writers:writers[ego].stdin.write(png)
    if i%60==0:print(a.scene,'paired frame',i,'/',len(times),flush=True)
  finally:
   for proc in writers.values():proc.stdin.close()
   codes=[proc.wait() for proc in writers.values()];browser.close()
  assert all(c==0 for c in codes)
  (a.output/'render.json').write_text(json.dumps(dict(scene=a.scene,sourceSHA256=source_hash,currentRecording=a.current_recording,recordedCamera=a.recorded_camera,views=a.views,fps=fps,frames=len(times),duration=r['durationSeconds'],poseInterpolation='linear position and quaternion SLERP',physicsRerun=False),indent=2)+'\n')
if __name__=='__main__':main()
