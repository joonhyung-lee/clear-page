"""Give G1 replay annotations a shared, legible visual hierarchy.

Only presentation messages change. Body poses, forecast samples and reference
coordinates are retained. Video overlays project the same native annotations
onto the existing camera frames, without rerunning the physical simulation.
"""
import argparse
import copy
import re
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial.transform import Rotation, Slerp
import imageio_ffmpeg
from recording_io import read_recording, write_recording, compact_buffers
from annotate_g1_reference import geometry

ROOT = Path(__file__).resolve().parents[1]
BLUE = [45, 99, 163]
TEAL = [24, 119, 108]
WHITE = [250, 250, 247]


def selected(name):
    return any(token in name for token in ('reference-overlay/', 'native-overlay/', 'object-motion/',
               'waypoint-anchors', 'reference-path', 'palm-centers', 'palm-history-', 'applied-candidate'))


def style(scene):
    record, buffers = read_recording(ROOT / f'assets/recordings/{scene}.viser')
    messages = [(t,m) for t,m in record['messages'] if '/tracking/object-motion/' not in m.get('name','')]
    body_poses = [(t, m) for t, m in messages if m['type'] in ('SetPositionMessage', 'SetOrientationMessage')
                  and re.fullmatch(r'(?:/tracking)?/body-\d+', m.get('name', ''))]

    def binary(values, dtype='<f4'):
        values = np.asarray(values, dtype=dtype)
        buffers.append(values.tobytes())
        return dict(__binary_index=len(buffers)-1, dtype=values.dtype.str)

    if scene == 'mpc-baseline' and not any('/reference-overlay/object-ghost-' in m.get('name', '') for _, m in messages):
        _, _, prefix, rails, anchors, ghosts = geometry(scene)
        for name, points in [('lane', rails), *[(f'object-ghost-{i}', points) for i, points in enumerate(ghosts)]]:
            messages.append([0., dict(type='LineSegmentsMessage', name=prefix+'/reference-overlay/'+name,
                props=dict(points=binary(points), colors=binary(np.broadcast_to(BLUE, points.shape), '|u1'), line_width=3., scale=1.))])
        messages.append([0., dict(type='PointCloudMessage', name=prefix+'/reference-overlay/anchors',
            props=dict(points=binary(anchors), colors=binary(np.tile(BLUE, (len(anchors), 1)), '|u1'),
                       point_size=.1, point_shape='circle', point_shading='flat', precision='float32', scale=1.))])
    # Measured object travel is separate from its intended corridor.
    if scene != 'mpc-g1-native' and not any('/object-motion/lane' in m.get('name', '') for _, m in messages):
        body = 32 if scene == 'mpc-baseline' else 31
        samples = [(t, m['position']) for t, m in body_poses if m['type']=='SetPositionMessage' and m['name']==f'/tracking/body-{body}']
        path = []
        for index, (t, position) in enumerate(samples):
            point = [*position[:2], .027]; path.append(point)
            values = np.array(list(zip(path[:-1], path[1:])) if index else [[point, point]], dtype=float)
            props = dict(points=binary(values), colors=binary(np.broadcast_to(TEAL, values.shape), '|u1'))
            name = '/tracking/object-motion/lane'
            messages.append([t, dict(type='SceneNodeUpdateMessage', name=name, updates=props) if index else
                             dict(type='LineSegmentsMessage', name=name, props=dict(**props, line_width=6.5, scale=1.))])
            if index == 0:
                messages.append([0., dict(type='PointCloudMessage', name='/tracking/object-motion/current',
                    props=dict(points=binary([[0,0,0]]), colors=binary([TEAL], '|u1'), point_size=.17,
                               point_shape='circle', point_shading='flat', precision='float32', scale=1.))])
            messages.append([t, dict(type='SetPositionMessage', name='/tracking/object-motion/current', position=point)])
    points = {}
    for _, m in messages:
        name = m.get('name', '')
        if not selected(name):
            continue
        props = m.get('props', m.get('updates', {}))
        if m['type'] == 'LineSegmentsMessage':
            props['line_width'] = (5. if 'object-ghost-' in name else 4.5 if '/reference-overlay/' in name else
                                  6.5 if 'object-motion' in name else 5. if 'applied-candidate' in name else
                                  3.5 if 'palm-history-' in name else 5.5)
        if m['type'] == 'PointCloudMessage' and not name.endswith('-outline'):
            props['point_size'] = (.17 if 'object-current' in name or '/object-motion/current' in name else
                                  .14 if '/reference-overlay/anchors' in name or 'object-anchors' in name else
                                  .105 if 'anchors' in name else .10)
            points[name] = props['point_size']
        if '/reference-overlay/' in name and 'colors' in props:
            ref = props['colors']; count = len(buffers[ref['__binary_index']])//3
            color = [94, 128, 171] if 'object-ghost-0' in name else BLUE
            props['colors'] = binary(np.tile(color, (count, 1)), '|u1')
    # White billboard rims separate anchors from meshes. Recreate from the base
    # nodes so both initial states and all dynamic updates stay aligned on seeks.
    messages = [(t, m) for t, m in messages if not (selected(m.get('name', '')) and m.get('name', '').endswith('-outline'))]
    outlines = []
    for t, m in messages:
        if m.get('name') not in points:
            continue
        clone = copy.deepcopy(m); clone['name'] += '-outline'
        props = clone.get('props', clone.get('updates', {}))
        if 'colors' in props:
            count = len(buffers[props['colors']['__binary_index']])//3
            props['colors'] = binary(np.tile(WHITE, (count, 1)), '|u1')
        if 'point_size' in props:
            props['point_size'] = points[m['name']]*1.38
        outlines.append((t, clone))
    messages.extend(outlines)
    # The native baseline already had a second, overlapping object corridor.
    for name in ['/native-overlay/object-target', '/native-overlay/object-anchors', '/native-overlay/object-anchors-outline']:
        if any(m.get('name') == name for _, m in messages):
            messages.append((0., dict(type='SetSceneNodeVisibilityMessage', name=name, visible=False)))
    initialized = {m['name'] for t,m in messages if t==0 and m['type']=='SetSceneNodeVisibilityMessage'}
    for _, m in list(messages):
        if m['type'] in ('LineSegmentsMessage','PointCloudMessage') and selected(m['name']) and m['name'] not in initialized:
            messages.append((0., dict(type='SetSceneNodeVisibilityMessage',name=m['name'],visible=True)))
            initialized.add(m['name'])
    record['messages'] = sorted(messages, key=lambda pair: pair[0])
    assert body_poses == [(t,m) for t,m in record['messages'] if m['type'] in ('SetPositionMessage','SetOrientationMessage')
                          and re.fullmatch(r'(?:/tracking)?/body-\d+',m.get('name',''))]
    record, buffers = compact_buffers(record, buffers)
    write_recording(ROOT / f'assets/recordings/{scene}.viser', record, buffers)
    return record, buffers


