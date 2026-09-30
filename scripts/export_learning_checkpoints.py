"""Package anonymous numeric checkpoint reconstructions as interactive Viser scenes."""
import argparse
import json
from pathlib import Path
import numpy as np
import trimesh
import viser
from scipy.spatial.transform import Rotation
from recording_io import read_recording, write_recording
from style_learning_checkpoints import style_recording

p = argparse.ArgumentParser()
p.add_argument('source', type=Path)
p.add_argument('--body', choices=['g1', 'spot', 'spot_arm'], required=True)
p.add_argument('--scene', help='Distinct public scene name for a new training lineage')
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
g = dict(np.load(a.source / (a.body + '-geometry.npz')))
s = dict(np.load(a.source / (a.body + '-states.npz')))
audit = json.loads((a.source / (a.body + '-audit.json')).read_text())

def geometry(i):
    typ, size, mid = int(g['geom_type'][i]), g['geom_size'][i], int(g['geom_dataid'][i])
    if typ == 7:
        v, n = g['mesh_vertadr'][mid], g['mesh_vertnum'][mid]
        f, m = g['mesh_faceadr'][mid], g['mesh_facenum'][mid]
        mesh = trimesh.Trimesh(g['mesh_vert'][v:v+n], g['mesh_face'][f:f+m], process=False)
    elif typ == 6:
        mesh = trimesh.creation.box(extents=size * 2)
    elif typ == 2:
        mesh = trimesh.creation.icosphere(subdivisions=1, radius=size[0])
    elif typ == 3:
        mesh = trimesh.creation.capsule(radius=size[0], height=size[1]*2, count=[8, 8])
    elif typ == 5:
        mesh = trimesh.creation.cylinder(radius=size[0], height=size[1]*2, sections=16)
    elif typ == 4:
        mesh = trimesh.creation.icosphere(subdivisions=2)
        mesh.vertices *= size
    elif typ == 1:
        rows, cols = int(g['hfield_nrow'][mid]), int(g['hfield_ncol'][mid])
        offset = int(g['hfield_adr'][mid])
        scale = g['hfield_size'][mid]
        xx, yy = np.meshgrid(np.linspace(-scale[0], scale[0], cols), np.linspace(-scale[1], scale[1], rows))
        zz = g['hfield_data'][offset:offset+rows*cols].reshape(rows, cols)*scale[2]
        vertices = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])
        ids = np.arange(rows*cols).reshape(rows, cols)
        tl, tr, bl, br = [v.ravel() for v in [ids[:-1, :-1], ids[:-1, 1:], ids[1:, :-1], ids[1:, 1:]]]
        faces = np.concatenate([np.column_stack([tl, tr, br]), np.column_stack([tl, br, bl])])
        mesh = trimesh.Trimesh(vertices, faces, process=False)
    else:
        return None
    mesh.vertices = Rotation.from_quat(g['geom_quat'][i], scalar_first=True).apply(mesh.vertices)+g['geom_pos'][i]
    return mesh

groups = {}
for i, b in enumerate(g['geom_bodyid']):
    if g['geom_rgba'][i, 3] <= 0 or (b and g['geom_group'][i] == 3):
        continue
    # Task assets put physical proxies in group 3 and visual meshes in group 2.
    mesh = geometry(i)
    if mesh is None:
        continue
    if g['geom_group'][i] == 0:
        mesh.vertices = Rotation.from_quat(s['quaternions'][0, 0, 0, b], scalar_first=True).apply(mesh.vertices) + s['positions'][0, 0, 0, b]
        b = 0
    material = int(g['geom_matid'][i])
    rgba = g['mat_rgba'][material] if material >= 0 else g['geom_rgba'][i]
    color = tuple(np.clip(rgba[:3]*255, 0, 255).astype(int))
    if b == 0:
        color = (196, 201, 190) if int(g['geom_type'][i]) == 1 else (209, 213, 202)
    groups.setdefault((int(b), color), []).append(mesh)

server = viser.ViserServer(host='127.0.0.1', port=8099, verbose=False)
server.gui.configure_theme(show_logo=False, show_share_button=False)
server.scene.world_axes.visible = False
server.scene.set_up_direction('+z')
# Inspect an ascending stair example close up. Native camera controls reveal the
# surrounding bank and all 32 independent agents without replacing the scene.
focus = s['origins'][len(audit['terrains'])+1].astype(float)
focus[2] += .55
server.initial_camera.position = tuple(focus + [5.1, -6.5, 4.6])
server.initial_camera.look_at = tuple(focus)
server.initial_camera.fov = .65
handles = []
for group, ((body, color), meshes) in enumerate(groups.items()):
    mesh = trimesh.util.concatenate(meshes)
    name = '/terrain/' if body == 0 else '/agents/'
    name += str(group)
    if body == 0:
        server.scene.add_mesh_simple(name, vertices=mesh.vertices, faces=mesh.faces, color=color, flat_shading=True)
    else:
        handle = server.scene.add_batched_meshes_simple(name, vertices=mesh.vertices, faces=mesh.faces,
            batched_positions=s['positions'][0, 0, :, body],
            batched_wxyzs=s['quaternions'][0, 0, :, body], batched_colors=color, lod='off')
        handles.append((body, handle))
# Labels identify terrain families, never the source machine or run path.
for i, name in enumerate(audit['terrains']):
    origin = s['origins'][i].astype(float)
    server.scene.add_label('/terrain-label/'+str(i), name.replace('_', ' '), position=tuple(origin+[0, 0, .1]))
recording = server.get_scene_serializer()
for stage in range(len(audit['stages'])):
    for frame in range(s['positions'].shape[1]):
        for body, handle in handles:
            handle.batched_positions = s['positions'][stage, frame, :, body]
            handle.batched_wxyzs = s['quaternions'][stage, frame, :, body]
        recording.insert_sleep(float(s['dt']))
out = root / 'assets/recordings' / ((a.scene or 'learning-'+a.body)+'.viser')
out.write_bytes(recording.serialize())
server.stop()
record, buffers = read_recording(out)
record, buffers = style_recording(record, buffers, a.source, a.body)
write_recording(out, record, buffers)
out.unlink()  # Only the packed, self-contained browser asset is published.
print(a.body, 'batches', len(handles), 'size', out.with_suffix('.hex.js').stat().st_size, flush=True)
