"""Restore complete visual meshes and color terrain without changing recorded motion.

Works offline on existing recordings. Source archives stay outside public assets.
"""
import argparse
import copy
import json
import tempfile
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation
from recording_io import read_recording, write_recording

TERRAIN_COLORS = {
    'flat': (160, 199, 224),
    'stairs_up': (235, 177, 140),
    'stairs_down': (232, 215, 143),
    'slope_up': (153, 205, 168),
    'slope_down': (177, 166, 218),
    'random_rough': (218, 162, 197),
    'border': (245, 248, 247),
}

def learning_lighting(record):
    """Use neutral lighting instead of the player's bright default HDRI/key."""
    names={'/learning-fill','/learning-key'}
    record['messages']=[(t,m) for t,m in record['messages']
        if m.get('name') not in names and m['type'] not in ['EnvironmentMapMessage','EnableLightsMessage']]
    messages=[
        dict(type='EnableLightsMessage',enabled=False,cast_shadow=False),
        dict(type='EnvironmentMapMessage',hdri=None,background=False,
             background_blurriness=0.,background_intensity=1.,background_wxyz=[1.,0.,0.,0.],
             environment_intensity=0.,environment_wxyz=[1.,0.,0.,0.]),
        dict(type='AmbientLightMessage',name='/learning-fill',props=dict(color=[255,255,255],intensity=2.)),
        dict(type='DirectionalLightMessage',name='/learning-key',props=dict(color=[255,255,255],intensity=1.2,cast_shadow=False)),
        dict(type='SetPositionMessage',name='/learning-key',position=[4.,-6.,12.]),
        *[dict(type='SetSceneNodeVisibilityMessage',name=name,visible=True) for name in sorted(names)],
    ]
    record['messages']=[(0.,m) for m in messages]+record['messages']
    return record


def terrain_hierarchy(record):
    """Native replay messages need explicit parents before their child meshes."""
    result, frames = [], {''}
    visibility_names={m['name'] for _,m in record['messages'] if m['type']=='SetSceneNodeVisibilityMessage'}
    node_types = {'FrameMessage', 'MeshMessage', 'BatchedMeshesMessage', 'LabelMessage'}
    for time, message in record['messages']:
        if message['type'] in node_types:
            name = message['name']
            if name.startswith('/terrain/'):
                parent = name.rpartition('/')[0]
                if parent not in frames:
                    assert parent.rpartition('/')[0] in frames, parent
                    result.append((time, dict(type='FrameMessage', name=parent,
                        props=dict(show_axes=False, axes_length=.5, axes_radius=.025,
                                   origin_radius=.05, origin_color=[236,236,0], scale=1.))))
                    frames.add(parent)
            frames.add(name)
        result.append((time, message))
        if message['type']=='MeshMessage' and message['name'].startswith('/terrain/') and message['name'] not in visibility_names:
            # Rewind hides every existing mesh before replaying time zero.
            result.append((time, dict(type='SetSceneNodeVisibilityMessage', name=message['name'], visible=True)))
    record['messages'] = result
    return record


