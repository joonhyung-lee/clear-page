"""Render small checkpoint videos from the exact published Viser poses."""
import os
os.environ.setdefault('MUJOCO_GL','egl')
os.environ.setdefault('PYOPENGL_PLATFORM','egl')
import json
import subprocess
import tempfile
from pathlib import Path
import imageio_ffmpeg
import numpy as np
import trimesh
from PIL import Image,ImageDraw
from scipy.spatial.transform import Rotation
from recording_io import read_recording
from replanning_mesh_renderer import MeshRenderer,camera_matrix

ROOT=Path(__file__).resolve().parents[1]

def data(name):
    return json.loads((ROOT/f'assets/{name}.js').read_text().split(' = ',2)[-1].strip().removesuffix(';'))

def render(scene,checkpoints):
    source=ROOT/f'assets/recordings/{scene}.hex.js'
    encoded=json.loads(source.read_text().rsplit(' = ',1)[1].strip().removesuffix(';'))
    with tempfile.NamedTemporaryFile() as f:
        f.write(bytes.fromhex(encoded));f.flush();record,buffers=read_recording(f.name)
    def array(ref,width):return np.frombuffer(buffers[ref['__binary_index']],dtype=ref['dtype']).reshape(-1,width)
    messages=record['messages'];geometry={};meshes=[];initial={};names={}
    for timestamp,message in messages:
        if message['type'] not in ['MeshMessage','BatchedMeshesMessage']:continue
        props=message['props'];vertices=array(props['vertices'],3);faces=array(props['faces'],3)
        index=len(meshes);names[message['name']]=index
        geometry[f'vertices_{index}']=vertices;geometry[f'faces_{index}']=faces
        geometry[f'normals_{index}']=np.asarray(trimesh.Trimesh(vertices,faces,process=False).vertex_normals)
        batched=message['type']=='BatchedMeshesMessage'
        color=array(props['batched_colors'],3)[0].tolist() if batched else props['color']
        meshes.append({'body':index,'color':color})
        if batched:initial[index]={'positions':array(props['batched_positions'],3),'quaternions':array(props['batched_wxyzs'],4)}
    assert initial,'No recorded robot poses'
    count=next(iter(initial.values()))['positions'].shape[0]
    agents=[min(7,count-1),min(8,count-1)]
    updates=[];state={index:dict(value) for index,value in initial.items()}
    for timestamp,message in messages:
        index=names.get(message.get('name'));props=message.get('updates',{})
        if index in initial and any(key in props for key in ['batched_positions','batched_wxyzs']):
            for key,target,width in [('batched_positions','positions',3),('batched_wxyzs','quaternions',4)]:
                if key in props:state[index][target]=array(props[key],width)
            updates.append((timestamp,index,dict(state[index])))
    updates.sort(key=lambda u:u[0]);assert updates,'No pose updates'
    # Fixed cameras cover the recorded trajectories at every checkpoint.
    torso=next(iter(initial));cameras=[]
    for agent in agents:
        trajectory=np.stack([u[2]['positions'][agent] for u in updates if u[1]==torso])
        target=(trajectory.min(axis=0)+trajectory.max(axis=0))/2
        cameras.append(camera_matrix(target+[5.8,-6.8,4.7],target,640/320,fov=46))
    renderer=MeshRenderer(geometry,meshes,width=640,height=320)
    for stage in checkpoints:
        replay=stage['replay'];step=replay['cumulativeUpdates'];start=replay.get('startTime',0)
        name=f'{scene}-update-{step:05d}.mp4';dest=ROOT/'assets/media'/name
        proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','640x640','-r','25','-i','-','-an','-c:v','libx264','-preset','fast','-crf','25','-pix_fmt','yuv420p','-movflags','+faststart','-map_metadata','-1',str(dest)],stdin=subprocess.PIPE)
        pose=dict(initial);cursor=0
        for frame in range(round(replay.get('duration',8)*25)):
            t=start+frame/25
            while cursor<len(updates) and updates[cursor][0]<=t+1e-6:
                _,index,state=updates[cursor];pose[index]=state;cursor+=1
            image=Image.new('RGB',(640,640),'#fafbf9')
            for column,(agent,camera) in enumerate(zip(agents,cameras)):
                matrices=np.repeat(np.eye(4)[None],len(meshes),axis=0)
                for index,state in pose.items():
                    matrices[index,:3,:3]=Rotation.from_quat(state['quaternions'][agent],scalar_first=True).as_matrix()
                    matrices[index,:3,3]=state['positions'][agent]
                image.paste(Image.fromarray(renderer.render(matrices,camera,640,320)),(0,320*column))
            proc.stdin.write(image.tobytes())
            if frame==75:image.save('/tmp/'+name+'.png')
        proc.stdin.close();assert proc.wait()==0
        print(name,dest.stat().st_size,flush=True)
    renderer.close()

if __name__=='__main__':
    scenes={}
    for name in ['g1-restored-data','spot_arm-restored-data','spot-curriculum-data']:
        body=data(name)
        for stage in body.get('checkpoints',body['stages']):
            if stage.get('replay'):scenes.setdefault(stage['replay']['scene'],[]).append(stage)
    for scene,stages in scenes.items():render(scene,stages)
