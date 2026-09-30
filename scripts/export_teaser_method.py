"""Build native explanatory replays offline from the teaser's baked geometry.

The observed robot is its recorded initial state. Flow ghosts are checkpoint
predictions, never a synthetic execution. All three lanes use source geometry.
"""
import argparse
import copy
import json
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial.transform import Rotation

from recording_io import read_recording, write_recording, compact_buffers
from style_learning_checkpoints import learning_lighting
from maze_geometry_refinement import Clearance

ROOT = Path(__file__).resolve().parents[1]
COLORS = [[128, 163, 175], [201, 158, 124], [145, 174, 128],
          [173, 157, 192], [190, 169, 115]]


class Recording:
    """A small offline writer for the native messages used by these figures."""
    def __init__(self):
        self.record = dict(durationSeconds=8., messages=[], viserVersion='1.0.24')
        self.buffers = []; self.frames = {''}
        # Viser records Z-up scene coordinates in a Y-up Three.js root.
        # The camera messages use this same root transform in the native player.
        self.emit('SetOrientationMessage', name='', wxyz=[.5,-.5,.5,.5])
        self.emit('ThemeConfigurationMessage',titlebar_content=None,control_layout='floating',
                  control_width='medium',show_logo=False,show_share_button=False,dark_mode=False,colors=None)

    def emit(self, type, time=0., **values):
        self.record['messages'].append([float(time), dict(type=type, **values)])

    def pack(self, value, dtype):
        a = np.asarray(value, dtype=dtype)
        index = len(self.buffers); self.buffers.append(a.tobytes())
        return dict(__binary_index=index, dtype=a.dtype.str)

    def frame(self, name, visible=True):
        if name in self.frames: return
        self.frame(name.rpartition('/')[0])
        self.emit('FrameMessage', name=name, props=dict(show_axes=False,
            axes_length=.5, axes_radius=.025, origin_radius=.05,
            origin_color=[236,236,0], scale=1.))
        self.emit('SetSceneNodeVisibilityMessage', name=name, visible=visible)
        self.frames.add(name)

    def node(self, type, name, props, position=None, wxyz=None):
        self.frame(name.rpartition('/')[0])
        self.emit(type, name=name, props=props)
        self.emit('SetSceneNodeVisibilityMessage', name=name, visible=True)
        if position is not None: self.position(name, position)
        if wxyz is not None: self.emit('SetOrientationMessage', name=name, wxyz=list(wxyz))

    def position(self, name, position, time=0.):
        self.emit('SetPositionMessage', time, name=name, position=list(map(float,position)))

    def mesh(self, name, vertices, faces, color, position, wxyz=(1.,0.,0.,0.), opacity=1.):
        self.node('MeshMessage', name, dict(vertices=self.pack(vertices,'<f4'),
            faces=self.pack(faces,'<u4'), color=list(map(int,color)), wireframe=False,
            opacity=opacity, flat_shading=True, side='front', material='standard',
            scale=1., cast_shadow=False, receive_shadow=False), position, wxyz)

    def lines(self, name, points, color, width=3.):
        points = np.asarray(points,dtype='<f4').reshape(-1,2,3)
        colors = np.broadcast_to(np.asarray(color,dtype='u1'), points.shape)
        self.node('LineSegmentsMessage', name, dict(points=self.pack(points,'<f4'),
            colors=self.pack(colors,'u1'), line_width=width, scale=1.))

    def line_update(self, name, points, color, time):
        points = np.asarray(points,dtype='<f4').reshape(-1,2,3)
        self.emit('SceneNodeUpdateMessage',time,name=name,updates=dict(
            points=self.pack(points,'<f4'),
            colors=self.pack(np.broadcast_to(np.asarray(color,dtype='u1'),points.shape),'u1')))

    def label(self,name,text,position):
        self.node('LabelMessage', name, dict(text=text,font_size_mode='screen',
            font_screen_scale=.8,font_scene_height=.075,depth_test=False,anchor='bottom-center'),position)

    def save(self,path):
        self.record['messages'].sort(key=lambda entry:entry[0])
        self.record=learning_lighting(self.record)
        r,b=compact_buffers(self.record,self.buffers)
        write_recording(path,r,b)


def box_edges(size):
    half=np.asarray(size)/2
    vertices=np.array(np.meshgrid(*[[-v,v] for v in half])).T.reshape(-1,3)
    # Only corner segments: both box shape and waypoint remain legible.
    segments=[]
    for i,x in enumerate(vertices):
        for y in vertices[i+1:]:
            if np.count_nonzero(x!=y)!=1:continue
            segments.extend([[x,x+.28*(y-x)],[y-.28*(y-x),y]])
    return np.asarray(segments)


