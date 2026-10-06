"""Package anonymous numeric checkpoint reconstructions as interactive Viser scenes."""
import argparse
import json
from pathlib import Path
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation
from recording_io import read_recording, write_recording
from style_learning_checkpoints import style_recording
from export_teaser_method import Recording

p = argparse.ArgumentParser()
p.add_argument('source', type=Path)
p.add_argument('--body', choices=['g1', 'spot', 'spot_arm'], required=True)
p.add_argument('--scene', help='Distinct public scene name for a new training lineage')
p.add_argument('--output-dir', type=Path, help='Optional staging directory for verification before publication')
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

recording = Recording()
recording.emit('SetSceneNodeVisibilityMessage', name='/WorldAxes', visible=False)
# Inspect an ascending stair example close up. Native camera controls reveal the
# surrounding bank and all 32 independent agents without replacing the scene.
focus = s['origins'][len(audit['terrains'])+1].astype(float)
focus[2] += .55
recording.emit('SetCameraPositionMessage', position=list(focus + [5.1, -6.5, 4.6]), initial=True)
recording.emit('SetCameraLookAtMessage', look_at=list(focus), initial=True)
recording.emit('SetCameraFovMessage', fov=.65, initial=True)
handles = []
for group, ((body, color), meshes) in enumerate(groups.items()):
    mesh = trimesh.util.concatenate(meshes)
    name = '/terrain/' if body == 0 else '/agents/'
    name += str(group)
    if body == 0:
        recording.mesh(name, mesh.vertices, mesh.faces, color, [0., 0., 0.])
    else:
        recording.node('BatchedMeshesMessage', name, dict(
            vertices=recording.pack(mesh.vertices, '<f4'), faces=recording.pack(mesh.faces, '<u4'),
            batched_positions=recording.pack(s['positions'][0, 0, :, body], '<f4'),
            batched_wxyzs=recording.pack(s['quaternions'][0, 0, :, body], '<f4'),
            batched_colors=recording.pack(color, 'u1'), batched_scales=None, lod='off',
            wireframe=False, opacity=None, flat_shading=False, side='double',
            material='standard', cast_shadow=True, receive_shadow=True,
            batched_opacities=None, scale=1.))
        handles.append((body, name))
# Labels identify terrain families, never the source machine or run path.
for i, name in enumerate(audit['terrains']):
    origin = s['origins'][i].astype(float)
    recording.label('/terrain-label/'+str(i), name.replace('_', ' '), origin+[0, 0, .1])
time = 0.
for stage in range(len(audit['stages'])):
    for frame in range(s['positions'].shape[1]):
        for body, name in handles:
            recording.emit('SceneNodeUpdateMessage', time, name=name, updates=dict(
                batched_positions=recording.pack(s['positions'][stage, frame, :, body], '<f4'),
                batched_wxyzs=recording.pack(s['quaternions'][stage, frame, :, body], '<f4')))
        time += float(s['dt'])
recording.record['durationSeconds'] = time
out = (a.output_dir or root / 'assets/recordings') / ((a.scene or 'learning-'+a.body)+'.viser')
out.parent.mkdir(parents=True, exist_ok=True)
record, buffers = recording.record, recording.buffers
record, buffers = style_recording(record, buffers, a.source, a.body)
write_recording(out, record, buffers)
out.unlink()  # Only the packed, self-contained browser asset is published.
print(a.body, 'batches', len(handles), 'size', out.with_suffix('.hex.js').stat().st_size, flush=True)
