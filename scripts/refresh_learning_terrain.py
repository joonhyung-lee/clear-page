"""Repair mesh array metadata and terrain parents, and apply the shared palette."""
import json
import re
import tempfile
from pathlib import Path
from recording_io import read_recording, write_recording
from style_learning_checkpoints import TERRAIN_COLORS, terrain_hierarchy, learning_lighting

root=Path(__file__).resolve().parents[1]
for body in ['g1','spot','spot_arm']:
    asset=root/f'assets/recordings/learning-{body}.hex.js'
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/f'learning-{body}.viser'
        path.write_bytes(bytes.fromhex(json.loads(asset.read_text().rsplit(' = ',1)[1].rstrip(';\n'))))
        record,buffers=read_recording(path)
        for _,message in record['messages']:
            if message['type'] in ['MeshMessage','BatchedMeshesMessage']:
                # Viser resolves a binary reference only when dtype is present.
                # The styling exporter writes float32 vertices and uint32 faces.
                for field,dtype in [('vertices','<f4'),('faces','<u4')]:
                    reference=message['props'][field]
                    assert len(buffers[reference['__binary_index']]) % 12 == 0
                    if 'dtype' in reference:assert reference['dtype']==dtype
                    reference['dtype']=dtype
            if message['type']=='MeshMessage' and message['name'].startswith('/terrain/'):
                message['props']['color']=TERRAIN_COLORS[message['name'].split('/')[-1]]
                message['props']['receive_shadow']=False
        write_recording(path,learning_lighting(terrain_hierarchy(record)),buffers)
        asset.write_bytes(path.with_suffix('.hex.js').read_bytes())
    print(body,'mesh array types and terrain parents restored; pastel palette applied')
for file in [root/'index.html',root/'scripts/build_controller_pretraining.py']:
    text=file.read_text()
    for family,color in TERRAIN_COLORS.items():
        text=re.sub(r'(data-terrain="'+family+r'" style="--terrain:)rgb\([^)]*\)',
                    lambda m:m[1]+'rgb('+','.join(map(str,color))+')',text)
    file.write_text(text)
