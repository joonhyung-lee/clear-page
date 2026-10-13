"""Restore the published execution presentation with a soft pastel palette.

Uses the pre-styling archive (identical to the published recordings), retaining
camera, robot meshes, clocks, line geometry, and visibility intervals. Flat
anchor markers remain flat; their density is ten markers per path.
"""
import copy
import colorsys
from pathlib import Path
import numpy as np
from recording_io import read_recording, write_recording, compact_buffers

ROOT=Path(__file__).resolve().parents[1]
SCENES=['mpc-optimized-full','mpc-baseline','mpc-spot-optimized','mpc-spot-native']
COLORS=dict(blue=[145,178,211],red=[210,153,157],green=[113,174,144],mint=[155,201,187],purple=[184,171,207],gray=[209,214,216])

def restore(scene):
    source=ROOT/f'.git/visual-refresh/original-recordings/{scene}.viser'
    record,buffers=read_recording(source)
    original=copy.deepcopy(record)
    def array(ref):return np.frombuffer(buffers[ref['__binary_index']],ref['dtype']).reshape(-1,3)
    def pack(values,dtype='<f4'):
        values=np.asarray(values,dtype=dtype);buffers.append(values.tobytes());return dict(__binary_index=len(buffers)-1,dtype=values.dtype.str)
    def sample(points):
        distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
        keep=np.r_[True,np.diff(distance)>1e-8]
        return np.column_stack([np.interp(np.linspace(0,distance[-1],10),distance[keep],points[keep,i]) for i in range(3)])
    def color(values,name):
        old=np.asarray(values,dtype=float);h,s,v=colorsys.rgb_to_hsv(*(old/255))
        if name.endswith('-outline'):return [35,42,47]
        if 'ghost' in name:return [40,60,74]
        if 'eef' in name or 'palm' in name or 'contacts' in name:return COLORS['red']
        if any(x in name for x in ['object-motion','object-current','observed','goal','highlight']):return COLORS['green']
        if any(x in name for x in ['reference','waypoint','target','object-overlay/lane','object-anchors']):return COLORS['blue']
        if s<.12:return old.astype(int).tolist()
        family='red' if h<.14 or h>.93 else 'green' if h<.43 else 'mint' if h<.55 else 'blue' if h<.75 else 'purple'
        return COLORS[family]
    remove={'/eef-overlay/lane-left','/eef-overlay/lane-right','/eef-overlay/time-dots'}
    msgs=[]
    for time,m in record['messages']:
        name=m.get('name','')
        if name in remove:continue
        props=m.get('props',m.get('updates',{}))
        if m['type']=='MeshMessage':
            object_ids=[21] if 'spot' in scene else [32,33] if scene=='mpc-baseline' else [31,32]
            if any(f'/body-{i}/' in name for i in object_ids):props['color']=COLORS['purple']
            elif '/body-0/' in name:
                old=props.get('color',[220,220,220]);h,s,v=colorsys.rgb_to_hsv(*(np.asarray(old)/255))
                props['color']=COLORS['green'] if s>.15 and .2<h<.5 else [235,237,235] if max(old)>225 else COLORS['gray']
        elif '/body-' not in name or any(s in name for s in ['palm','contact']):
            for key in ['color','colors']:
                value=props.get(key)
                if isinstance(value,(tuple,list)):props[key]=color(value,name)
                elif isinstance(value,dict) and '__binary_index' in value:
                    old=array(value);unique,inverse=np.unique(old,axis=0,return_inverse=True)
                    props[key]=pack(np.array([color(row,name) for row in unique])[inverse],'|u1')
        if 'anchor' in name and 'points' in props:
            props['points']=pack(sample(array(props['points'])))
            if 'colors' in props:props['colors']=pack(np.tile(array(props['colors'])[0],(10,1)),'|u1')
        if m['type']=='PointCloudMessage':
            # Native Viser sizes billboards relative to the viewport. Match the
            # compact markers in the published video rather than enlarging them.
            size=.04 if 'current' in name or 'palm' in name else .03
            props['point_size']=size*(1.2 if name.endswith('-outline') else 1.)
        msgs.append([time,m])
    if scene=='mpc-spot-native':
        # The archived baseline omitted visibility defaults. Make its original
        # overlays visible in both the embedded and standalone native players.
        for _,m in list(msgs):
            if m['type'] in ['PointCloudMessage','LineSegmentsMessage'] and m.get('name','').startswith('/native-overlay/'):
                msgs.append([0.,dict(type='SetSceneNodeVisibilityMessage',name=m['name'],visible=True)])
    # Draw coplanar colored centers after their flat rims.
    msgs.sort(key=lambda pair:(pair[0],0 if pair[1]['type']=='PointCloudMessage' and pair[1].get('name','').endswith('-outline') else 1))
    record['messages']=msgs
    # Display geometry and the recorded cameras stay byte-for-byte unchanged,
    # apart from the explicitly requested anchor count / duplicate EEF lanes.
    stable=lambda r:[(t,m) for t,m in r['messages'] if 'Camera' in m['type'] or (m['type'] in ['SetPositionMessage','SetOrientationMessage'] and '/body-' in m.get('name',''))]
    assert stable(original)==stable(record)
    if scene.startswith('mpc-spot-'):
        from style_eef_annotations import style
        record,buffers=style(record,buffers)
    record,buffers=compact_buffers(record,buffers)
    write_recording(ROOT/f'assets/recordings/{scene}.viser',record,buffers)
    print(scene,'published presentation restored; pastel colors; flat anchors',flush=True)

if __name__=='__main__':
    for scene in SCENES:restore(scene)
