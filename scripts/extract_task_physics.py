"""Extract numeric native task physics using the model's MuJoCo version.

The output is an intermediate input for a geometry transfer, not a rollout.
"""
import argparse
from pathlib import Path
import mujoco
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('folder', type=Path)
args = parser.parse_args()
model = mujoco.MjModel.from_binary_path(str(args.folder/'task.mjb'))
fields = [
    'body_parentid', 'body_pos', 'body_quat', 'body_ipos', 'body_iquat', 'body_mass', 'body_inertia',
    'body_jntadr', 'body_jntnum', 'jnt_type', 'jnt_pos', 'jnt_axis',
    'geom_type', 'geom_size', 'geom_pos', 'geom_quat', 'geom_bodyid', 'geom_dataid',
    'geom_rgba', 'geom_matid', 'geom_group', 'geom_contype', 'geom_conaffinity', 'geom_condim',
    'geom_friction', 'geom_solmix', 'geom_solref', 'geom_solimp', 'geom_margin', 'geom_gap', 'geom_priority',
    'mat_rgba', 'mesh_vert', 'mesh_face', 'mesh_vertadr', 'mesh_vertnum', 'mesh_faceadr', 'mesh_facenum',
]
np.savez_compressed(args.folder/'physics.npz', **{key: np.asarray(getattr(model, key)) for key in fields})
print('Saved numeric task physics')