def style_recording(record, buffers, source, body):
    g = np.load(source / f'{body}-geometry.npz')
    s = np.load(source / f'{body}-states.npz')
    terrain_names = json.loads((source / f'{body}-audit.json').read_text())['terrains']

    def array(ref, dtype):
        return np.frombuffer(buffers[ref['__binary_index']], dtype=dtype).reshape(-1, 3)

    def pack(values, dtype):
        index = len(buffers)
        buffers.append(np.asarray(values, dtype=dtype).tobytes())
        return {'__binary_index': index, 'dtype': np.dtype(dtype).str}

    # Same body/material grouping as the exporter, retaining every visual face.
    groups = {}
    for i in np.flatnonzero(g['geom_group'] == 2):
        assert g['geom_type'][i] == 7, 'Expected source visual triangle mesh'
        b, mid, mat = (int(g[k][i]) for k in ['geom_bodyid', 'geom_dataid', 'geom_matid'])
        rgba = g['mat_rgba'][mat] if mat >= 0 else g['geom_rgba'][i]
        color = tuple(np.clip(rgba[:3] * 255, 0, 255).astype(int))
        va, vn = g['mesh_vertadr'][mid], g['mesh_vertnum'][mid]
        fa, fn = g['mesh_faceadr'][mid], g['mesh_facenum'][mid]
        vertices = Rotation.from_quat(g['geom_quat'][i], scalar_first=True).apply(g['mesh_vert'][va:va+vn]) + g['geom_pos'][i]
        groups.setdefault((b, color), []).append((vertices, g['mesh_face'][fa:fa+fn]))

    agents = [m for _, m in record['messages'] if m['type'] == 'BatchedMeshesMessage']
    assert len(agents) == len(groups), 'Source visual parts must match recorded batches'
    for message, ((b, color), meshes) in zip(agents, groups.items()):
        props = message['props']
        assert np.array_equal(array(props['batched_colors'], 'u1')[0], color)
        assert np.allclose(array(props['batched_positions'], '<f4'), s['positions'][0, 0, :, b])
        vertices, faces, offset = [], [], 0
        for v, f in meshes:
            vertices.append(v)
            faces.append(f + offset)
            offset += len(v)
        props.update(vertices=pack(np.concatenate(vertices), '<f4'), faces=pack(np.concatenate(faces), '<u4'),
                     opacity=None, batched_opacities=None, wireframe=False, side='double', lod='off')
        # Viser's None is the fully opaque path (transparent=false), not alpha blending.

    # Terrain columns follow the recorded environment origins. Partition existing
    # triangles, keeping every coordinate and face, including the border floor.
    columns = s['origins'][:len(terrain_names), 1]
    half_tile = float(np.diff(columns).min()) / 2
    replacements, removed = [], set()
    for time, message in record['messages']:
        if message['type'] != 'MeshMessage' or not message['name'].startswith('/terrain/'):
            replacements.append((time, message))
            continue
        removed.add(message['name'])
        props = message['props']
        v, f = array(props['vertices'], '<f4'), array(props['faces'], '<u4')
        centers = v[f].mean(axis=1)
        family = np.abs(centers[:, 1, None] - columns).argmin(axis=1)
        family[(centers[:, 1] < columns.min()-half_tile) | (centers[:, 1] > columns.max()+half_tile)] = len(terrain_names)
        for index, name in enumerate(terrain_names + ['border']):
            selected = f[family == index]
            if not len(selected):
                continue
            used, remapped = np.unique(selected, return_inverse=True)
            part = copy.deepcopy(message)
            part['name'] = '/'.join(message['name'].split('/')[:3]) + '/' + name
            part['props'].update(vertices=pack(v[used], '<f4'), faces=pack(remapped.reshape(-1, 3), '<u4'),
                                 color=TERRAIN_COLORS[name], opacity=None, side='double', receive_shadow=False)
            replacements.append((time, part))
    record['messages'] = [(t, m) for t, m in replacements if not (
        m['type'] == 'SetSceneNodeVisibilityMessage' and m.get('name') in removed)]
    # Drop superseded geometry buffers to keep the self-contained asset compact.
    compact, indices = [], {}

    def visit(value):
        if isinstance(value, dict):
            if '__binary_index' in value:
                old = value['__binary_index']
                if old not in indices:
                    indices[old] = len(compact)
                    compact.append(buffers[old])
                value['__binary_index'] = indices[old]
            else:
                for child in value.values():
                    visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)
    visit(record)
    return learning_lighting(terrain_hierarchy(record)), compact


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--body', choices=['g1', 'spot', 'spot_arm'], required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    asset = root / f'assets/recordings/learning-{args.body}.hex.js'
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / f'learning-{args.body}.viser'
        path.write_bytes(bytes.fromhex(json.loads(asset.read_text().rsplit(' = ', 1)[1].rstrip(';\n'))))
        record, buffers = read_recording(path)
        record, buffers = style_recording(record, buffers, args.source, args.body)
        write_recording(path, record, buffers)
        asset.write_bytes(path.with_suffix('.hex.js').read_bytes())
    print(args.body, 'complete visual meshes and terrain colors written')
