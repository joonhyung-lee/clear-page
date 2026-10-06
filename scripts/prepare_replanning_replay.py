"""Normalize an actual Viser recording and logged plan revisions for video rendering."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from recording_io import read_recording

p=argparse.ArgumentParser(description=__doc__)
for name in ['recording','episode','scene','output']:p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--title',required=True);p.add_argument('--scope',required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
episode=json.loads(a.episode.read_text());scene=json.loads(a.scene.read_text());record,buffers=read_recording(a.recording)
bodies=sorted({m['name'] for _,m in record['messages'] if m['type']=='FrameMessage' and m['name'].startswith('/body-')},key=lambda n:int(n.split('-')[-1]));lookup={n:i for i,n in enumerate(bodies)}
meshes={};local_pos={};local_q={}
for t,m in record['messages']:
 if t>0:break
 n=m.get('name');typ=m['type']
 if typ=='MeshMessage':meshes[n]=m['props']
 if typ=='SetPositionMessage':local_pos[n]=m['position']
 if typ=='SetOrientationMessage':local_q[n]=m['wxyz']
arrays={};mesh_meta=[]
for i,(name,props) in enumerate(meshes.items()):
 v=np.frombuffer(buffers[props['vertices']['__binary_index']],dtype='<f4').reshape(-1,3).copy();f=np.frombuffer(buffers[props['faces']['__binary_index']],dtype='<u4').reshape(-1,3).copy()
 v=Rotation.from_quat(local_q.get(name,[1,0,0,0]),scalar_first=True).apply(v)*props.get('scale',1)+local_pos.get(name,[0,0,0])
 tri=v[f];norm=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);vn=np.zeros_like(v)
 for k in range(3):np.add.at(vn,f[:,k],norm)
 vn/=np.maximum(np.linalg.norm(vn,axis=1,keepdims=True),1e-12)
 arrays.update({f'vertices_{i}':v.astype('f4'),f'normals_{i}':vn.astype('f4'),f'faces_{i}':f})
 mesh_meta.append(dict(body=lookup[name.rpartition('/')[0]],color=props['color']))
pos=np.zeros((len(bodies),3));quat=np.tile([1.,0,0,0],(len(bodies),1));times=[];positions=[];quats=[];last=None
for t,m in record['messages']:
 n=m.get('name');typ=m['type']
 if n not in lookup or typ not in ['SetPositionMessage','SetOrientationMessage']:continue
 if last is not None and t!=last:times.append(last);positions.append(pos.copy());quats.append(quat.copy())
 last=t
 if typ=='SetPositionMessage':pos[lookup[n]]=m['position']
 else:quat[lookup[n]]=m['wxyz']
times.append(last);positions.append(pos.copy());quats.append(quat.copy())
arrays.update(time=np.asarray(times),positions=np.asarray(positions),quaternions=np.asarray(quats));assert np.all(np.diff(times)>0)
object_bodies={}
for obj in scene['objects']:
 ids=[i for i,n in enumerate(bodies) if np.linalg.norm(np.asarray(local_pos.get(n,[0,0,0]))[:2]-obj['pose'][:2])<1e-4]
 assert len(ids)==1,(obj['object_id'],ids);object_bodies[obj['object_id']]=ids[0]
plans=[]
for p in episode['plans']:
 plans.append(dict(time=p['time_s'],call=p['call'],purpose=p['purpose'],paths=p['plan']['paths'],order=p['order'],source=p.get('selection_source','logged_plan'),wall_seconds=p['wall_s']))
events=[{k:e[k] for k in ['object_id','start_time_s','end_time_s','motion_start_s','motion_end_s'] if k in e} for e in episode.get('external_events',[])]
attempts=[{k:e[k] for k in ['object_id','start_time_s','end_time_s','success']} for e in episode['attempt_log']]
meta=dict(title=a.title,scope=a.scope,scene=scene,bodies=bodies,meshes=mesh_meta,object_bodies=object_bodies,plans=plans,events=events,attempts=attempts,duration=times[-1],outcome=episode['status'],recordingSHA256=hashlib.sha256(a.recording.read_bytes()).hexdigest(),episodeSHA256=hashlib.sha256(a.episode.read_bytes()).hexdigest())
np.savez_compressed(a.output/'geometry.npz',**arrays);(a.output/'timeline.json').write_text(json.dumps(meta,separators=(',',':'))+'\n')
print('PASS',len(mesh_meta),'native meshes,',len(times),'states,',len(plans),'logged plans,',len(events),'external events')
