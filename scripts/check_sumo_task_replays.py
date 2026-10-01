"""Compare published task geometry and every body pose against native records."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.spatial.transform import Rotation

from recording_io import read_recording
from replay_geometry import mesh

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
parser.add_argument('--scene', help='Verify this published scene against source as one recording directory')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
manifest = json.loads((root/'assets/mpc-comparison.json').read_text())
inputs = [(args.source, args.scene)] if args.scene else [
    (args.source/f'{task}-baseline', f'mpc-{task}-baseline') for task in ['table', 'chair', 'door']]
for folder, scene in inputs:
    with np.load(folder/'states.npz') as archive:
        states = {key: archive[key] for key in ['time', 'positions', 'quaternions']}
    geometry = SimpleNamespace(**dict(np.load(folder/'geometry.npz')))
    outcome = json.loads((folder/'result.json').read_text())
    record, buffers = read_recording(root/f'assets/recordings/{scene}.viser')
    assert record['durationSeconds'] == float(states['time'][-1]) == outcome['duration']
    if outcome['task']=='spot_box' or outcome.get('nativeController'):
        gallery=json.loads((root/'assets/controller-gallery.json').read_text())
        entry=next(r for r in gallery if r['scene']==scene)
        assert entry['body']==outcome.get('robot','spot_arm')
        assert entry['outcome']==f"{outcome['moved']:.2f} m moved · {outcome['goalError']:.2f} m goal error · {outcome['duration']:.1f} s"
        np.testing.assert_allclose(next(m['position'] for t,m in record['messages'] if m['type']=='SetCameraPositionMessage'),outcome['camera']['position'])
    else:
        entry = next(r for r in manifest if r['scene'] == scene)
        assert entry['goalReached'] == outcome['goalReached']
    meshes = [m for _, m in record['messages'] if m['type'] == 'MeshMessage']
    used_bodies = set()
    index = 0
    for i, kind in enumerate(geometry.geom_type):
        rgba = geometry.geom_rgba[i]
        if geometry.geom_matid[i] >= 0:
            rgba = geometry.mat_rgba[geometry.geom_matid[i]]
        if geometry.geom_group[i] == 3 or rgba[3] <= 0:
            continue
        message = meshes[index]
        index += 1
        body = int(geometry.geom_bodyid[i])
        used_bodies.add(body)
        assert message['name'].startswith(f'/body-{body}/')
        p = message['props']
        assert p['opacity'] is None
        if kind == 0:
            continue  # The infinite plane is tessellated for the CPU renderer.
        source = mesh(geometry, i)
        expected = Rotation.from_quat(geometry.geom_quat[i], scalar_first=True).apply(source.vertices)
        expected += geometry.geom_pos[i]
        vertices = np.frombuffer(buffers[p['vertices']['__binary_index']], dtype='<f4').reshape(-1, 3)
        faces = np.frombuffer(buffers[p['faces']['__binary_index']], dtype='<u4').reshape(-1, 3)
        np.testing.assert_array_equal(vertices, expected.astype('<f4'))
        np.testing.assert_array_equal(faces, source.faces)
        np.testing.assert_array_equal(p['color'], np.round(rgba[:3]*255))
    assert len(meshes) == index+1  # The one additional mesh is the actual goal ring.
    used_bodies.add(0)  # The goal ring is attached to the world body.
    saved = {'positions': [], 'quaternions': []}
    expected = {'positions': [], 'quaternions': []}
    for time, message in record['messages']:
        if message['type'] not in ['SetPositionMessage', 'SetOrientationMessage'] or not message['name'].startswith('/body-'):
            continue
        frame = int(np.searchsorted(states['time'], time))
        assert states['time'][frame] == time
        body = int(message['name'].split('-')[1])
        field, key = ('positions', 'position') if message['type'] == 'SetPositionMessage' else ('quaternions', 'wxyz')
        saved[field].append(message[key])
        expected[field].append(states[field][frame, body])
    for field in saved:
        assert len(saved[field]) == len(states['time'])*len(used_bodies)
        np.testing.assert_array_equal(saved[field], expected[field])
    text = (root/f'assets/recordings/{scene}.hex.js').read_text()
    encoded = json.loads(text.rsplit(' = ', 1)[1].rstrip(';\n'))
    assert bytes.fromhex(encoded) == (root/f'assets/recordings/{scene}.viser').read_bytes()
    print('PASS', scene, len(states['time']), 'frames, complete visual meshes and exact measured poses')
