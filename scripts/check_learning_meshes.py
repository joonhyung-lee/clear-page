"""Compare public learning meshes, terrain and motion to the source reconstructions."""
import argparse
import json
import tempfile
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from recording_io import read_recording

ROOT = Path(__file__).resolve().parents[1]


def main(source):
    for body in ['g1', 'spot', 'spot_arm']:
        text = (ROOT / f'assets/recordings/learning-{body}.hex.js').read_text()
        with tempfile.NamedTemporaryFile() as temporary:
            temporary.write(bytes.fromhex(json.loads(text.rsplit(' = ', 1)[1].rstrip(';\n'))))
            temporary.flush()
            record, buffers = read_recording(temporary.name)
        original, old_buffers = read_recording(source / f'{body}.viser')
        geometry = np.load(source / f'{body}-geometry.npz')
        expected_faces = sum(int(geometry['mesh_facenum'][i]) for i in geometry['geom_dataid'][geometry['geom_group'] == 2])
        agents = [m['props'] for _, m in record['messages'] if m['type'] == 'BatchedMeshesMessage']
        actual_faces = sum(len(buffers[p['faces']['__binary_index']])//12 for p in agents)
        assert actual_faces == expected_faces, (body, actual_faces, expected_faces)
        expected = {}
        for i in np.flatnonzero(geometry['geom_group'] == 2):
            b, mid, mat = (int(geometry[k][i]) for k in ['geom_bodyid', 'geom_dataid', 'geom_matid'])
            rgba = geometry['mat_rgba'][mat] if mat >= 0 else geometry['geom_rgba'][i]
            color = tuple(np.clip(rgba[:3]*255, 0, 255).astype(int))
            va, vn = geometry['mesh_vertadr'][mid], geometry['mesh_vertnum'][mid]
            fa, fn = geometry['mesh_faceadr'][mid], geometry['mesh_facenum'][mid]
            v = Rotation.from_quat(geometry['geom_quat'][i], scalar_first=True).apply(geometry['mesh_vert'][va:va+vn]) + geometry['geom_pos'][i]
            expected.setdefault((b, color), []).append((v, geometry['mesh_face'][fa:fa+fn]))
        assert len(agents) == len(expected)
        for props, ((_, color), parts) in zip(agents, expected.items()):
            offset, vertices, faces = 0, [], []
            for v, f in parts:
                vertices.append(v)
                faces.append(f+offset)
                offset += len(v)
            assert buffers[props['vertices']['__binary_index']] == np.concatenate(vertices).astype('<f4').tobytes()
            assert buffers[props['faces']['__binary_index']] == np.concatenate(faces).astype('<u4').tobytes()
            assert buffers[props['batched_colors']['__binary_index']] == np.array(color, 'u1').tobytes()
        for props in agents:
            assert props['opacity'] is None and props['batched_opacities'] is None
            assert props['side'] == 'double' and props['wireframe'] is False
            assert props['lod'] == 'off'
            assert len(buffers[props['batched_positions']['__binary_index']]) == 32*3*4

        def motion(r, bs):
            # Resolve buffer references, since packing can renumber unchanged arrays.
            def resolve(obj):
                if isinstance(obj, dict):
                    if '__binary_index' in obj:
                        return bs[obj['__binary_index']]
                    return {k: resolve(v) for k, v in obj.items()}
                if isinstance(obj, (list, tuple)):
                    return [resolve(v) for v in obj]
                return obj
            return [resolve((t, m)) for t, m in r['messages'] if m['type'] == 'SceneNodeUpdateMessage']
        assert motion(record, buffers) == motion(original, old_buffers), 'Recorded motion changed'

        def triangles(r, bs):
            result = []
            for _, message in r['messages']:
                if message['type'] != 'MeshMessage':
                    continue
                p = message['props']
                v = np.frombuffer(bs[p['vertices']['__binary_index']], '<f4').reshape(-1, 3)
                f = np.frombuffer(bs[p['faces']['__binary_index']], '<u4').reshape(-1, 3)
                result.extend(v[f].reshape(-1, 9).view('V36').ravel().tolist())
            return sorted(result)
        assert triangles(record, buffers) == triangles(original, old_buffers), 'Terrain geometry changed'
        terrains = json.loads((source / f'{body}-audit.json').read_text())['terrains']
        colors = {m['name'].split('/')[-1]: tuple(m['props']['color']) for _, m in record['messages'] if m['type'] == 'MeshMessage'}
        assert set(terrains).issubset(colors)
        assert len(set(colors.values())) == len(colors), 'Terrain families must have distinct colors'
        assert min(np.linalg.norm(np.array(colors[a])-colors[b]) for a in colors for b in colors if a != b) > 18
        print('PASS', body, actual_faces, 'visual faces, opaque surfaces, 32 agents, distinct terrain colors, unchanged terrain and every motion update')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    main(parser.parse_args().source)
