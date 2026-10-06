"""Extract recorded native poses and meshes for matching Viser and MP4 views."""
import argparse
import hashlib
import json
from pathlib import Path
import mujoco
import numpy as np
from scipy.spatial.transform import Rotation
from replay_geometry import mesh

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--run', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--title', required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
episode = json.loads((a.run / 'episode.json').read_text())
assert episode['status'] != 'infrastructure_error', 'An infrastructure failure is not a method result'
scene = json.loads((a.run / 'scene.json').read_text())
model = mujoco.MjModel.from_binary_path(str(a.run / 'physics/task.mjb'))
data = mujoco.MjData(model)
with np.load(a.run / 'physics/task.npz') as archive:
    states = dict(archive)
times = states['time']
indices = [0]
for i in range(1, len(times)-1):
    if times[i]-times[indices[-1]] >= .019:
        indices.append(i)
if len(times) > 1:
    indices.append(len(times)-1)
positions, quaternions, palms = [], [], []
sites = [model.site(name).id for name in ['robot/left_palm', 'robot/right_palm']]
for i in indices:
    data.qpos[:] = states['qpos'][i]
    for key in ['mocap_pos', 'mocap_quat']:
        if key in states:
            getattr(data, key)[:] = states[key][i]
    mujoco.mj_forward(model, data)
    positions.append(data.xpos.copy())
    quaternions.append(data.xquat.copy())
    palms.append(data.site_xpos[sites].copy())
positions = np.asarray(positions)
object_bodies = {}
for obj in scene['objects']:
    ids = [i for i in range(model.nbody) if model.body(i).name.startswith('object')
           and np.linalg.norm(positions[0, i, :2]-obj['pose'][:2]) < .05]
    assert len(ids) == 1
    object_bodies[str(obj['object_id'])] = ids[0]
arrays = dict(time=times[indices], positions=positions, quaternions=np.asarray(quaternions), palms=np.asarray(palms))
meshes = []
for i in range(model.ngeom):
    if model.geom_group[i] == 3:
        continue
    mat = model.geom_matid[i]
    rgba = model.geom_rgba[i] if mat < 0 else model.mat_rgba[mat]
    if rgba[3] <= 0:
        continue
    geometry = mesh(model, i)
    geometry.vertices = Rotation.from_quat(model.geom_quat[i], scalar_first=True).apply(geometry.vertices) + model.geom_pos[i]
    k = len(meshes)
    arrays.update({f'vertices_{k}': np.asarray(geometry.vertices, dtype='f4'),
                   f'normals_{k}': np.asarray(geometry.vertex_normals, dtype='f4'),
                   f'faces_{k}': np.asarray(geometry.faces, dtype='u4')})
    meshes.append(dict(body=int(model.geom_bodyid[i]), color=np.round(rgba[:3]*255).astype(int).tolist()))
plans = [dict(time=q['time_s'], call=q['call'], status=q['status'], purpose=q['purpose'],
              paths=q.get('plan', {}).get('paths', []), order=q.get('order', []),
              route=q.get('route'), trace=q.get('trace', []), wall_seconds=q['wall_s'])
         for q in episode['plans']]
for plan, original in zip(plans, episode['plans'], strict=True):
    # Match the actual selected axis-chord plan back to its raw flow draw.
    # A failed call has no selected draw and is explicitly shown as a sample.
    plan['selected_candidate'] = None
    if not plan['paths']:
        continue
    for i, raw in enumerate(original.get('raw_proposals', [])[:episode.get('candidates', 8)]):
        paths = raw.get('paths', [])
        if [x['object_id'] for x in paths] != plan['order']:
            continue
        matches = True
        for proposal, chosen in zip(paths, plan['paths'], strict=True):
            origin = np.asarray(proposal['poses'][0], float)
            target = np.asarray(proposal['poses'][-1], float)
            if episode.get('decoder') == 'axis_chord':
                axis = int(np.argmax(np.abs(target[:2]-origin[:2])))
                value = target[axis]
                target = origin.copy()
                target[axis] = value
            matches &= np.allclose(origin, chosen['poses'][0], atol=1e-7, rtol=0)
            matches &= np.allclose(target, chosen['poses'][-1], atol=1e-7, rtol=0)
        if matches:
            plan['selected_candidate'] = i
            break
events = [{k: e[k] for k in ['object_id', 'start_time_s', 'end_time_s', 'motion_start_s', 'motion_end_s'] if k in e}
          for e in episode.get('external_events', [])]
attempts = [{k: e[k] for k in ['object_id', 'start_time_s', 'end_time_s', 'success']}
            for e in episode.get('attempt_log', [])]
meta = dict(title=a.title, scope='Native CLEAR execution with an explicit upright-palm development controller and tall-box planner adaptation.',
            runtime_profile=episode.get('runtime_profile'), runtime_profile_sha256=episode.get('runtime_profile_sha256'),
            scene=scene, bodies=[f'/body-{i}' for i in range(model.nbody)], meshes=meshes,
            object_bodies=object_bodies, ego_body=model.body('robot/torso_link').id,
            root_body=model.body('robot/pelvis').id, ego_offset=[.14, 0, .30],
            duration=float(times[-1]), plans=plans, events=events, attempts=attempts,
            outcome=episode['status'], success=episode['task_success'], strict_success=episode['strict_success'],
            episodeSHA256=hashlib.sha256((a.run/'episode.json').read_bytes()).hexdigest(),
            recordingSHA256=hashlib.sha256((a.run/'physics/task.npz').read_bytes()).hexdigest())
np.savez_compressed(a.output / 'geometry.npz', **arrays)
(a.output/'timeline.json').write_text(json.dumps(meta, separators=(',', ':')) + '\n')
print('PASS', len(meshes), 'meshes,', len(indices), 'poses,', len(plans), 'planning calls')
