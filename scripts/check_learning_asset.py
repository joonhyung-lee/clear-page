"""Verify an offline native replay against every saved physical body pose."""
import argparse
import json
from pathlib import Path
import tempfile

import numpy as np
from recording_io import read_recording, validate_binary_arrays
from style_learning_checkpoints import TERRAIN_COLORS


def check(source, body, asset):
    geometry = dict(np.load(source / f'{body}-geometry.npz'))
    states = dict(np.load(source / f'{body}-states.npz'))
    audit = json.loads((source / f'{body}-audit.json').read_text())
    encoded = json.loads(asset.read_text().rsplit(' = ', 1)[1].rstrip(';\n'))
    with tempfile.NamedTemporaryFile() as stream:
        stream.write(bytes.fromhex(encoded))
        stream.flush()
        record, buffers = read_recording(stream.name)
    validate_binary_arrays(record, buffers)

    def array(ref, width):
        return np.frombuffer(buffers[ref['__binary_index']], dtype=ref['dtype']).reshape(-1, width)

    groups = {}
    for index in np.flatnonzero(geometry['geom_group'] == 2):
        part, material, mesh = (int(geometry[k][index]) for k in ['geom_bodyid', 'geom_matid', 'geom_dataid'])
        rgba = geometry['mat_rgba'][material] if material >= 0 else geometry['geom_rgba'][index]
        color = tuple(np.clip(rgba[:3] * 255, 0, 255).astype(int))
        groups[(part, color)] = groups.get((part, color), 0) + int(geometry['mesh_facenum'][mesh])
    meshes = [m for _, m in record['messages'] if m['type'] == 'BatchedMeshesMessage']
    assert len(meshes) == len(groups), 'Missing visual mesh groups'
    stages, frames, agents = states['positions'].shape[:3]
    assert stages == len(audit['stages']) and agents == 32
    dt = float(states['dt'])
    assert abs(record['durationSeconds'] - stages * frames * dt) < 1e-5
    for message, ((part, color), faces) in zip(meshes, groups.items()):
        props = message['props']
        assert len(array(props['faces'], 3)) == faces, 'Visual faces were dropped'
        assert tuple(array(props['batched_colors'], 3)[0]) == color
        assert props['opacity'] is None and props['batched_opacities'] is None
        np.testing.assert_array_equal(array(props['batched_positions'], 3), states['positions'][0, 0, :, part])
        updates = [(t, m['updates']) for t, m in record['messages']
                   if m.get('name') == message['name'] and 'batched_positions' in m.get('updates', {})]
        assert len(updates) == stages * frames, 'Every recorded frame must survive export'
        for index, (timestamp, update) in enumerate(updates):
            stage, frame = divmod(index, frames)
            assert abs(timestamp - index * dt) < 1e-5
            np.testing.assert_array_equal(array(update['batched_positions'], 3), states['positions'][stage, frame, :, part])
            np.testing.assert_array_equal(array(update['batched_wxyzs'], 4), states['quaternions'][stage, frame, :, part])
    colors = {m['name'].rsplit('/', 1)[-1]: tuple(m['props']['color']) for _, m in record['messages']
              if m['type'] == 'MeshMessage' and m['name'].startswith('/terrain/')}
    for terrain in audit['terrains']:
        assert colors[terrain] == TERRAIN_COLORS[terrain]
    print(f'PASS {body}: {len(meshes)} complete mesh groups, {agents} agents, '
          f'all {stages * frames} frames match saved physics, {len(audit["terrains"])} terrain colors')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--body', choices=['g1', 'spot', 'spot_arm'], required=True)
    parser.add_argument('--asset', type=Path, required=True)
    args = parser.parse_args()
    check(args.source, args.body, args.asset)