def elevation(scene, xy):
    x,y=xy; z=0.
    for t in scene['terrain']:
        x0,y0,x1,y1=t['bounds']
        if x0<=x<=x1 and y0<=y<=y1:
            h=t.get('height_m')
            if h is None:
                axis=t['axis'];u=(xy[axis]-t['bounds'][axis])/(t['bounds'][axis+2]-t['bounds'][axis])
                h=t['start_height_m']+u*(t['end_height_m']-t['start_height_m'])
            z=max(z,h)
    return z


def setup(source, scene):
    r=Recording();g=np.load(source/'g1__geometry.npz');s=np.load(source/'g1__states.npz')
    r.record['viserVersion']=read_recording(ROOT/'assets/recordings/scene-maze.viser')[0]['viserVersion']
    r.emit('SetCameraPositionMessage',position=[14.,-5.,20.],initial=True)
    r.emit('SetCameraLookAtMessage',look_at=[5.,8.,.35],initial=True)
    r.emit('SetCameraFovMessage',fov=.78,initial=True)
    r.emit('SetSceneNodeVisibilityMessage',name='/WorldAxes',visible=False)
    floor=trimesh.creation.box(extents=[10.,17.,.04])
    r.mesh('/floor',floor.vertices,floor.faces,[240,244,241],[5.,8.5,-.03])
    for i,kind in enumerate(g['geom_type']):
        if kind==0:continue
        body=int(g['geom_body'][i]);name=str(g['geom_name'][i])
        if kind==6:
            mesh=trimesh.creation.box(extents=2*g['geom_size'][i]);vertices,faces=mesh.vertices,mesh.faces
        elif kind==7:
            va,vn=g['mesh_vert_range'][i];fa,fn=g['mesh_face_range'][i]
            vertices=g['mesh_vert'][va:va+vn];faces=g['mesh_face'][fa:fa+fn]
            # Baked ranges contain independent local face indices.
            assert faces.min()>=0 and faces.max()<len(vertices),(name,va,vn,faces.min(),faces.max())
        else:raise ValueError(f'Unexpected source geometry type {kind}')
        rot=Rotation.from_quat(s['xquat'][0,body],scalar_first=True)
        pos=rot.apply(g['geom_local_pos'][i])+s['xpos'][0,body]
        quat=(rot*Rotation.from_quat(g['geom_local_quat'][i],scalar_first=True)).as_quat(scalar_first=True)
        color=np.clip(g['geom_rgba'][i,:3]*255,0,255).astype(int).tolist()
        opacity=1.
        if body==0:
            if 'stair_' in name:color=[250,220,202] if '_2_' in name else [222,219,247]
            elif 'ramp_' in name:color=[212,238,222]
            elif 'border' in name:color=[214,222,218];opacity=.22
            elif g['geom_size'][i,2]>.7:color=[209,219,214];opacity=.65
            else:color=[227,235,230]
        body_name=str(s['body_names'][body])
        if body_name.startswith('object'):
            idx=0 if body_name.startswith('object/') else int(body_name.split('/')[0].split('_')[1])
            color=COLORS[idx]
        r.mesh('/observed/part-'+str(i),vertices,faces,color,pos,quat,opacity)
    for i,o in enumerate(scene['objects']):
        z=elevation(scene,o['pose'][:2])
        r.label('/label-'+str(i),'Object '+str(i),[*o['pose'][:2],z+o['size'][2]+.25])
    for name,p,color in [('start',scene['start'],[101,148,177]),('goal',scene['goal'],[115,161,127])]:
        disc=trimesh.creation.cylinder(radius=.22,height=.02,sections=32)
        z=elevation(scene,p[:2]);r.mesh('/'+name,disc.vertices,disc.faces,color,[*p[:2],z+.02])
        r.label('/'+name+'-label',name.title(),[*p[:2],z+.2])
    for label,x in [('Stairs 1',2.5),('Stairs 2',5.5),('Slope',8.5)]:
        r.label('/terrain-label-'+str(x),label,[x,8.7,1.15])
    return r


def ghost(r,name,scene,i,pose,time=None):
    o=scene['objects'][i];xyz=[*pose[:2],elevation(scene,pose[:2])+o['size'][2]/2]
    if time is None:r.lines(name,box_edges(o['size']),COLORS[i],2.5)
    r.position(name,xyz,0. if time is None else time)
    r.emit('SetOrientationMessage',0. if time is None else time,name=name,
           wxyz=Rotation.from_euler('z',pose[2]).as_quat(scalar_first=True).tolist())


