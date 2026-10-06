"""Check native example geometry, flow fidelity and sequential collision results."""
import copy,json,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from recording_io import read_recording,validate_binary_arrays
ROOT=Path(__file__).resolve().parents[1]

def data():return json.loads((ROOT/'assets/code-native-data.js').read_text().split('=',1)[1].strip().removesuffix(';'))

def check():
 d=data();scene=d['scene'];assert len(d['states'])==31
 assert d['rank']==[-1,0,1] and d['provenance']['decoding']=='raw'
 old=json.loads((ROOT/'assets/teaser-flow-data.js').read_text().split('=',1)[1].strip().removesuffix(';'))
 # Regression fixture: the previous forced teaser paths really leave the map.
 w,h=old['scene']['world_size']
 assert any(not(0<=p[0]<=w and 0<=p[1]<=h) for path in old['referenceFlow'][0]['states'][-1] for p in path['poses'])
 sys.path.insert(0,str(ROOT/'clear-standalone-anonymous/runtime'))
 from experiments.exp3.trajectory_v3.scenes import path_collision
 from experiments.exp3.trajectory_v3.contracts import ObjectPath
 for path in d['states'][-1]['paths']:
  assert not path_collision(scene,ObjectPath(path['object'],tuple(map(tuple,path['poses']))))
 work=copy.deepcopy(scene)
 for path,reported in zip(d['referencePaths'],d['checks'],strict=True):
  i=path['object'];poses=path['poses'];assert poses[0]==work['objects'][i]['pose']
  assert all(0<=p[0]<=scene['world_size'][0] and 0<=p[1]<=scene['world_size'][1] for p in poses)
  assert not path_collision(work,ObjectPath(i,tuple(map(tuple,poses)))) and reported['collision'] is False
  work['objects'][i]['pose']=poses[-1]
 records={}
 for kind in ['representation','ordering','generation','validation']:
  record,buffers=read_recording(ROOT/f'assets/recordings/code-{kind}.viser');validate_binary_arrays(record,buffers)
  records[kind]=(record,buffers)
  names={m.get('name') for t,m in record['messages']}
  assert {'/layers/embodiment','/layers/objects','/layers/scene'}<=names
  assert not any('contact-field' in n for n in names if n)
  meshes=[m for t,m in record['messages'] if m['type']=='MeshMessage' and m['name'].startswith('/layers/embodiment/body-')]
  assert len(meshes)>=30
  for i,o in enumerate(scene['objects']):
   position=next(m['position'] for t,m in record['messages'] if t==0 and m['type']=='SetPositionMessage' and m['name']==f'/layers/objects/object-{i}')
   np.testing.assert_allclose(position[:2],o['pose'][:2],atol=1e-6)
   assert abs(position[2]-o['size'][2]/2)<.1
 record,buffers=records['generation']
 for state in d['states']:
  time=max(0,state['t']*6-1e-6)
  for path in state['paths']:
   i=path['object'];xyz=np.array([[*p[:2],scene['objects'][i]['size'][2]/2+.015] for p in path['poses']])
   lane=next(m['updates']['points'] for t,m in record['messages'] if abs(t-time)<1e-10 and m['type']=='SceneNodeUpdateMessage' and m['name']==f'/flow/{i}/lane')
   actual=np.frombuffer(buffers[lane['__binary_index']],'<f4').reshape(-1,2,3)
   np.testing.assert_allclose(actual,np.stack([xyz[:-1],xyz[1:]],1),atol=2e-6)
   for slot,index in enumerate([len(xyz)//2,len(xyz)-1]):
    messages=[m for t,m in record['messages'] if t<=time+1e-10 and m.get('name')==f'/flow/{i}/ghost-{slot}']
    position=next(m['position'] for m in reversed(messages) if m['type']=='SetPositionMessage')
    orientation=next(m['wxyz'] for m in reversed(messages) if m['type']=='SetOrientationMessage')
    np.testing.assert_allclose(position,xyz[index])
    np.testing.assert_allclose(orientation,Rotation.from_euler('z',path['poses'][index][2]).as_quat(scalar_first=True))
  assert len([m for t,m in record['messages'] if t==0 and m['type']=='LineSegmentsMessage' and '/ghost-' in m['name']])==4
 record,_=records['validation']
 for order,path in enumerate(d['referencePaths']):
  i=path['object'];m=next(m for t,m in record['messages'] if t==(order+1)*4-1e-6 and m['type']=='SetPositionMessage' and m['name']==f'/layers/objects/object-{i}')
  np.testing.assert_allclose(m['position'][:2],path['poses'][-1][:2])
 # The exact navigation contract must close the initial route and open the final one.
 from experiments.exp3.trajectory_v3.navigation import TerrainNavigator
 from experiments.exp3.trajectory_v3.plan_audit import GeometryOnlyPredictor
 from experiments.exp3.trajectory_v3.oracle_capability import robot_after
 from types import SimpleNamespace
 nav=TerrainNavigator(GeometryOnlyPredictor(),resolution=.1,threshold=.8);body=SimpleNamespace(footprint_radius_m=.4)
 assert nav.analyze(scene,body).goal_route is None
 # The fresh generated candidate must also open the route, independently of
 # the archived reference used for the physical execution.
 from experiments.exp3.trajectory_v3.oracle_capability import approach_point
 generated=copy.deepcopy(scene)
 for raw in d['states'][-1]['paths']:
  candidate=ObjectPath(raw['object'],tuple(map(tuple,raw['poses'])))
  assert not path_collision(generated,candidate)
  assert nav.analyze(generated,body).route_to(approach_point(candidate)) is not None
  generated['objects'][candidate.object_id]['pose']=list(candidate.goal)
  generated['start']=[*robot_after(candidate,generated['world_size'],.4),0.]
 assert nav.analyze(generated,body).goal_route is not None

 last=d['referencePaths'][-1];path=ObjectPath(last['object'],tuple(map(tuple,last['poses'])))
 work['start']=[*robot_after(path,work['world_size'],.4),0.]
 assert nav.analyze(work,body).goal_route is not None
 assert [r['kind'] for r in d['routes']]==['approach','approach','goal']
 for row in d['representation']['attention']:assert abs(sum(row)-1)<2e-6
 assert np.isfinite(d['representation']['tokens']).all()
 assert d['execution']['status']=='goal_reached'
 execution,buffers=read_recording(ROOT/'assets/recordings/code-execution.viser')
 route=d['execution']['measuredRoute'];assert len(route)>1200
 assert np.linalg.norm(np.asarray(route[-1][1:])-scene['goal'][:2])<.2
 poses=[(t,m['position']) for t,m in execution['messages'] if m['type']=='SetPositionMessage' and m['name']=='/layers/embodiment/body-1']
 assert len(poses)==len(route)
 np.testing.assert_allclose(np.asarray([p[1][:2] for p in poses]),np.asarray(route)[:,1:],atol=1e-7)
 for record,_ in [*records.values(),(execution,buffers)]:
  eye=next(m['position'] for t,m in record['messages'] if m['type']=='SetCameraPositionMessage')
  target=next(m['look_at'] for t,m in record['messages'] if m['type']=='SetCameraLookAtMessage')
  assert np.linalg.norm(np.array(eye[:2])-target[:2])<.1 and eye[2]>20
 print('PASS component features, sampled selection, top-down figures, 31 raw states, sequential open routes, and matching recorded goal arrival')
if __name__=='__main__':check()
