"""Add mesh-conforming locomotion/interaction regions and circular ground regions.

Body IDs follow the archived G1, Spot, Spot-arm and Husky XML body order.
The base geometry and all recorded robot transforms are preserved.
"""
import copy
import re
import shutil
from pathlib import Path
import numpy as np
from recording_io import read_recording,write_recording,compact_buffers

ROOT=Path(__file__).resolve().parents[1]
BODIES=['g1','spot','spot_arm','husky']
LOCOMOTION={'g1':set(range(2,14)),'spot':set(range(2,14)),'spot_arm':set(range(2,14)),'husky':set(range(2,6))}
INTERACTION={'g1':set(range(17,31)),'spot':{1},'spot_arm':set(range(14,21)),'husky':set()}
GREEN=[29,173,95]

def build(body):
    target=ROOT/f'assets/recordings/structure-{body}.viser'
    source=ROOT/f'.git/embodiment-regions-original/structure-{body}.viser'
    source.parent.mkdir(parents=True,exist_ok=True)
    if not source.exists():shutil.copyfile(target,source)
    record,buffers=read_recording(source)
    def array(ref):return np.frombuffer(buffers[ref['__binary_index']],ref['dtype']).reshape(-1,3)
    def pack(values,dtype='<f4'):
        a=np.asarray(values,dtype=dtype);buffers.append(a.tobytes());return dict(__binary_index=len(buffers)-1,dtype=a.dtype.str)
    messages=[[t,copy.deepcopy(m)] for t,m in record['messages'] if not m.get('name','').endswith('/contact-field')]
    before=[(t,m) for t,m in messages if m['type'] in ['SetPositionMessage','SetOrientationMessage'] and re.fullmatch(r'/'+body+r'/body-\d+',m.get('name',''))]
    mapping={}
    for t,m in list(messages):
        match=re.fullmatch(r'/'+body+r'/body-(\d+)/mesh-(\d+)',m.get('name',''))
        if not match or m['type']!='MeshMessage':continue
        bid=int(match[1])
        for label,ids in [('locomotion',LOCOMOTION[body]),('interaction',INTERACTION[body])]:
            if bid not in ids:continue
            clone=copy.deepcopy(m);name=m['name'].replace('/mesh-',f'/{label}-shell-');clone['name']=name
            props=clone['props'];vertices=array(props['vertices']);center=(vertices.min(axis=0)+vertices.max(axis=0))/2
            props.update(vertices=pack(center+(vertices-center)*1.018),color=GREEN,opacity=.72,side='front',cast_shadow=False,receive_shadow=False)
            messages.extend([[t,clone],[t,dict(type='SetSceneNodeVisibilityMessage',name=name,visible=False)]])
            mapping.setdefault(m['name'],[]).append(name)
    for t,m in list(messages):
        if m['type'] not in ['SetPositionMessage','SetOrientationMessage']:continue
        for name in mapping.get(m.get('name'),[]):
            clone=copy.deepcopy(m);clone['name']=name;messages.append([t,clone])
    record['messages']=sorted(messages,key=lambda row:row[0])
    after=[(t,m) for t,m in record['messages'] if m['type'] in ['SetPositionMessage','SetOrientationMessage'] and re.fullmatch(r'/'+body+r'/body-\d+',m.get('name',''))]
    assert before==after
    record,buffers=compact_buffers(record,buffers);write_recording(target,record,buffers)
    print(body, 'locomotion bodies',sorted(LOCOMOTION[body]),'interaction bodies',sorted(INTERACTION[body]),flush=True)

if __name__=='__main__':
    for body in BODIES:build(body)