def build_order(base,d,out):
    r=copy.deepcopy(base);scene=d['scene']
    for stage in ['context','supervision','prediction']+[f'sample-{i}' for i in range(4)]:
        r.frame('/order/'+stage,stage=='context')
    for path in d['supervision']['paths']:
        i=path['object'];poses=path['poses'];xyz=np.array([[*p[:2],elevation(scene,p[:2])+.07] for p in poses])
        r.lines(f'/order/supervision/reference-{i}',np.stack([xyz[:-1],xyz[1:]],1),COLORS[i],4.)
        ghost(r,f'/order/supervision/ghost-{i}',scene,i,poses[-1])
    for sample,trace in enumerate(d['traces']):
        ids=sorted([i for i,rank in enumerate(trace['rank']) if rank>=0],key=lambda i:trace['rank'][i])
        for i in ids:
            o=scene['objects'][i];ring=trimesh.creation.annulus(r_min=.60,r_max=.68,height=.025,sections=32)
            r.mesh(f'/order/sample-{sample}/ring-{i}',ring.vertices,ring.faces,COLORS[i],
                   [*o['pose'][:2],elevation(scene,o['pose'][:2])+.03])
        if len(ids)>1:
            xyz=np.array([[*scene['objects'][i]['pose'][:2],elevation(scene,scene['objects'][i]['pose'][:2])+1.4] for i in ids])
            r.lines(f'/order/sample-{sample}/sequence',np.stack([xyz[:-1],xyz[1:]],1),[110,130,119],3.)
    r.save(out/'method-order-maze.viser')


def build_flow(base,d,out):
    scene=d['scene']
    for sample,trace in enumerate(d.get('referenceFlow',d['traces'])):
        r=copy.deepcopy(base);r.record['durationSeconds']=8.
        for path in trace['states'][0]:
            i=path['object'];poses=np.asarray(path['poses'])
            for slot,p in enumerate([poses[len(poses)//2],poses[-1]]):ghost(r,f'/ghost-{i}-{slot}',scene,i,p)
            points=np.array([[*p[:2],elevation(scene,p[:2])+scene['objects'][i]['size'][2]+.10] for p in poses])
            r.lines(f'/path-{i}',np.stack([points[:-1],points[1:]],1),COLORS[i])
            for j,point in enumerate(points):
                ring=trimesh.creation.annulus(r_min=.065,r_max=.105,height=.018,sections=16)
                r.mesh(f'/anchor-{i}-{j}',ring.vertices,ring.faces,COLORS[i],point)
        for frame in range(360):
            f=frame/359*30;lo=int(f);hi=min(lo+1,30);u=f-lo
            paths=[dict(object=p0['object'],poses=(1-u)*np.asarray(p0['poses'])+u*np.asarray(p1['poses']))
                   for p0,p1 in zip(trace['states'][lo],trace['states'][hi])]
            time=frame/60
            for path in paths:
                i=path['object'];poses=np.asarray(path['poses'])
                points=np.array([[*p[:2],elevation(scene,p[:2])+scene['objects'][i]['size'][2]+.10] for p in poses])
                r.line_update(f'/path-{i}',np.stack([points[:-1],points[1:]],1),COLORS[i],time)
                for j,point in enumerate(points):r.position(f'/anchor-{i}-{j}',point,time)
                for slot,p in enumerate([poses[len(poses)//2],poses[-1]]):ghost(r,f'/ghost-{i}-{slot}',scene,i,p,time)
        # Final collision projection is shown only after raw integration.
        # The source gate is narrower than a bounding disc, so a conservative
        # projection can legitimately fail. Never fabricate a refined path.
        outcomes=[];placed={}
        for path in trace['states'][-1]:
            i=path['object'];poses=np.asarray(path['poses'])
            try:xy=Clearance(scene,i,placed).refine(poses)
            except ValueError:
                outcomes.append(dict(object=i,refined=False));continue
            placed[i]=xy[-1];outcomes.append(dict(object=i,refined=True))
            points=np.array([[*p,elevation(scene,p)+scene['objects'][i]['size'][2]+.10] for p in xy])
            r.line_update(f'/path-{i}',np.stack([points[:-1],points[1:]],1),COLORS[i],6.)
            for slot,j in enumerate([len(xy)//2,len(xy)-1]):ghost(r,f'/ghost-{i}-{slot}',scene,i,[*xy[j],poses[-1,2]],6.)
        r.save(out/f'method-flow-{sample}-pipeline.viser')
        (out/f'method-flow-{sample}-status.json').write_text(json.dumps(outcomes))
        print('Saved flow draw',sample,outcomes,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('trace',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();d=json.loads(a.trace.read_text().split(' = ',1)[1].rstrip(';\n'))
    a.output.mkdir(parents=True,exist_ok=True)
    base=setup(a.source,d['scene']);build_order(base,d,a.output);build_flow(base,d,a.output)
