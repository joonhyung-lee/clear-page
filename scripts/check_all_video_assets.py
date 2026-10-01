"""Check every public movie in Chromium and compare saved timeline metadata."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from recording_io import read_recording
ROOT=Path(__file__).resolve().parents[1]
PROBE=r'''async path=>{
 const v=document.querySelector('video');v.pause();v.src=path;v.load();
 const until=(test,event)=>new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>{cleanup();reject(Error(event+' timeout: '+path))},15000);
  const ready=()=>{if(test()){cleanup();resolve()}};
  const fail=()=>{cleanup();reject(Error('media error '+v.error?.code+': '+path))};
  function cleanup(){clearTimeout(timer);v.removeEventListener(event,ready);v.removeEventListener('error',fail)}
  v.addEventListener(event,ready);v.addEventListener('error',fail);ready();
 });
 await until(()=>v.readyState>=2,'loadeddata');
 const results=[];
 for(const t of [0,v.duration*.5,Math.max(0,v.duration-.1)]){
  if(t){v.currentTime=t;await until(()=>!v.seeking&&Math.abs(v.currentTime-t)<.1,'seeked');}
  const c=document.createElement('canvas');c.width=64;c.height=48;
  const ctx=c.getContext('2d');ctx.drawImage(v,0,0,64,48);const data=ctx.getImageData(0,0,64,48).data;
  let min=255,max=0;for(let i=0;i<data.length;i+=4){min=Math.min(min,data[i],data[i+1],data[i+2]);max=Math.max(max,data[i],data[i+1],data[i+2]);}
  if(max-min<5)throw Error('Blank frame at '+t+': '+path);
  results.push({time:v.currentTime,range:max-min});
 }
 return {duration:v.duration,width:v.videoWidth,height:v.videoHeight,samples:results};
}'''

def main():
 files=sorted((ROOT/'assets').rglob('*.mp4'));rows={}
 with sync_playwright() as p:
  browser=p.chromium.launch();page=browser.new_page()
  page.route('**/video-audit.html',lambda route:route.fulfill(content_type='text/html',body='<video muted playsinline preload="auto"></video>'))
  page.goto('http://localhost:8765/video-audit.html')
  for i,file in enumerate(files):
   relative=file.relative_to(ROOT).as_posix();rows[relative]=page.evaluate(PROBE,'/'+relative)
   if (i+1)%25==0:print('PASS browser decoded/seeks',i+1,'/',len(files),flush=True)
  browser.close()
 samples=json.loads((ROOT/'assets/learning-samples.js').read_text().split('=',1)[1].rstrip(';\n'))['grounding']
 manifest=json.loads((ROOT/'assets/learning-media.json').read_text())
 for entry,sample in zip(manifest,samples):
  row=rows[f"assets/media/attempts/attempt-{entry['id']:03d}.mp4"]
  assert abs(entry['start']-sample['rollout'][0][0])<1e-6
  assert abs(entry['end']-sample['rollout'][-1][0])<1e-6
  # The original exporter includes the final held frame after rounding.
  assert abs(row['duration']-entry['frames']/entry['fps'])<.011
  assert abs(row['duration']-(entry['end']-entry['start']))<=1.51/entry['fps']
 native=0
 for relative,row in rows.items():
  path=ROOT/'assets/recordings'/Path(relative).with_suffix('.viser').name
  if path.exists():
   record,_=read_recording(path)
   assert abs(row['duration']-record['durationSeconds'])<.15,(relative,row['duration'],record['durationSeconds'])
   native+=1
 report=dict(videos=rows,groundingIntervals=len(manifest),matchingNativeTimelines=native)
 Path('/tmp/clear-all-video-browser.json').write_text(json.dumps(report,indent=2)+'\n')
 print('PASS',len(rows),'browser decodes and seeks;',len(manifest),'sample intervals;',native,'native replay timelines',flush=True)
if __name__=='__main__':main()
