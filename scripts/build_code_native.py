"""Native Viser figures sharing one verified maze query and metric coordinate frame."""
import copy,json,tempfile
from pathlib import Path
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation
from export_teaser_method import Recording,box_edges
from recording_io import read_recording,write_recording
from render_teaser_method import render
ROOT=Path(__file__).resolve().parents[1]
GREEN=[45,120,88];BLUE=[76,119,159];ORANGE=[181,115,69]

def data():
 text=(ROOT/'assets/code-native-data.js').read_text();return json.loads(text.split('=',1)[1].strip().removesuffix(';'))

def transforms(record,time=0):
 pos={};quat={};visible={}
 for t,m in record['messages']:
  if t>time:continue
  name=m.get('name','')
  if m['type']=='SetPositionMessage':pos[name]=np.array(m['position'])
  if m['type']=='SetOrientationMessage':quat[name]=m['wxyz']
  if m['type']=='SetSceneNodeVisibilityMessage':visible[name]=m['visible']
 def world(name):
  if not name:return np.eye(3),np.zeros(3)
  pr,pp=world(name.rpartition('/')[0]);r=Rotation.from_quat(quat.get(name,[1,0,0,0]),scalar_first=True).as_matrix()
  return pr@r, pp+pr@pos.get(name,np.zeros(3))
 def shown(name):
  return not name or visible.get(name,True) and shown(name.rpartition('/')[0])
 return world,shown

def mesh_box(r,name,size,position,color,opacity=1):
 mesh=trimesh.creation.box(extents=size);r.mesh(name,mesh.vertices,mesh.faces,color,position,opacity=opacity)

def robot(r,scene):
 record,buffers=read_recording(ROOT/'assets/recordings/structure-g1.viser');world,_=transforms(record)
 yaw=Rotation.from_euler('z',scene['start'][2]);base=np.array([*scene['start'][:2],0.])
 for t,m in record['messages']:
  if t!=0 or m['type']!='MeshMessage' or not m['name'].startswith('/g1/') or '/mesh-' not in m['name']:continue
  p=m['props'];rot,pos=world(m['name']);vertices=np.frombuffer(buffers[p['vertices']['__binary_index']],'<f4').reshape(-1,3)
  faces=np.frombuffer(buffers[p['faces']['__binary_index']],'<u4').reshape(-1,3)
  xyz=yaw.apply(vertices@rot.T+pos)+base
  r.mesh('/layers/embodiment/'+m['name'].strip('/').replace('/','-'),xyz,faces,p['color'],[0,0,0],opacity=.8)
 # Physical joint locations from the same native initial pose.
 joints=[]
 for t,m in record['messages']:
  if t==0 and m['type']=='FrameMessage' and m['name'].startswith('/g1/body-'):
   _,p=world(m['name']);joints.append(yaw.apply(p)+base)
 ball=trimesh.creation.icosphere(subdivisions=1,radius=.035)
 for i,p in enumerate(joints):r.mesh(f'/layers/embodiment/joint-{i}',ball.vertices,ball.faces,BLUE,p)

def base(d):
 scene=d['scene'];r=Recording()
 r.record,r.buffers=read_recording(ROOT/'assets/recordings/code-observation.viser')
 r.frames={m.get('name','') for t,m in r.record['messages'] if m['type']=='FrameMessage'}|{''}
 r.record['durationSeconds']=10
 for i,o in enumerate(scene['objects']):
  r.label(f'/layers/objects/object-{i}/label','Object '+str(i),[0,-.55,o['size'][2]/2+.06])
 for key,color in [('start',BLUE),('goal',GREEN)]:
  ring=trimesh.creation.annulus(r_min=.14,r_max=.22,height=.018)
  r.mesh('/query/'+key,ring.vertices,ring.faces,color,[*scene[key][:2],.04]);r.label('/query/'+key+'-label',key.title(),[*scene[key][:2],.2])
 return r

def route_lane(r,name,points,color=BLUE):
 xy=np.asarray(points)[:,:2];xyz=np.column_stack([xy,np.full(len(xy),.07)])
 r.lines(name,np.stack([xyz[:-1],xyz[1:]],1),color,4.)


def center(scene,i,pose):return np.array([*pose[:2],scene['objects'][i]['size'][2]/2+.015])

