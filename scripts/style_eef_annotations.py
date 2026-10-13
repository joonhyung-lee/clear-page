"""One visible measured EEF lane, ten compact anchors and dark flat rims."""
import copy
import numpy as np
import trimesh

def style(record,buffers):
    record=copy.deepcopy(record);buffers=list(buffers)
    def array(ref):return np.frombuffer(buffers[ref['__binary_index']],ref['dtype']).reshape(-1,3)
    def pack(values,dtype='<f4'):
        a=np.asarray(values,dtype=dtype);buffers.append(a.tobytes());return dict(__binary_index=len(buffers)-1,dtype=a.dtype.str)
    def sample(path):
        d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(path,axis=0),axis=1))];keep=np.r_[True,np.diff(d)>1e-8]
        return np.column_stack([np.interp(np.linspace(0,d[-1],10),d[keep],path[keep,i]) for i in range(3)])
    native=any(m.get('name')=='/native-overlay/eef-0' for _,m in record['messages'])
    lane='/native-overlay/eef-0' if native else '/eef-overlay/trace'
    anchor='/native-overlay/anchors-0' if native else '/eef-overlay/anchors'
    current='/native-overlay/current-0' if native else '/eef-overlay/current'
    paths=[array(m.get('props',m.get('updates',{}))['points']).reshape(-1,2,3) for _,m in record['messages'] if m.get('name')==lane and 'points' in m.get('props',m.get('updates',{}))]
    segments=max(paths,key=len);path=np.vstack([segments[0,0],segments[:,1]])
    if native:
        points=[array(m.get('props',m.get('updates',{}))['points'])[0] for _,m in record['messages'] if m.get('name')==current and 'points' in m.get('props',m.get('updates',{}))]
        if len(points)>2:path=np.asarray(points)
    anchors=sample(path);segments=np.stack([path[:-1],path[1:]],axis=1)
    remove={'/eef-overlay/recent','/eef-overlay/lane-left','/eef-overlay/lane-right','/eef-overlay/time-dots'}
    messages=[];copies=[]
    existing={m.get('name') for _,m in record['messages']}
    for t,m in record['messages']:
        name=m.get('name','')
        if name in remove:continue
        if name==lane and m['type']=='SceneNodeUpdateMessage':continue
        p=m.get('props',m.get('updates',{}))
        if name==lane and m['type']=='LineSegmentsMessage':p.update(points=pack(segments),colors=pack(np.broadcast_to([176,90,111],segments.shape),'|u1'),line_width=4.5)
        if name in [anchor,anchor+'-outline'] and 'points' in p:
            p.update(points=pack(anchors),colors=pack(np.tile([35,42,47] if name.endswith('-outline') else [208,142,151],(10,1)),'|u1'))
        if name in [anchor,anchor+'-outline',current,current+'-outline'] and m['type']=='PointCloudMessage':
            p['point_size']=(.031 if 'anchors' in name else .036)*(1.18 if name.endswith('-outline') else 1.)
        if name==lane and m['type']=='SetSceneNodeVisibilityMessage':m['visible']=True
        messages.append([t,m])
        if native and name==anchor and anchor+'-outline' not in existing:
            clone=copy.deepcopy(m);clone['name']=anchor+'-outline';props=clone.get('props',clone.get('updates',{}))
            if 'colors' in props:props['colors']=pack(np.tile([35,42,47],(10,1)),'|u1')
            if 'point_size' in props:props['point_size']*=1.18
            copies.append([t,clone])
    messages.extend(copies)
    for name in [lane,anchor,anchor+'-outline',current]:messages.append([0.,dict(type='SetSceneNodeVisibilityMessage',name=name,visible=True)])
    # Two planned object poses, using the original box mesh and reference path.
    box=next(m for _,m in messages if m['type']=='MeshMessage' and m['name'].startswith('/body-21/'))
    boxpos=next(m['position'] for _,m in messages if m['type']=='SetPositionMessage' and m.get('name')=='/body-21')
    boxrot=next(m['wxyz'] for _,m in messages if m['type']=='SetOrientationMessage' and m.get('name')=='/body-21')
    refname='/native-overlay/object-reference' if native else '/object-overlay/reference'
    anchorsname='/native-overlay/object-anchors' if native else '/object-overlay/anchors'
    ref=next(m for _,m in messages if m['type']=='PointCloudMessage' and m.get('name')==anchorsname)
    planned=array(ref['props']['points'])
    mesh=trimesh.Trimesh(array(box['props']['vertices']),array(box['props']['faces']),process=True)
    edges=mesh.face_adjacency_edges[mesh.face_adjacency_angles>np.deg2rad(15)]
    outline=mesh.vertices[edges]
    for i,point in enumerate(planned[[len(planned)//2,-1]]):
        name=f'/reference-ghost/{i}'
        ghost=copy.deepcopy(box);ghost['name']=name
        ghost['props'].update(color=[166,190,218],opacity=.16,cast_shadow=False,receive_shadow=False)
        rim=dict(type='LineSegmentsMessage',name=name+'-outline',props=dict(points=pack(outline),colors=pack(np.broadcast_to([47,57,67],outline.shape),'|u1'),line_width=2.4,scale=box['props'].get('scale',1.)))
        messages.extend([[0.,ghost],[0.,rim]])
        for node in [name,name+'-outline']:
            messages.extend([[0.,dict(type='SetPositionMessage',name=node,position=[float(point[0]),float(point[1]),boxpos[2]])],[0.,dict(type='SetOrientationMessage',name=node,wxyz=boxrot)],[0.,dict(type='SetSceneNodeVisibilityMessage',name=node,visible=True)]])
    if native:
        segments=np.stack([planned[:-1],planned[1:]],axis=1)
        messages.extend([[0.,dict(type='LineSegmentsMessage',name=refname,props=dict(points=pack(segments),colors=pack(np.broadcast_to([145,178,211],segments.shape),'|u1'),line_width=4.,scale=1.))],[0.,dict(type='SetSceneNodeVisibilityMessage',name=refname,visible=True)]])
    # Keep the planned object path visible alongside the measured EEF lane.
    reference_nodes={m['name'] for _,m in messages if m['type']=='LineSegmentsMessage' and m.get('name','').startswith(('/object-overlay/reference','/object-overlay/lane-','/native-overlay/object-reference'))}
    for _,m in messages:
        if m.get('name') in reference_nodes and m['type']=='LineSegmentsMessage':m['props']['line_width']=4.
        if m.get('name') in reference_nodes and m['type']=='SetSceneNodeVisibilityMessage':m['visible']=True
    for name in reference_nodes:messages.append([0.,dict(type='SetSceneNodeVisibilityMessage',name=name,visible=True)])
    record['messages']=sorted(messages,key=lambda row:(row[0],0 if row[1]['type']=='PointCloudMessage' and row[1].get('name','').endswith('-outline') else 1))
    return record,buffers
