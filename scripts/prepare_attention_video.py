"""Prepare exact native Viser geometry and body transforms for offscreen rendering."""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from recording_io import read_recording

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
ROOT=Path(__file__).resolve().parents[1]
reference=json.loads((ROOT/'attention/attention.json').read_text())
names=['maze-e03-highmass-g1-clear','maze-e03-highmass-spot-arm-clear','maze-e03-parallel-terrain-g1-clear']
for case,name in zip(reference['cases'],names,strict=True):
    record,buffers=read_recording(ROOT/f'assets/recordings/{name}.viser')
    meshes={};local_positions={};local_quats={}
    body_names=sorted({m['name'] for _,m in record['messages'] if m['type']=='FrameMessage' and m['name'].startswith('/body-')},key=lambda n:int(n.split('-')[-1]))
    bodies={n:i for i,n in enumerate(body_names)}
    for t,m in record['messages']:
        if t>0:continue
        n=m.get('name');kind=m['type']
        if kind=='MeshMessage':meshes[n]=m['props']
        elif kind=='SetPositionMessage':local_positions[n]=m['position']
        elif kind=='SetOrientationMessage':local_quats[n]=m['wxyz']
    arrays={};metadata=[]
    scene=case['frames'][0]['scene'];keys=case['frames'][0]['keys']
    object_bodies={}
    for obj in scene['objects']:
        matches=[n for n in body_names if np.linalg.norm(np.asarray(local_positions.get(n,[0,0,0]))[:2]-obj['pose'][:2])<1e-4]
        assert len(matches)==1,(obj['object_id'],matches)
        object_bodies[matches[0]]=obj['object_id']
    for i,(name,props) in enumerate(meshes.items()):
        vertices=np.frombuffer(buffers[props['vertices']['__binary_index']],dtype='<f4').reshape(-1,3).copy()
        faces=np.frombuffer(buffers[props['faces']['__binary_index']],dtype='<u4').reshape(-1,3).copy()
        rot=Rotation.from_quat(local_quats.get(name,[1,0,0,0]),scalar_first=True)
        vertices=rot.apply(vertices)*props.get('scale',1)+local_positions.get(name,[0,0,0])
        tri=vertices[faces];norm=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);vn=np.zeros_like(vertices)
        for column in range(3):np.add.at(vn,faces[:,column],norm)
        vn/=np.maximum(np.linalg.norm(vn,axis=1,keepdims=True),1e-12)
        body=name.rpartition('/')[0];key=None
        if body in object_bodies:
            key=next(j for j,k in enumerate(keys) if k['source_id']==f'object:{object_bodies[body]}')
        elif body=='/body-0':
            lo=vertices.min(0);hi=vertices.max(0)
            if hi[2]-lo[2]<.05:key=next(j for j,k in enumerate(keys) if k['kind']=='floor')
            else:
                bounds=np.array([lo[0],lo[1],hi[0],hi[1]])
                matches=[j for j,k in enumerate(keys) if 'bounds' in k and np.max(np.abs(bounds-k['bounds']))<1e-4]
                assert len(matches)==1,(name,bounds,matches)
                key=matches[0]
        arrays[f'vertices_{i}']=vertices.astype('f4');arrays[f'normals_{i}']=vn.astype('f4');arrays[f'faces_{i}']=faces
        metadata.append(dict(name=name,body=bodies[body],key=key,color=props['color']))
    positions=np.zeros((len(bodies),3));quats=np.tile([1.,0,0,0],(len(bodies),1));times=[];ps=[];qs=[];last=None
    for t,m in record['messages']:
        n=m.get('name');kind=m['type']
        if n not in bodies or kind not in ['SetPositionMessage','SetOrientationMessage']:continue
        if last is not None and t!=last:
            times.append(last);ps.append(positions.copy());qs.append(quats.copy())
        last=t
        if kind=='SetPositionMessage':positions[bodies[n]]=m['position']
        else:quats[bodies[n]]=m['wxyz']
    times.append(last);ps.append(positions.copy());qs.append(quats.copy())
    arrays.update(time=np.asarray(times),positions=np.asarray(ps),quaternions=np.asarray(qs))
    assert np.all(np.diff(times)>0)
    target=a.output/case['id'];target.mkdir(parents=True,exist_ok=True)
    np.savez(target/'geometry.npz',**arrays)
    (target/'scene.json').write_text(json.dumps(dict(id=case['id'],title=case['title'],body=case['body'],
        sourceRecording=names[reference['cases'].index(case)],meshes=metadata,bodies=body_names,
        objectBodies=object_bodies,duration=times[-1],scene=scene,
        egoBody=bodies['/body-16' if case['body']=='g1' else '/body-1'],
        egoOffset=[.14,0,.30] if case['body']=='g1' else [.38,0,.10]),indent=2)+'\n')
    print('PASS',case['title'],len(meshes),'native meshes',len(times),'recorded poses',flush=True)
