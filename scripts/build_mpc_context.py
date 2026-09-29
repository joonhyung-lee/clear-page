"""Build translucent robot replays from measured poses and existing numeric meshes."""
import argparse,copy,json,math,re
from pathlib import Path
import numpy as np
from recording_io import read_recording,write_recording
p=argparse.ArgumentParser();p.add_argument('kind',choices=['optimized','baseline']);p.add_argument('states',type=Path);a=p.parse_args();root=Path(__file__).resolve().parents[1]
source,buffers=read_recording(root/f'assets/recordings/mpc-{a.kind}.viser');state=np.load(a.states);robot=set(state['robot'].tolist());process_path=root/'assets/mpc-process-data.js';process=json.loads(process_path.read_text().split('=',1)[1].rstrip(';\n'));r=process[a.kind]
if a.kind=='optimized':
 old=np.asarray(r['observed']);new=state['observed'].round(5);assert np.array_equal(old,new[:len(old)])
 r['observed']=new.tolist();r['interactionEnd']=20.5;r['continuation']='Recorded navigation and subsequent object interaction'
else:r['interactionEnd']=40.
# The final measured state is at 40 s. One frame of padding keeps Viser's modulo seek from wrapping it to zero.
record={'durationSeconds':40.1,'viserVersion':source['viserVersion'],'messages':[]};messages=record['messages'];created=set()
def add(t,typ,name=None,**kwargs):
 if typ in ('LineSegmentsMessage','PointCloudMessage'):
  if name in created:typ='SceneNodeUpdateMessage';kwargs={'updates':kwargs['props']}
  else:created.add(name)
 m=dict(type=typ,**kwargs)
 if name is not None:m['name']=name
 messages.append([round(float(t),6),m])
 if typ in ('LineSegmentsMessage','PointCloudMessage'):
  # Backward seeks hide existing nodes before replaying initialization messages.
  messages.append([round(float(t),6),dict(type='SetSceneNodeVisibilityMessage',name=name,visible=True)])
def array(value,dtype='<f4'):
 x=np.asarray(value,dtype=dtype);index=len(buffers);buffers.append(x.tobytes());return {'__binary_index':index,'dtype':x.dtype.str}
def lines(t,name,points,color,width=1):
 points=np.asarray(points,dtype=np.float32)
 add(t,'LineSegmentsMessage',name,props=dict(points=array(points),colors=array(np.broadcast_to(color,points.shape),'u1'),line_width=width,scale=1.))
# Keep only numeric geometry, transforms and viewer setup. No contact textures or source names.
for t,m in source['messages']:
 if t>0:break
 name=m.get('name','');typ=m['type'];body=re.fullmatch(r'/tracking/body-(\d+)(?:/geom-\d+)?',name)
 keep=body is not None and typ in ('FrameMessage','MeshMessage','SetPositionMessage','SetOrientationMessage','SetSceneNodeVisibilityMessage')
 keep|=name in ('','/WorldAxes','/tracking') and typ not in ('SetPositionMessage','SetOrientationMessage')
 keep|=name=='' and typ=='SetOrientationMessage'
 if body and '/geom-' in name and int(body[1]) not in robot and int(body[1]) not in state['objects']:keep=False
 if body and '/geom-' not in name and typ in ('SetPositionMessage','SetOrientationMessage'):keep=False
 if not keep:continue
 m=copy.deepcopy(m)
 if typ=='MeshMessage':m['props'].update(opacity=.16 if int(body[1]) in robot else .22,wireframe=int(body[1]) not in robot,cast_shadow=False,receive_shadow=False)
 if typ=='SetCameraPositionMessage':m['position']=[-2.2,-2.6,2.0]
 if typ=='SetCameraLookAtMessage':m['look_at']=[.35,0,.8]
 messages.append([0.,m])
direction=np.asarray(r['reference'][-1][:2])-r['reference'][0][:2];angle=math.atan2(direction[1],direction[0]);c,s=math.cos(angle),math.sin(angle);rot=np.array([[c,s],[-s,c]])
add(0,'SetOrientationMessage','/tracking',wxyz=[math.cos(angle/2),0,0,-math.sin(angle/2)])
# World grid travels under the tracked robot; it is not a decorative moving floor.
grid=[]
for v in range(-8,13):grid.extend([[[v,-8,0],[v,12,0]],[[-8,v,0],[12,v,0]]])
lines(0,'/tracking/ground-grid',grid,[205,213,205],1)
# Current candidates and measured history keep the translucent body legible.
color=[86,126,92] if a.kind=='optimized' else [180,115,111]
observed=np.asarray(r['observed']);history=[[],[]];last_update=None
for frame,t in enumerate(state['time']):
 absolute=float(state['observed'][frame,0]);body_positions=state['positions'][frame]
 xy=rot@body_positions[1,:2];add(t,'SetPositionMessage','/tracking',position=[-float(xy[0]),-float(xy[1]),0])
 for body,(pos,quat) in enumerate(zip(body_positions,state['orientations'][frame])):
  add(t,'SetPositionMessage',f'/tracking/body-{body}',position=pos.tolist());add(t,'SetOrientationMessage',f'/tracking/body-{body}',wxyz=quat.tolist())
 skeleton=body_positions[state['edges']];lines(t,'/tracking/skeleton',skeleton,[53,75,69],3)
 add(t,'PointCloudMessage','/tracking/joints',props=dict(points=array(body_positions[state['robot']]),colors=array([65,86,77],'u1'),point_size=.023,point_shape='circle',point_shading='flat',precision='float32',scale=1.))
 palms=state['observed'][frame,1:7].reshape(2,3)
 for h in range(2):
  history[h].append(palms[h]);points=np.asarray(history[h]);lines(t,f'/tracking/palm-history-{h}',np.stack([points[:-1],points[1:]],axis=1) if len(points)>1 else np.array([[points[0],points[0]]]),[47,66,52] if h==0 else [78,117,115],3)
 add(t,'PointCloudMessage','/tracking/current-palms',props=dict(points=array(palms),colors=array([color,[114,151,147]] if a.kind=='optimized' else [color,[194,151,145]],'u1'),point_size=.06,point_shape='circle',point_shading='flat',precision='float32',scale=1.))
 u=next((u for u in reversed(r['updates']) if u['time']<=absolute+1e-6),r['updates'][0]);valid=absolute<=r['interactionEnd']+1e-6
 if u['sourceIndex']!=last_update:
  for n,path in enumerate(np.asarray(u['paths'])):
   lines(t,f'/tracking/current-candidate-{n}',np.stack([path[:-1],path[1:]],axis=2).reshape(-1,2,3),color if n in u['elites'] or n==u['applied'] else [186,197,182],3 if n==u['applied'] else 1)
  last_update=u['sourceIndex']
 for n in range(len(u['paths'])):add(t,'SetSceneNodeVisibilityMessage',f'/tracking/current-candidate-{n}',visible=bool(valid))
# Remove unused source buffers and remap all binary references.
used={};packed=[]
def remap(value):
 if isinstance(value,dict):
  if '__binary_index' in value:
   old=value['__binary_index']
   if old not in used:used[old]=len(packed);packed.append(buffers[old])
   value['__binary_index']=used[old]
  else:
   for v in value.values():remap(v)
 elif isinstance(value,list):
  for v in value:remap(v)
remap(messages);write_recording(root/f'assets/recordings/mpc-context-{a.kind}.viser',record,packed)
process_path.write_text('window.CLEAR_MPC_PROCESS='+json.dumps(process,separators=(',',':'))+';\n')
print(a.kind,'context:',len(messages),'messages, 40 s, measured skeleton and transparent geometry')
