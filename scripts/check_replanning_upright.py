"""Measure the saved physical posture, box geometry and bilateral palm contact."""
import argparse
import hashlib
import json
import os
from pathlib import Path
os.environ.setdefault('MUJOCO_GL', 'egl')
import mujoco
import numpy as np
from PIL import Image

p = argparse.ArgumentParser()
p.add_argument('--physics', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
config = json.loads((a.physics/'result.json').read_text())['config']
profile = config['runtime_profile']
profile_sha = hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()
assert profile_sha == config['runtime_profile_sha256']
assert not profile['low_contact_profile'] and not profile['crouch_offsets']
m = mujoco.MjModel.from_binary_path(str(a.physics/'task.mjb'))
d = mujoco.MjData(m)
with np.load(a.physics/'task.npz') as archive:
    state = dict(archive)
body = m.body('robot/pelvis').id
sites = [m.site('robot/'+side+'_palm').id for side in ['left', 'right']]
elbows = [m.jnt_qposadr[m.joint('robot/'+side+'_elbow_joint').id] for side in ['left', 'right']]
root_z, palm_z, elbow = [], [], []
for q in state['qpos']:
    d.qpos[:] = q
    mujoco.mj_forward(m, d)
    root_z.append(d.xpos[body, 2])
    palm_z.append(d.site_xpos[sites, 2].copy())
    elbow.append(q[elbows])
root_z, palm_z, elbow = map(np.asarray, [root_z, palm_z, elbow])
raised = (palm_z.min(axis=1) > .82) & (np.max(np.abs(elbow), axis=1) < 1.)
assert raised.sum() >= 10, 'No sustained upright, extended bilateral palm posture was recorded'
assert np.quantile(root_z[raised], .05) > .67, 'The recorded contact posture is still crouched'
objects = [g for g in range(m.ngeom) if m.body(m.geom_bodyid[g]).name.startswith('object') and m.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX]
assert objects and all(np.isclose(2*m.geom_size[g, 2], profile['box_height_m']) for g in objects)
audit = json.loads((a.physics/'whole_contact_audit.json').read_text())
contacts = audit['whole_episode_contact_frames_by_body']
assert all(contacts.get('robot/'+side+'_wrist_yaw_link', 0) > 0 for side in ['left', 'right']), 'Both palms must physically contact the box'
assert not audit['whole_episode_forbidden_nonarm_contact'], 'Unexpected non-arm contact'
report = dict(runtime_profile_sha256=profile_sha, frames=len(root_z), raised_palm_frames=int(raised.sum()),
              root_height_p05_m=float(np.quantile(root_z[raised], .05)),
              root_height_median_m=float(np.median(root_z[raised])),
              palm_height_median_m=np.median(palm_z[raised], axis=0).tolist(),
              elbow_median_rad=np.median(elbow[raised], axis=0).tolist(),
              physical_box_height_m=profile['box_height_m'], native_contact_audit=audit)
(a.output/'upright-audit.json').write_text(json.dumps(report, indent=2)+'\n')
i = np.flatnonzero(raised)[len(np.flatnonzero(raised))//2]
d.qpos[:] = state['qpos'][i]
mujoco.mj_forward(m, d)
m.vis.global_.offwidth, m.vis.global_.offheight = 1000, 800
m.vis.headlight.active = 1
m.vis.headlight.ambient[:] = .6
m.vis.headlight.diffuse[:] = .4
cam = mujoco.MjvCamera()
cam.lookat[:] = d.xpos[body]+[0, 0, .1]
cam.distance, cam.azimuth, cam.elevation = 2.5, 0, -15
opt = mujoco.MjvOption()
opt.geomgroup[3] = 0
opt.sitegroup[:] = 0
# Diagnostic cutaway only: keep every measured robot/object pose intact.
for geom in range(m.ngeom):
    if 'wall' in m.geom(geom).name.lower() or 'wall' in m.body(m.geom_bodyid[geom]).name.lower():
        m.geom_rgba[geom, 3] = .10
    elif m.body(m.geom_bodyid[geom]).name.startswith('object'):
        m.geom_rgba[geom, 3] = .25
with mujoco.Renderer(m, height=800, width=1000) as renderer:
    renderer.update_scene(d, camera=cam, scene_option=opt)
    Image.fromarray(renderer.render()).save(a.output/'upright-palm-posture.png')
print('PASS measured upright posture and tall physical boxes:', json.dumps({k:v for k,v in report.items() if k != 'native_contact_audit'}))
