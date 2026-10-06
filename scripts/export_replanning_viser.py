"""Write the prepared native geometry and poses as a socket-free Viser recording."""
import argparse
import json
from pathlib import Path
import numpy as np
from export_teaser_method import Recording
from attention_lanes import box_vertices
from replanning_timeline import at_time
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
d = json.loads((a.source/'timeline.json').read_text())
with np.load(a.source/'geometry.npz') as archive:
    g = dict(archive)
r = Recording()
r.emit('SetSceneNodeVisibilityMessage', name='/WorldAxes', visible=False)
w, h = d['scene']['world_size']
r.emit('SetCameraPositionMessage', position=[w/2, -h*.15, max(w, h)*1.25], initial=True)
r.emit('SetCameraLookAtMessage', look_at=[w/2, h/2, 0], initial=True)
r.emit('SetCameraFovMessage', fov=.85, initial=True)
for body in d['bodies']:
    r.frame(body)
for i, m in enumerate(d['meshes']):
    r.mesh(d['bodies'][m['body']]+f'/mesh-{i}', g[f'vertices_{i}'], g[f'faces_{i}'], m['color'], [0, 0, 0])
for i, t in enumerate(g['time']):
    for b, name in enumerate(d['bodies']):
        r.position(name, g['positions'][i, b], float(t))
        r.emit('SetOrientationMessage', float(t), name=name, wxyz=g['quaternions'][i, b].tolist())
sizes = {o['object_id']: o['size'] for o in d['scene']['objects']}
for oid in sizes:
    for kind in ['lane', 'ghosts']:
        name = f'/plans/object-{oid}/{kind}'
        r.lines(name, np.zeros((1, 2, 3)), [56, 124, 194], 3)
        r.emit('SetSceneNodeVisibilityMessage', name=name, visible=False)
boundaries = sorted({0., *[p['time'] for p in d['plans']], *[e['end_time_s'] for e in d['attempts']]})
edges = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
for t in boundaries:
    state = at_time(d, t)
    active = {} if state['current'] is None else {p['object_id']: p for p in state['current']['paths']
        if p['object_id'] not in state['fulfilled']}
    for oid in sizes:
        for kind in ['lane', 'ghosts']:
            r.emit('SetSceneNodeVisibilityMessage', t, name=f'/plans/object-{oid}/{kind}', visible=oid in active)
        if oid not in active:
            continue
        poses = active[oid]['poses']
        color = [55, 132, 105] if state['changes'][oid] == 'unchanged' else [56, 124, 194]
        xyz = np.c_[np.asarray(poses)[:, :2], np.full(len(poses), sizes[oid][2]+.03)]
        r.line_update(f'/plans/object-{oid}/lane', np.stack([xyz[:-1], xyz[1:]], 1), color, t)
        segments = []
        for pose in [poses[len(poses)//2], poses[-1]]:
            vv = box_vertices(pose, sizes[oid])
            segments.extend([[vv[i], vv[j]] for i, j in edges])
        r.line_update(f'/plans/object-{oid}/ghosts', segments, color, t)
r.record['durationSeconds'] = d['duration']
a.output.parent.mkdir(parents=True, exist_ok=True)
r.save(a.output)
print('PASS Viser recording', a.output)
