"""Check teaser geometry, reference conditioning, and native replay consistency."""
import json
from pathlib import Path
import numpy as np
from bs4 import BeautifulSoup
from recording_io import read_recording, validate_binary_arrays

root=Path(__file__).resolve().parents[1]
d=json.loads((root/'assets/maze-method-trace.js').read_text().split(' = ',1)[1].rstrip(';\n'))
scene=d['scene']
assert scene['world_size']==[10,17]
assert len(scene['objects'])==5
assert scene['start'][:2]==[2.5,.5] and scene['goal']==[2.5,16.5]
stairs=[t for t in scene['terrain'] if t['kind']=='stair_tread']
ramps=[t for t in scene['terrain'] if t['kind']=='ramp']
assert len(stairs)==12 and len(ramps)==3
assert {t['bounds'][0] for t in stairs}=={2,5}
assert {t['bounds'][0] for t in ramps}=={8}
assert all(t['axis']==1 for t in ramps)
assert scene['objects'][0]['pose'][:2]==[2.5,2.5]
assert scene['objects'][4]['pose'][:2]==[9.5,12.5]
assert d['supervision']['rank']==[0,-1,-1,-1,-1]
assert 'not produced by the learned planner' in d['supervision']['scope']
assert 'not predicted by OrderNet' in d['flowScope']
for trace,conditional in zip(d['traces'],d['referenceFlow']):
    assert len(trace['rank'])==len(trace['selected'])==5
    assert all(not paths for paths in trace['states']), 'Do not present conditional flow as end-to-end sampling'
    assert conditional['rank']==d['supervision']['rank']
    assert len(conditional['states'])==31
    assert all([p['object'] for p in paths]==[0] for paths in conditional['states'])
    assert not np.allclose(conditional['states'][0][0]['poses'],conditional['states'][-1][0]['poses'])

names=['method-order-maze']+[f'method-flow-{i}-pipeline' for i in range(4)]
for name in names:
    record,buffers=read_recording(root/f'assets/recordings/{name}.viser')
    validate_binary_arrays(record,buffers)
    messages=record['messages'];assert all(a[0]<=b[0] for a,b in zip(messages,messages[1:]))
    root_orientation=next(m['wxyz'] for t,m in messages if m['type']=='SetOrientationMessage' and m['name']=='')
    np.testing.assert_allclose(root_orientation,[.5,-.5,.5,.5])
    frames={''};initial={}
    for time,m in messages:
        if m['type'] in ['FrameMessage','MeshMessage','LabelMessage','LineSegmentsMessage']:
            assert m['name'].rpartition('/')[0] in frames,m['name']
            if m['type']=='FrameMessage':frames.add(m['name'])
        if time==0 and m['type']=='MeshMessage':initial[m['name']]=m['props']
    colors={tuple(p['color']) for name,p in initial.items() if name.startswith('/observed/')}
    assert {(250,220,202),(222,219,247),(212,238,222)}<=colors
    assert len([m for t,m in messages if m['type']=='LabelMessage' and m['name'].startswith('/label-')])==5
    assert len([name for name in initial if name.startswith('/observed/')])==148
    if 'pipeline' in name:
        index=int(name.split('-')[2]);trace=d['referenceFlow'][index]
        ghosts={m['name'] for t,m in messages if m['type']=='LineSegmentsMessage' and m['name'].startswith('/ghost-')}
        assert ghosts=={'/ghost-0-0','/ghost-0-1'}
        updates=[(t,m) for t,m in messages if m['type']=='SceneNodeUpdateMessage' and m['name']=='/path-0' and t<6]
        assert len(updates)==360
        points=np.frombuffer(buffers[updates[-1][1]['updates']['points']['__binary_index']],dtype='<f4').reshape(-1,2,3)
        target=np.array(trace['states'][-1][0]['poses'])
        np.testing.assert_allclose(points[:,0,:2],target[:-1,:2],atol=1e-5)
        np.testing.assert_allclose(points[:,1,:2],target[1:,:2],atol=1e-5)
    print('PASS',name,'source geometry and typed replay arrays')
s=BeautifulSoup((root/'index.html').read_text(),'html.parser')
assert 'teaser' in s.select_one('#ordering-context .preview-image')['alt'].lower()
assert 'select no interaction' in s.select_one('#teaser-query-scope').get_text()
assert s.select_one('#failure-cases #flow-learning .flow-pair canvas') is not None
assert 'supplied example order' in s.select_one('#flow-learning').get_text()
assert 'does not produce a feasible plan' in s.select_one('#flow-learning').get_text()
print('PASS two stair lanes, one slope, five objects, designated reference and actual checkpoint traces')

flow=json.loads((root/'assets/teaser-flow-data.js').read_text().split(' = ',1)[1].rstrip(';\n'))
assert flow['scene']==scene
assert flow['conditionedOrder']==[0,1,2]
assert 'not an OrderNet prediction' in flow['flowScope']
for index,trace in enumerate(flow['referenceFlow']):
    assert trace['rank']==[0,1,2,-1,-1]
    assert all([p['object'] for p in state]==[0,1,2] for state in trace['states'])
    record,buffers=read_recording(root/f'assets/recordings/teaser-flow-{index}.viser')
    validate_binary_arrays(record,buffers)
    poses={m['name']:m['position'] for t,m in record['messages'] if t==0 and m['type']=='SetPositionMessage'}
    for i in range(3):
        np.testing.assert_allclose(poses[f'/anchor-{i}-0'],poses[f'/observed/part-{144+i}'],atol=1e-6)
    assert record['durationSeconds']==16
print('PASS actual three-object flow inference, common scene and box-center anchor alignment')
