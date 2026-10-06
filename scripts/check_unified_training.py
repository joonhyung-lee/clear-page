"""Verify actual update-zero recordings and the single training presentation."""
import json
import tempfile
from pathlib import Path
import numpy as np
from bs4 import BeautifulSoup
from recording_io import read_recording, validate_binary_arrays

ROOT=Path(__file__).resolve().parents[1]
s=BeautifulSoup((ROOT/'index.html').read_text(),'html.parser')
section=s.select_one('#controller-pretraining')
assert section['data-training-layout']=='unified'
assert not section.select('[data-loco-source], [data-policy-recorded], #policy-evaluation, [data-policy-evaluation]')
assert [b.get_text(strip=True) for b in section.select('.loco-metrics button')]==['PPO losses','Training progress']
assert section.select_one('[data-curriculum-reset]')
assert section.select_one('[data-curriculum-explanations]')
signatures=[]
for body in ['g1','spot','spot_arm']:
    text=(ROOT/f'assets/{body}-curriculum-data.js').read_text()
    data=json.loads(text.split(' = ',2)[2].rstrip(';\n'))
    assert data['body']==body and data['curves'][0]['update']==1
    initial=next(st for st in data['stages'] if st['id']=='initialization')['replay']
    assert initial['body']==body and initial['startsBeforeAction']
    assert initial['cumulativeUpdates']==0 and initial['completedUpdates']==0
    scene=initial['scene']
    script=(ROOT/f'assets/recordings/{scene}.hex.js').read_text()
    binary=bytes.fromhex(json.loads(script.rsplit(' = ',1)[1].rstrip(';\n')))
    with tempfile.NamedTemporaryFile() as f:
        f.write(binary);f.flush();record,buffers=read_recording(f.name)
    validate_binary_arrays(record,buffers)
    mesh=next(m for _,m in record['messages'] if m['type']=='BatchedMeshesMessage')
    def array(ref):return np.frombuffer(buffers[ref['__binary_index']],dtype=ref['dtype']).reshape(-1,3)
    start=array(mesh['props']['batched_positions']);lowest=start[:,2].copy();frames=0
    for t,m in record['messages']:
        if m.get('name')==mesh['name'] and 'batched_positions' in m.get('updates',{}):
            lowest=np.minimum(lowest,array(m['updates']['batched_positions'])[:,2]);frames+=1
    assert len(start)==32 and frames>=190 and record['durationSeconds']>=8
    # Inspect measured collapse without synthesizing falls or treating this as a success metric.
    drops=int(np.count_nonzero(start[:,2]-lowest>.2));assert drops>0
    assert (ROOT/f'assets/media/{scene}.png').is_file()
    for stage in data['stages']:
        if stage['replay']:
            assert (ROOT/f"assets/recordings/{stage['replay']['scene']}.hex.js").is_file()
        if stage['state']=='pending':
            assert not any(row['stage']==stage['id'] for row in data['curves'])
    signatures.append((scene,[(row['update'],row['value']) for row in data['curves']]))
    print(f'PASS {body}: independent update 0, {frames} pose updates, {drops}/32 bodies drop >20 cm, unaltered logged losses')
assert len({scene for scene,_ in signatures})==3
assert signatures[1][1]!=signatures[2][1]
print('PASS one training view, two metric tabs, original initialization recordings and honest pending phases')
