"""Offline native Viser export of the same recorded physics task used for planning."""
import argparse,copy,json
from pathlib import Path
import numpy as np
import trimesh
from types import SimpleNamespace
from export_teaser_method import Recording
from replay_geometry import mesh
ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--baked',type=Path,required=True);a=p.parse_args()
 d=json.loads((ROOT/'assets/code-native-data.js').read_text().split('=',1)[1].strip().removesuffix(';'))
 track={k:v for k,v in np.load(a.baked).items()};names={}
 for b,name in enumerate(track['body_names']):
  if name.startswith('robot/'):names[b]='/layers/embodiment/body-'+str(b)
  elif name.startswith('object/') :names[b]='/layers/objects/object-0'
  elif name.startswith('object_'):names[b]='/layers/objects/object-'+name.split('/')[0].split('_')[1]
  else:names[b]='/layers/scene/body-'+str(b)
 model=SimpleNamespace(**{k:track[k] for k in ['geom_type','geom_size','geom_dataid','mesh_vert','mesh_face','mesh_vertadr','mesh_vertnum','mesh_faceadr','mesh_facenum']})
 r=Recording();r.record['durationSeconds']=float(track['time'][-1]-track['time'][0]+.1)
 r.emit('SetCameraPositionMessage',position=[6,5.95,22],initial=True);r.emit('SetCameraLookAtMessage',look_at=[6,6,0],initial=True);r.emit('SetCameraFovMessage',fov=.7,initial=True)
 for b,name in names.items():r.frame(name)
 for i in range(len(track['geom_type'])):
  if track['geom_group'][i]==3:continue
  rgba=track['geom_rgba'][i]
  if rgba[3]<=0:continue
  geom=mesh(model,i);name=names[int(track['geom_body'][i])]+f'/mesh-{i}'
  color=(rgba[:3]*255).astype(int).tolist()
  if name.startswith('/layers/scene/'):color=[214,222,217] if model.geom_type[i]!=0 else [244,247,242]
  if name.startswith('/layers/objects/'):color=[172,151,119]
  r.mesh(name,geom.vertices,geom.faces,color,track['geom_pos'][i],track['geom_quat'][i],float(rgba[3]))
 rootbody=list(track['body_names']).index('robot/pelvis')
 measured=[]
 for k,t in enumerate(track['time']):
  time=float(t-track['time'][0])
  for b,name in names.items():
   if b==0 and k:continue
   r.position(name,track['xpos'][k,b],max(0,time-1e-6));r.emit('SetOrientationMessage',max(0,time-1e-6),name=name,wxyz=track['xquat'][k,b].tolist())
  measured.append([time,*track['xpos'][k,rootbody,:2]])
  if k==0:
   initial=copy.deepcopy(r);initial.record['durationSeconds']=8;initial.save(ROOT/'assets/recordings/code-observation.viser')
 for i,o in enumerate(d['scene']['objects']):
  r.label(f'/layers/objects/object-{i}/label','Object '+str(i),[0,-.55,o['size'][2]/2+.06])
 for key,color in [('start',[66,113,162]),('goal',[40,129,89])]:
  ring=trimesh.creation.annulus(r_min=.14,r_max=.22,height=.018)
  r.mesh('/query/'+key,ring.vertices,ring.faces,color,[*d['scene'][key][:2],.04])
  r.label('/query/'+key+'-label',key.title(),[*d['scene'][key][:2],.12])
 from build_code_native import path_graph
 for path,attempt in zip(d['referencePaths'],d['execution']['attempts'],strict=True):
  prefix='/reference/'+str(path['object']);path_graph(r,d['scene'],path,prefix,[94,146,121])
  r.emit('SetSceneNodeVisibilityMessage',name=prefix,visible=False)
  r.emit('SetSceneNodeVisibilityMessage',attempt['push'][0]-1e-6,name=prefix,visible=True)
  r.emit('SetSceneNodeVisibilityMessage',attempt['push'][1]-1e-6,name=prefix,visible=False)
 # A growing trail is measured motion; no future execution is drawn in advance.
 xyz=np.array([[x,y,.07] for t,x,y in measured]);r.lines('/measured/trail',[[xyz[0],xyz[0]]],[66,113,162],3.)
 for k in range(1,len(measured),3):r.line_update('/measured/trail',np.stack([xyz[:k],xyz[1:k+1]],1),[66,113,162],max(0,measured[k][0]-1e-6))
 r.save(ROOT/'assets/recordings/code-execution.viser')
 d['execution']['measuredRoute']=measured;d['execution']['bodyNodes']=names
 (ROOT/'assets/code-native-data.js').write_text('window.CLEAR_CODE_NATIVE='+json.dumps(d,separators=(',',':'))+';\n')
 print('PASS native source states',len(measured),'duration',measured[-1][0],'goal error',np.linalg.norm(np.array(measured[-1][1:])-d['scene']['goal'][:2]),flush=True)
if __name__=='__main__':main()
