"""Verify contact-anchor XYZ against independent MuJoCo capsule geometry."""
import argparse
from pathlib import Path
from types import SimpleNamespace
import mujoco
import numpy as np
import torch
from palm_surface_points import palm_site_targets, _original

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('recordings', type=Path, nargs='+')
p.add_argument('--original', action='store_true', help='Reproduce the original normal-only error')
a = p.parse_args()
convert = _original if a.original else palm_site_targets
count = 0
for folder in a.recordings:
    model = mujoco.MjModel.from_binary_path(str(folder/'task.mjb'))
    states = np.load(folder/'states.npz')
    data = mujoco.MjData(model)
    sites = [model.site('robot/'+side+'_palm').id for side in ('left','right')]
    geoms = [model.geom('robot/'+side+'_hand_collision').id for side in ('left','right')]
    for q in states['qpos'][::max(1,len(states['qpos'])//12)]:
        data.qpos[:] = q
        mujoco.mj_forward(model, data)
        rotation = torch.tensor(data.site_xmat[sites].reshape(1,2,3,3), dtype=torch.float64)
        surface = torch.tensor([[[3.,4.14,.45],[3.,3.86,.45]]], dtype=torch.float64)
        for angle in (0., .6, 1.7, 3.):
            normal = np.array([np.cos(angle),np.sin(angle),0.])
            c = SimpleNamespace(rt=SimpleNamespace(model=model), site_ids=sites,
                                direction=torch.tensor(normal[:2], dtype=torch.float64))
            result = convert(c, surface, rotation).numpy()[0]
            for hand,(sid,gid) in enumerate(zip(sites,geoms)):
                # Independent world-space FK, rather than the converter's
                # cached local geometry or quaternion implementation.
                axis = data.geom_xmat[gid].reshape(3,3)[:,2]
                endpoint = (data.geom_xpos[gid] - data.site_xpos[sid]
                            + np.sign(axis@normal)*axis*model.geom_size[gid,1])
                support = result[hand] + endpoint + normal*model.geom_size[gid,0]
                np.testing.assert_allclose(support, surface.numpy()[0,hand], atol=1e-9,
                    err_msg='Capsule support point misses the requested observed surface in XYZ')
                count += 1
print('PASS',count,'palm support points match XYZ across recorded poses and push directions')
