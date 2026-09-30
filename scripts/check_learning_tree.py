"""Reject orphan native replay nodes that can never mount in Viser's scene tree."""
import argparse,json,tempfile
from pathlib import Path
from bs4 import BeautifulSoup
from recording_io import read_recording
from style_learning_checkpoints import TERRAIN_COLORS
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--recording',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parents[1]
files=[a.recording] if a.recording else [root/f'assets/recordings/learning-{body}.hex.js' for body in ['g1','spot','spot_arm']]
for file in files:
    with tempfile.NamedTemporaryFile() as temporary:
        if file.suffix=='.js':
            temporary.write(bytes.fromhex(json.loads(file.read_text().rsplit(' = ',1)[1].rstrip(';\n'))));temporary.flush();path=temporary.name
        else:path=file
        record,buffers=read_recording(path)
    mounted={''};orphans=[];terrain=0
    def check_arrays(value, path='record'):
        if isinstance(value,dict):
            if '__binary_index' in value:
                assert 'dtype' in value, f'{file.name}: missing native array dtype at {path}'
            else:
                for key,child in value.items():check_arrays(child,path+'.'+key)
        elif isinstance(value,(list,tuple)):
            for index,child in enumerate(value):check_arrays(child,path+f'[{index}]')
    check_arrays(record)
    if not a.recording:
        lighting={m['type']:m for _,m in record['messages'] if m['type'] in ['EnableLightsMessage','EnvironmentMapMessage']}
        assert lighting['EnableLightsMessage']['enabled'] is False
        assert lighting['EnvironmentMapMessage']['hdri'] is None
        assert any(m['type']=='AmbientLightMessage' for _,m in record['messages'])
        assert any(m['type']=='DirectionalLightMessage' for _,m in record['messages'])
    for _,m in record['messages']:
        if m['type'] not in ['FrameMessage','MeshMessage','BatchedMeshesMessage','LabelMessage']:continue
        name=m['name'];parent=name.rpartition('/')[0]
        if parent not in mounted:orphans.append((name,parent))
        else:mounted.add(name)
        if m['type']=='MeshMessage' and name.startswith('/terrain/'):
            terrain+=1
            if not a.recording:assert tuple(m['props']['color'])==TERRAIN_COLORS[name.split('/')[-1]]
    assert not orphans, f'{file.name}: unreachable scene nodes {orphans}'
    assert terrain>0
    # Native rewind hides existing meshes before replaying time-zero messages.
    terrain_meshes={m['name'] for _,m in record['messages'] if m['type']=='MeshMessage' and m['name'].startswith('/terrain/')}
    restored={m['name'] for _,m in record['messages'] if m['type']=='SetSceneNodeVisibilityMessage' and m['visible']}
    assert terrain_meshes<=restored, f'{file.name}: terrain remains hidden after rewind: {sorted(terrain_meshes-restored)}'
    print('PASS',file.name,terrain,'terrain meshes attached to the native scene tree')
if not a.recording:
    soup=BeautifulSoup((root/'index.html').read_text(),'html.parser')
    for span in soup.select('[data-terrain]'):
        expected='rgb('+','.join(map(str,TERRAIN_COLORS[span['data-terrain']]))+')'
        assert expected in span['style']
    print('PASS legend and mesh palettes match')
