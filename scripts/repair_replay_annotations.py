"""Repair replay annotation visibility without changing any measured body poses."""
import copy
import re
from pathlib import Path
import numpy as np
from recording_io import read_recording, write_recording, compact_buffers
from design_tokens import rgb
ROOT=Path(__file__).resolve().parents[1]
SCENES=['mpc-optimized-full','mpc-baseline','mpc-spot-optimized','mpc-spot-native']

def repair(scene):
    path=ROOT/f'assets/recordings/{scene}.viser'
    record,buffers=read_recording(path)
    if any(m['type']=='BatchedMeshesMessage' and m.get('name','').endswith('-outline') for _,m in record['messages']):
        print(scene,'retaining refined mesh anchors; use refine_replay_annotations.py for their style')
        return
    def poses(messages):
        return [(t,m) for t,m in messages if re.fullmatch(r'(?:/tracking)?/body-\d+',m.get('name',''))]
    before=copy.deepcopy(poses(record['messages']))
    def pack(values,dtype='<f4'):
        arr=np.asarray(values,dtype=dtype);buffers.append(arr.tobytes())
        return dict(__binary_index=len(buffers)-1,dtype=arr.dtype.str)
    def array(ref):return np.frombuffer(buffers[ref['__binary_index']],ref['dtype']).reshape(-1,3)
    def overlay(name):return any(s in name for s in ('overlay/','object-motion/','waypoint-anchors','reference-path','palm-centers','palm-history'))
    messages=[]
    for t,m in record['messages']:
        name=m.get('name','')
        if overlay(name) and name.endswith('-outline'):continue
        props=m.get('props',m.get('updates',{}))
        if overlay(name):
            color=rgb('red',600) if 'eef' in name or 'palm' in name else rgb('green',600) if 'observed' in name or 'object-motion' in name else rgb('blue',600)
            if 'colors' in props:props['colors']=pack(np.tile(color,(len(array(props['colors'])),1)),'|u1')
            if 'point_size' in props:props['point_size']=.045 if 'current' in name else .032
            if 'line_width' in props:props['line_width']=3.5 if 'lane' in name or 'ghost' in name else 4.
            if m['type']=='SetSceneNodeVisibilityMessage':m['visible']=True
        messages.append([t,m])
    # The saved object mesh at actual plan anchors supplies the missing target ghosts.
    if scene.startswith('mpc-spot-') and not any('/reference-ghost/' in m.get('name','') for _,m in messages):
        mesh=next(m for _,m in messages if m['type']=='MeshMessage' and m['name'].startswith('/body-21/'))
        initial=next(m['position'] for _,m in messages if m['type']=='SetPositionMessage' and m['name']=='/body-21')
        orientation=next(m['wxyz'] for _,m in messages if m['type']=='SetOrientationMessage' and m['name']=='/body-21')
        anchors=next(m for _,m in messages if m['type']=='PointCloudMessage' and m['name'] in ['/object-overlay/anchors','/native-overlay/object-anchors'])
        points=array(anchors['props']['points'])
        for i,p in enumerate(points[[len(points)//2,-1]]):
            name=f'/reference-ghost/{i}';ghost=copy.deepcopy(mesh);ghost['name']=name
            ghost['props'].update(color=rgb('blue',500),opacity=.18,cast_shadow=False,receive_shadow=False)
            messages.extend([[0,ghost],[0,dict(type='SetPositionMessage',name=name,position=[float(p[0]),float(p[1]),initial[2]])],[0,dict(type='SetOrientationMessage',name=name,wxyz=orientation)],[0,dict(type='SetSceneNodeVisibilityMessage',name=name,visible=True)]])
    # Native Spot baseline stores the measured EEF trace but no corridor rails.
    if scene=='mpc-spot-native' and not any(m.get('name')=='/native-overlay/eef-lane-left' for _,m in messages):
        traces=[m for _,m in messages if m.get('name')=='/native-overlay/eef-0' and ('props' in m or 'updates' in m)]
        trace=max(traces,key=lambda m:len(array(m.get('props',m.get('updates'))['points'])))
        points=array(trace.get('props',trace.get('updates'))['points']).reshape(-1,2,3)
        direction=points[-1,-1]-points[0,0];side=np.array([-direction[1],direction[0],0.]);side*=.045/max(np.linalg.norm(side),1e-8)
        for label,sign in [('left',1),('right',-1)]:
            name='/native-overlay/eef-lane-'+label;values=points+side*sign
            messages.extend([[0,dict(type='LineSegmentsMessage',name=name,props=dict(points=pack(values),colors=pack(np.broadcast_to(rgb('red',600),values.shape),'|u1'),line_width=3.5,scale=1.))],[0,dict(type='SetSceneNodeVisibilityMessage',name=name,visible=True)]])
    record['messages']=sorted(messages,key=lambda p:p[0]);assert poses(record['messages'])==before
    record,buffers=compact_buffers(record,buffers);write_recording(path,record,buffers)
    print(scene,'annotations repaired; measured poses unchanged')
if __name__=='__main__':
    for scene in SCENES:repair(scene)