def render(scene, cache, output, sample=None):
    record, buffers = read_recording(ROOT / f'assets/recordings/{scene}.viser')
    nodes = {}; cursor = 0; tracks = {}
    def array(ref):
        return np.frombuffer(buffers[ref['__binary_index']], ref['dtype']).reshape(-1, 3)
    def node(name):
        return nodes.setdefault(name, dict(position=np.zeros(3), wxyz=[1,0,0,0], visible=True, props={}))
    # The two Ours videos interpolate archived poses at 30 fps. The native
    # videos use the saved pose at each frame. Match those existing render clocks.
    if scene.startswith('mpc-optimized'):
        values = {}
        for t,m in record['messages']:
            if m['type'] in ('SetPositionMessage','SetOrientationMessage'):
                key = 'position' if m['type']=='SetPositionMessage' else 'wxyz'
                values.setdefault((m['name'],key),{})[t] = m[key]
        for key, data in values.items():
            times=np.array(sorted(data)); values_=np.array([data[t] for t in times])
            if len(times)<2:continue
            if key[1]=='wxyz':
                fn=Slerp(times,Rotation.from_quat(values_,scalar_first=True))
                tracks[key]=lambda t,fn=fn,ts=times:fn(np.clip(t,ts[0],ts[-1])).as_quat(scalar_first=True)
            else:
                tracks[key]=lambda t,v=values_,ts=times:np.array([np.interp(t,ts,v[:,i]) for i in range(3)])
    camera={}
    for _,m in record['messages']:
        if m['type'].startswith('SetCamera'):camera.update(m)
    if scene in ('mpc-optimized','mpc-baseline'):
        camera.update(position=[2.6,-1.8,1.5],look_at=[0,.5,.7])
    eye=np.array(camera['position']);forward=np.array(camera['look_at'])-eye;forward/=np.linalg.norm(forward)
    right=np.cross(forward,[0,0,1.]);right/=np.linalg.norm(right);basis=np.stack([right,np.cross(right,forward),forward],axis=1)
    suffix='' if scene=='mpc-g1-native' else '-contact'
    reader=imageio_ffmpeg.read_frames(str(cache/f'{scene}{suffix}.mp4'));meta=next(reader);w,h=meta['size'];fps=meta['fps']
    focal=h/(2*np.tan(camera['fov']/2));writer=None;output.mkdir(parents=True,exist_ok=True)
    def project(name, positions):
        while name:
            n=node(name);positions=Rotation.from_quat(n['wxyz'],scalar_first=True).apply(positions)+n['position']
            name=name.rsplit('/',1)[0]
        local=(positions-eye)@basis
        xy=np.column_stack([w/2+local[:,0]/np.maximum(local[:,2],.001)*focal,h/2-local[:,1]/np.maximum(local[:,2],.001)*focal])
        return xy,local[:,2]
    def visible(name):
        while name:
            if not node(name)['visible']:return False
            name=name.rsplit('/',1)[0]
        return True
    try:
        for i,raw in enumerate(reader):
            t=i/fps
            while cursor<len(record['messages']) and record['messages'][cursor][0]<=t+1e-7:
                _,m=record['messages'][cursor];cursor+=1
                if 'name' not in m:continue
                n=node(m['name']);kind=m['type']
                if 'props' in m:n.update(kind=kind,props=m['props'].copy())
                elif kind=='SceneNodeUpdateMessage':n['props'].update(m['updates'])
                elif kind=='SetPositionMessage':n['position']=m['position']
                elif kind=='SetOrientationMessage':n['wxyz']=m['wxyz']
                elif kind=='SetSceneNodeVisibilityMessage':n['visible']=m['visible']
            if sample is not None and abs(t-sample)>0.5/fps:continue
            for (name,field),fn in tracks.items():node(name)[field]=fn(t)
            image=Image.frombytes('RGB',(w,h),raw);draw=ImageDraw.Draw(image,'RGBA')
            active=[(name,n) for name,n in list(nodes.items()) if selected(name) and not name.endswith('-outline') and visible(name)]
            for name,n in active:
                if n.get('kind')!='LineSegmentsMessage':continue
                props=n['props'];xy,depth=project(name,array(props['points']));colors=array(props['colors'])
                width=round(props['line_width']);alpha=210 if 'object-ghost-' in name else 235
                for j,pair in enumerate(xy.reshape(-1,2,2)):
                    if min(depth[j*2:j*2+2])<.02:continue
                    pts=[tuple(p) for p in pair]
                    if all(p[0]<-20 for p in pts) or all(p[0]>w+20 for p in pts):continue
                    if all(p[1]<-20 for p in pts) or all(p[1]>h+20 for p in pts):continue
                    color=tuple(int(v) for v in colors[min(j*2,len(colors)-1)])
                    draw.line(pts,fill=(*WHITE,210),width=width+2)
                    draw.line(pts,fill=(*color,alpha),width=width)
            for name,n in active:
                if n.get('kind')!='PointCloudMessage':continue
                props=n['props'];xy,depth=project(name,array(props['points']));colors=array(props['colors'])
                for j,((x,y),z) in enumerate(zip(xy,depth)):
                    if z<.02 or not (-20<x<w+20 and -20<y<h+20):continue
                    radius=max(3.,min(14.,props['point_size']*.5*focal/z));color=tuple(int(v) for v in colors[min(j,len(colors)-1)])
                    draw.ellipse((x-radius-2,y-radius-2,x+radius+2,y+radius+2),fill=(*WHITE,250))
                    draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=(*color,255))
                    if '/reference-overlay/anchors' in name:
                        r=radius*.50;draw.ellipse((x-r,y-r,x+r,y+r),fill=(*WHITE,255))
            if i==0 or sample is not None or i%300==0:image.save(output/f'{scene}{suffix}-{t:g}.png')
            if sample is not None:break
            if writer is None:
                writer=imageio_ffmpeg.write_frames(str(output/f'{scene}{suffix}.mp4'),(w,h),fps=fps,codec='libx264',macro_block_size=1,
                    output_params=['-crf','18','-map_metadata','-1','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart'])
                writer.send(None)
            writer.send(np.array(image))
            if i%300==0:print(scene,'frame',i,flush=True)
    finally:
        reader.close()
        if writer:writer.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scene',required=True)
    p.add_argument('--cache',type=Path);p.add_argument('--output',type=Path);p.add_argument('--sample',type=float)
    p.add_argument('--render-only',action='store_true');a=p.parse_args()
    if not a.render_only:style(a.scene)
    if a.cache:
        assert a.output is not None
        render(a.scene,a.cache,a.output,a.sample)
