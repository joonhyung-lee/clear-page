"""Single EEF lanes and outlined 3D anchors, preserving recorded poses and paths."""
import copy
import itertools
import shutil
from pathlib import Path
import numpy as np
import trimesh
from recording_io import read_recording, write_recording, compact_buffers
from repair_replay_annotations import SCENES, ROOT

def refine(scene):
    target=ROOT/f'assets/recordings/{scene}.viser'
    source=ROOT/f'.git/replay-annotation-v2/{scene}.viser'
    source.parent.mkdir(parents=True,exist_ok=True)
    if not source.exists():shutil.copyfile(target,source)
    record,buffers=read_recording(source)
    if any(m['type']=='BatchedMeshesMessage' and m.get('name','').endswith('-outline') for _,m in record['messages']):
        # A fresh checkout may already contain the finished style and no local archive.
        print(scene,'already has outlined mesh anchors; retained existing style',flush=True)
        return
    def arr(ref,width=3):return np.frombuffer(buffers[ref['__binary_index']],ref['dtype']).reshape(-1,width)
    def pack(values,dtype='<f4'):
        a=np.asarray(values,dtype=dtype);buffers.append(a.tobytes());return dict(__binary_index=len(buffers)-1,dtype=a.dtype.str)
    def overlay(name):return any(s in name for s in ('overlay/','object-motion/','waypoint-anchors','reference-path','palm-centers','palm-history'))
    def softened(ref):return pack(np.round(arr(ref)*.72+255*.28),'|u1')
    def sample_path(path,count=10):
        path=np.asarray(path)
        distance=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(path,axis=0),axis=1))]
        keep=np.r_[True,np.diff(distance)>1e-8]
        return np.column_stack([np.interp(np.linspace(0,distance[-1],count),distance[keep],path[keep,i]) for i in range(3)])
    # Sample EEF anchors along the measured trace, including its bends.
    anchor_paths={}
    for _,m in record['messages']:
        if m.get('name')=='/eef-overlay/trace' and m['type']=='LineSegmentsMessage':
            segments=arr(m['props']['points']).reshape(-1,2,3)
            anchor_paths['/eef-overlay/anchors']=np.vstack([segments[0,0],segments[:,1]])
    native_points=[]
    for _,m in record['messages']:
        if m.get('name')=='/native-overlay/current-0':
            props=m.get('props',m.get('updates',{}))
            if 'points' in props:native_points.extend(arr(props['points']))
    if native_points:anchor_paths['/native-overlay/anchors-0']=np.asarray(native_points)
    remove={'/eef-overlay/lane-left','/eef-overlay/lane-right','/eef-overlay/recent','/eef-overlay/time-dots','/native-overlay/eef-lane-left','/native-overlay/eef-lane-right'}
    sphere=trimesh.creation.icosphere(subdivisions=2,radius=1.)
    points={m['name']:m['props'] for _,m in record['messages'] if m['type']=='PointCloudMessage' and overlay(m['name']) and m['name'] not in remove}
    messages=[]
    for t,message in record['messages']:
        m=copy.deepcopy(message);name=m.get('name','')
        if name in remove:continue
        props=m.get('props',m.get('updates',{}))
        if overlay(name) and 'colors' in props:props['colors']=softened(props['colors'])
        if overlay(name) and 'line_width' in props:props['line_width']=5.5 if 'ghost' in name else 6.
        if 'object-ghost-' in name and 'colors' in props:
            if 'points' in props:
                # The original G1 ghost used short corner brackets. Join the
                # recorded box corners into a complete twelve-edge silhouette.
                vertices=arr(props['points']);low=vertices.min(axis=0);high=vertices.max(axis=0)
                corners=np.array(list(itertools.product(*zip(low,high))))
                edges=[[a,b] for i,a in enumerate(corners) for b in corners[i+1:] if np.count_nonzero(a!=b)==1]
                props['points']=pack(edges)
                props['colors']=pack(np.broadcast_to([35,42,47],np.shape(edges)),'|u1')
            else:props['colors']=pack(np.tile([35,42,47],(len(arr(props['colors'])),1)),'|u1')
            props['line_width']=3.
        if name in points:
            if 'anchor' in name:
                if 'points' in props:props['points']=pack(sample_path(anchor_paths.get(name,arr(props['points']))))
                if 'colors' in props:props['colors']=pack(np.tile(arr(props['colors'])[0],(10,1)),'|u1')
            radius=.035 if 'current' in name else .0275
            if m['type']=='PointCloudMessage':
                count=len(arr(props['points']))
                m['type']='BatchedMeshesMessage'
                m['props']=dict(vertices=pack(sphere.vertices*radius),faces=pack(sphere.faces,'<u4'),
                    batched_positions=props['points'],batched_wxyzs=pack(np.tile([1,0,0,0],(count,1))),
                    batched_colors=props['colors'],batched_scales=None,batched_opacities=None,lod='off',wireframe=False,
                    opacity=None,flat_shading=False,side='front',material='standard',scale=1.,cast_shadow=False,receive_shadow=False)
                rim=copy.deepcopy(m);rim['name']=name+'-outline';rim['props'].update(vertices=pack(sphere.vertices*radius*1.16),batched_colors=pack([[18,20,19]],'|u1'),side='back')
            elif m['type']=='SceneNodeUpdateMessage':
                props=m['updates'];props={ {'points':'batched_positions','colors':'batched_colors'}.get(k,k):v for k,v in props.items() if k in ['points','colors'] }
                if 'batched_positions' in props:props['batched_wxyzs']=pack(np.tile([1,0,0,0],(len(arr(props['batched_positions'])),1)))
                m['updates']=props;rim=copy.deepcopy(m);rim['name']=name+'-outline';rim['updates'].pop('batched_colors',None)
            else:
                rim=copy.deepcopy(m);rim['name']=name+'-outline'
            messages.extend([[t,rim],[t,m]])
        else:messages.append([t,m])
    # Outline only real mesh creases; omit the triangulation diagonals.
    ghosts={m['name']:m for _,m in messages if m['type']=='MeshMessage' and m.get('name','').startswith('/reference-ghost/')}
    for name,ghost in ghosts.items():
        props=ghost['props']
        mesh=trimesh.Trimesh(vertices=arr(props['vertices']),faces=arr(props['faces']),process=True)
        edges=mesh.face_adjacency_edges[mesh.face_adjacency_angles>np.deg2rad(15)]
        segments=mesh.vertices[edges]
        outline=name+'-outline'
        messages.append([0.,dict(type='LineSegmentsMessage',name=outline,props=dict(points=pack(segments),colors=pack(np.broadcast_to([35,42,47],segments.shape),'|u1'),line_width=3.,scale=props.get('scale',1.)))])
        for t,m in list(messages):
            if m.get('name')==name and m['type'] in ['SetPositionMessage','SetOrientationMessage','SetSceneNodeVisibilityMessage']:
                clone=copy.deepcopy(m);clone['name']=outline;messages.append([t,clone])
    # One translucent tube follows the exact recorded Spot EEF centerline.
    # It replaces the duplicated center/recent/left/right lanes, without smoothing motion.
    for t,m in messages:
        if m.get('name')!='/eef-overlay/trace' or m['type']!='LineSegmentsMessage':continue
        props=m['props'];segments=arr(props['points']).reshape(-1,2,3);vertices=[];faces=[]
        for a,b in segments:
            delta=b-a;length=np.linalg.norm(delta)
            if length<1e-7:continue
            direction=delta/length;side=np.cross(direction,[0,0,1.])
            if np.linalg.norm(side)<1e-5:side=np.cross(direction,[0,1.,0])
            side/=np.linalg.norm(side);up=np.cross(direction,side)
            theta=np.arange(8)*np.pi/4;ring=.018*(np.cos(theta)[:,None]*side+np.sin(theta)[:,None]*up)
            offset=len(vertices);vertices.extend(a+ring);vertices.extend(b+ring)
            for j in range(8):k=(j+1)%8;faces.extend([[offset+j,offset+k,offset+8+k],[offset+j,offset+8+k,offset+8+j]])
        color=arr(props['colors'])[0].tolist()
        m['type']='MeshMessage';m['props']=dict(vertices=pack(vertices),faces=pack(faces,'<u4'),color=color,wireframe=False,opacity=.62,flat_shading=False,side='double',material='standard',scale=1.,cast_shadow=False,receive_shadow=False)
    if scene=='mpc-spot-native':
        # These archived overlay nodes never received a visibility message.
        # Set it explicitly instead of relying on a render-only camera override.
        for _,m in list(messages):
            if m['type'] in ['BatchedMeshesMessage','LineSegmentsMessage','MeshMessage'] and overlay(m.get('name','')):
                messages.append([0.,dict(type='SetSceneNodeVisibilityMessage',name=m['name'],visible=True)])
    record['messages']=sorted(messages,key=lambda pair:pair[0])
    record,buffers=compact_buffers(record,buffers);write_recording(target,record,buffers)
    print(scene,'outlined anchors:',len(points),'single EEF lane',flush=True)
if __name__=='__main__':
    for scene in SCENES:refine(scene)
