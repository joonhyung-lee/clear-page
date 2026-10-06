"""Verify restored metrics and the four real segments of the archived replay."""
import json
import tempfile
from pathlib import Path
import numpy as np
from recording_io import read_recording, validate_binary_arrays

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / 'assets/spot_arm-restored-data.js').read_text()
data = json.loads(text.split(' = ', 2)[2].rstrip(';\n'))
source = (ROOT / 'assets/locomotion-training-spot_arm.js').read_text()
original = json.loads(source.split('["spot_arm"]=', 1)[1].rstrip(';\n'))
assert data['source'] == 'archived-controller'
assert data['defaultCheckpoint'] == 'checkpoint-28000'
for row, sample in zip(data['curves'], original['samples'], strict=True):
    expected = dict(zip(original['columns'], sample))
    for key in ['value', 'policy', 'entropy', 'terrain', 'tracking', 'arm']:
        assert row[key] == expected[key]
    assert row['return'] == expected['reward'] and row['update'] == expected['step']
assert [s['label'] for s in data['stages']] == [s['label'] for s in original['phases']]
assert sum(s['targetUpdates'] for s in data['stages']) == 28000
print('PASS all archived metric samples and original phase boundaries')

text = (ROOT / 'assets/recordings/learning-spot_arm.hex.js').read_text()
with tempfile.NamedTemporaryFile() as file:
    file.write(bytes.fromhex(json.loads(text.rsplit(' = ', 1)[1].rstrip(';\n'))))
    file.flush()
    record, buffers = read_recording(file.name)
validate_binary_arrays(record, buffers)
assert sum(m['type'] == 'BatchedMeshesMessage' for _, m in record['messages']) == 30
poses = []
for time, message in record['messages']:
    if message.get('name') != '/agents/2':
        continue
    value = message.get('props', message.get('updates', {})).get('batched_positions')
    if value:
        poses.append((time, np.frombuffer(buffers[value['__binary_index']], dtype='<f4').reshape(-1, 3)))
for checkpoint in data['checkpoints']:
    replay = checkpoint['replay']
    start = replay['startTime']
    # Floating-point timestamps can land a fraction below an eight-second boundary.
    frames = [p for t, p in poses if start-1e-6 <= t < start+8-1e-6]
    assert len(frames) == 200 and len(frames[0]) == 32
    displacement = np.median(np.linalg.norm(frames[-1][:, :2]-frames[0][:, :2], axis=1))
    assert displacement > 1, 'Restored checkpoint must contain actual locomotion'
    print(f'PASS {replay["cumulativeUpdates"]}: 200 frames, 32 bodies, median horizontal displacement {displacement:.2f} m')
