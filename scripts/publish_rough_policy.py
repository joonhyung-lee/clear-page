"""Publish measured rough-terrain checkpoint clips alongside existing terrain views."""
import argparse, hashlib, json, shutil, subprocess, tempfile
from pathlib import Path
import imageio_ffmpeg
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from design_tokens import font_path
from render_policy_videos import write_poster
from policy_matrix_scene import representative_agent

ROOT=Path(__file__).resolve().parents[1]

def publish(body, directory, evidence):
    datafile=ROOT/'assets'/('spot-curriculum-data.js' if body=='spot' else 'spot_arm-restored-data.js')
    prefix,raw=datafile.read_text().rsplit(' = ',1);data=json.loads(raw.strip().removesuffix(';'))
    rendered=json.loads((directory/'policy-video-provenance.json').read_text())
    audit=json.loads((evidence/body/(body+'-audit.json')).read_text())
    telemetry=np.load(evidence/body/(body+'-tracking.npz'));states=np.load(evidence/body/(body+'-states.npz'))
    agent=representative_agent(body,'random_rough',list(range(len(states['origins']))),states['origins'])
    trackingfile=ROOT/f'assets/policy-tracking-{body}.json';tracking=json.loads(trackingfile.read_text())
    provenancefile=ROOT/'assets/policy-video-provenance.json';provenance=json.loads(provenancefile.read_text())
    media=ROOT/'assets/media';backup=ROOT/'.git/rough-evaluation/original-matrices';backup.mkdir(parents=True,exist_ok=True)
    terrains=[('flat','Flat'),('stairs_down','Stairs down'),('stairs_up','Stairs up'),('slope_down','Slope down'),('slope_up','Slope up'),('random_rough','Rough terrain')]
    labels=Image.new('RGBA',(960,1260),(255,255,255,0));draw=ImageDraw.Draw(labels)
    titlefont=ImageFont.truetype(font_path(mono=True),20);smallfont=ImageFont.truetype(font_path(mono=True),12)
    for i,(_,title) in enumerate(terrains):
        x=i%2*480;y=i//2*420
        draw.text((x+14,y+5),title,font=titlefont,fill='#39434a')
        draw.text((x+364,y+8),'4 directions',font=smallfont,fill='#637079')
    labelpath=backup/'six-terrain-labels.png';labels.save(labelpath)
    for stage in data['checkpoints']:
        replay=stage['replay'];step=replay['cumulativeUpdates'];name=Path(replay['video']).name
        row=next(r for r in rendered if r['file']==name)
        index=next(i for i,s in enumerate(audit['stages']) if s['iteration']==step)
        entry=next(c for c in tracking['checkpoints'] if c['update']==step)
        if audit['stages'][index]['sha256']!=entry['checkpointSHA256']:raise ValueError('Checkpoint lineage differs')
        source=directory/(Path(name).stem+'-random_rough.mp4')
        if not source.exists():raise FileNotFoundError(source)
        shutil.copyfile(source,media/source.name);shutil.copyfile(source.with_suffix('.webp'),media/source.with_suffix('.webp').name)
        # Recompose six existing detail clips; every motion frame stays recorded.
        output=media/name
        if not (backup/name).exists():shutil.copyfile(output,backup/name)
        inputs=[];filters=[]
        for i,(terrain,title) in enumerate(terrains):
            clip=media/(Path(name).stem+'-'+terrain+'.mp4')
            inputs += ['-i',str(clip)]
            filters.append(f"[{i}:v]fps=24,scale=464:376:flags=lanczos,pad=480:420:8:36:white[v{i}]")
        inputs += ['-loop','1','-i',str(labelpath)]
        filters.append(''.join(f'[v{i}]' for i in range(6))+'xstack=inputs=6:layout=0_0|480_0|0_420|480_420|0_840|480_840:shortest=1[grid]')
        filters.append('[grid][6:v]overlay=shortest=1[out]')
        with tempfile.TemporaryDirectory(prefix='clear-six-terrains-') as tmp:
            dest=Path(tmp)/name
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error',*inputs,'-filter_complex',';'.join(filters),'-map','[out]','-an','-c:v','libx264','-preset','fast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart','-map_metadata','-1',str(dest)],check=True)
            shutil.copyfile(dest,output)
        write_poster(output)
        replay['roughTerrain']=True
        command=telemetry['command_world'][index,:,agent,:2];velocity=telemetry['velocity_world'][index,:,agent,:2];heading=telemetry['heading'][index,:,agent]
        samples=np.column_stack([np.arange(len(heading))*float(telemetry['dt']),command,velocity,heading,telemetry['command_body'][index,:,agent,2],telemetry['root_position'][index,:,agent]])
        forward=velocity[:,0]*np.cos(heading)+velocity[:,1]*np.sin(heading)
        rough=dict(terrain='random_rough',sourceTerrain='random_rough',sourceAgent=agent,meanVelocityError=float(np.linalg.norm(velocity-command,axis=1).mean()),meanHeadingErrorDegrees=float(np.degrees(abs(heading)).mean()),forwardMotionFraction=float((forward[np.linalg.norm(velocity,axis=1)>.1]>0).mean()),samples=np.round(samples,6).tolist())
        entry['terrains']=[t for t in entry['terrains'] if t['terrain']!='random_rough']+[rough]
        entry['roughTerrainEvaluation']=dict(seed=42,noiseRange=[.02,.08],noiseStep=.02,checkpointSHA256=entry['checkpointSHA256'],telemetrySHA256=hashlib.sha256((evidence/body/(body+'-tracking.npz')).read_bytes()).hexdigest())
        original=next(r for r in provenance if r['file']==name)
        original['roughTerrain']=dict(sourceSHA256=row['sourceSHA256'],view=row['views'][0],displayLayout=row['displayLayout'],videoSHA256=hashlib.sha256(source.read_bytes()).hexdigest(),recordedAgents=row['agents'])
        original['composition']='Six terrain detail clips in a 2 by 3 matrix'
        original['matrixSHA256']=hashlib.sha256(output.read_bytes()).hexdigest()
        print(body,step,'rough view + six-terrain overview published',flush=True)
    datafile.write_text(prefix+' = '+json.dumps(data,separators=(',',':'))+';\n')
    trackingfile.write_text(json.dumps(tracking,separators=(',',':'))+'\n')
    provenancefile.write_text(json.dumps(provenance,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--body',choices=['spot','spot_arm'],required=True);p.add_argument('--directory',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args();publish(a.body,a.directory,a.evidence)