def path_graph(r,scene,path,prefix,color):
 i=path['object'];poses=path['poses'];points=np.array([center(scene,i,p) for p in poses])
 r.lines(prefix+'/lane',np.stack([points[:-1],points[1:]],1),color,4.)
 sphere=trimesh.creation.icosphere(subdivisions=1,radius=.065)
 for j,p in enumerate(points):r.mesh(prefix+f'/anchor-{j}',sphere.vertices,sphere.faces,color,p)
 for slot,k in enumerate([len(poses)//2,len(poses)-1]):
  name=prefix+f'/ghost-{slot}';r.lines(name,box_edges(scene['objects'][i]['size']),color,3.)
  r.position(name,points[k]);r.emit('SetOrientationMessage',name=name,wxyz=Rotation.from_euler('z',poses[k][2]).as_quat(scalar_first=True).tolist())

def update_path(r,scene,path,prefix,time):
 poses=path['poses'];i=path['object'];points=np.array([center(scene,i,p) for p in poses]);color=GREEN if i==1 else BLUE
 r.line_update(prefix+'/lane',np.stack([points[:-1],points[1:]],1),color,time)
 for j,p in enumerate(points):r.position(prefix+f'/anchor-{j}',p,time)
 for slot,k in enumerate([len(poses)//2,len(poses)-1]):
  r.position(prefix+f'/ghost-{slot}',points[k],time)
  r.emit('SetOrientationMessage',time,name=prefix+f'/ghost-{slot}',wxyz=Rotation.from_euler('z',poses[k][2]).as_quat(scalar_first=True).tolist())

def poster(r,output,time=0,offsets=None):
 # Flatten the same Viser meshes and lines at the requested time for a CPU poster.
 snap=copy.deepcopy(r.record)
 for layer,z in (offsets or {}).items():snap['messages'].append([0,dict(type='SetPositionMessage',name='/layers/'+layer,position=[0,0,z])])
 world,shown=transforms(snap,time);nodes={}
 for t,m in snap['messages']:
  if t>time:continue
  if m['type'] in ['MeshMessage','LineSegmentsMessage','LabelMessage']:nodes[m['name']]=copy.deepcopy(m)
  if m['type']=='SceneNodeUpdateMessage' and m['name'] in nodes:nodes[m['name']]['props'].update(m['updates'])
 flat=Recording();flat.record['messages']=[copy.deepcopy(e) for e in snap['messages'] if e[1]['type'].startswith('SetCamera')]
 for name,m in nodes.items():
  if not shown(name):continue
  rot,pos=world(name);p=m['props'];name='/'+name.strip('/').replace('/','-')
  if m['type']=='MeshMessage':
   v=np.frombuffer(r.buffers[p['vertices']['__binary_index']],'<f4').reshape(-1,3)@rot.T+pos
   f=np.frombuffer(r.buffers[p['faces']['__binary_index']],'<u4').reshape(-1,3)
   flat.mesh(name,v,f,p['color'],[0,0,0],opacity=p.get('opacity',1))
  elif m['type']=='LineSegmentsMessage':
   points=np.frombuffer(r.buffers[p['points']['__binary_index']],'<f4').reshape(-1,2,3)@rot.T+pos
   color=np.frombuffer(r.buffers[p['colors']['__binary_index']],'u1').reshape(-1,3)[0]
   for j,(a,b) in enumerate(points):
    if np.linalg.norm(a-b)<1e-7:continue
    tube=trimesh.creation.cylinder(radius=.022,segment=[a,b],sections=6)
    flat.mesh(name+f'-{j}',tube.vertices,tube.faces,color,[0,0,0])
  else:flat.label(name,p['text'],pos)
 with tempfile.TemporaryDirectory(prefix='clear-native-poster-') as temp:
  source=Path(temp)/'snapshot.viser';flat.save(source);render(source,output)

def build():
 d=data();scene=d['scene'];final=d['referencePaths']
 for kind in ['representation','ordering','generation','validation']:
  r=base(d)
  if kind=='representation':
   weights=np.mean(d['representation']['attention'],axis=0)
   for index,(key,weight) in enumerate(zip(d['representation']['keys'],weights)):
    k=key['kind'];group='embodiment' if k=='embodiment' else 'objects' if k=='object' else 'scene'
    name=f'/features/{group}/token-{index}'
    if k=='embodiment':
     ring=trimesh.creation.annulus(r_min=.42,r_max=.50,height=.025)
     r.mesh(name,ring.vertices,ring.faces,GREEN,[*scene['start'][:2],.08])
    elif k=='object':
     o=scene['objects'][key['object']];r.lines(name,box_edges(np.array(o['size'])+.05),GREEN,2+float(weight)*25);r.position(name,center(scene,key['object'],o['pose']))
    elif 'bounds' in key and k!='floor':
     x0,y0,x1,y1=key['bounds'];pts=np.array([[x0,y0,1.55],[x1,y0,1.55],[x1,y1,1.55],[x0,y1,1.55],[x0,y0,1.55]])
     r.lines(name,np.stack([pts[:-1],pts[1:]],1),GREEN,2+float(weight)*25)
    elif 'position' in key:
     ring=trimesh.creation.annulus(r_min=.26,r_max=.32,height=.02);r.mesh(name,ring.vertices,ring.faces,GREEN,[*key['position'][:2],.07])
   for group in ['embodiment','objects','scene']:
    r.frame('/features/'+group);r.emit('SetSceneNodeVisibilityMessage',name='/features/'+group,visible=group=='embodiment')
  elif kind=='ordering':
   for stage in ['participation','order']:r.frame('/selection/'+stage)
   for i,rank in enumerate(d['rank']):
    o=scene['objects'][i];p=center(scene,i,o['pose'])
    color=GREEN if rank>=0 else [157,164,160]
    name=f'/selection/participation/box-{i}';r.lines(name,box_edges(np.array(o['size'])+.08),color,4.);r.position(name,p)
    if rank>=0:r.label(f'/selection/order/rank-{i}',str(rank+1),p+[0,.65,.5])
   route_lane(r,'/selection/order/approach',d['routes'][0]['points'])
  elif kind=='generation':
   r.record['durationSeconds']=8
   for path in d['states'][0]['paths']:path_graph(r,scene,path,'/flow/'+str(path['object']),GREEN if path['object']==1 else BLUE)
   for state in d['states']:
    for path in state['paths']:update_path(r,scene,path,'/flow/'+str(path['object']),max(0,state['t']*6-1e-6))
   for path in final:
    xyz=np.array([center(scene,path['object'],p) for p in path['poses']]);r.lines('/reference/'+str(path['object']),np.stack([xyz[:-1],xyz[1:]],1),[155,161,155],2.)
  else:
   r.record['durationSeconds']=12
   for order,path in enumerate(final):
    i=path['object'];prefix='/validation/'+str(i);color=GREEN if i==1 else BLUE
    path_graph(r,scene,path,prefix,color)
    route_lane(r,f'/routes/step-{order}',d['routes'][order]['points'])
    r.emit('SetSceneNodeVisibilityMessage',name=f'/routes/step-{order}',visible=order==0)
    if order:r.emit('SetSceneNodeVisibilityMessage',order*4-1e-6,name=f'/routes/step-{order}',visible=True)
    poses=np.asarray(path['poses'])
    for frame in range(121):
     time=order*4+frame/30;k=frame/120*(len(poses)-1);lo=int(k);hi=min(lo+1,len(poses)-1)
     pose=(1-(k-lo))*poses[lo]+(k-lo)*poses[hi]
     # Original objects move only in this explicitly planned-state inspection.
     r.position(f'/layers/objects/object-{i}',center(scene,i,pose)-[0,0,.015],max(0,time-1e-6))
     r.emit('SetOrientationMessage',max(0,time-1e-6),name=f'/layers/objects/object-{i}',wxyz=Rotation.from_euler('z',pose[2]).as_quat(scalar_first=True).tolist())
   route_lane(r,'/routes/goal',d['routes'][-1]['points'],GREEN)
   r.emit('SetSceneNodeVisibilityMessage',name='/routes/goal',visible=False)
   r.emit('SetSceneNodeVisibilityMessage',8-1e-6,name='/routes/goal',visible=True)
  name='code-'+kind
  poster(r,ROOT/'assets/media'/f'{name}.png',6 if kind=='generation' else 8 if kind=='validation' else 0)
  r.save(ROOT/'assets/recordings'/f'{name}.viser');print('Built',name,flush=True)
 # Execution preview is rendered from its own recorded initial geometry.
 r=Recording();r.record,r.buffers=read_recording(ROOT/'assets/recordings/code-execution.viser')
 poster(r,ROOT/'assets/media/code-execution.png',0)
if __name__=='__main__':build()
