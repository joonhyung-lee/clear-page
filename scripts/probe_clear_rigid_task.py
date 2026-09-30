"""Check exact rigid geometry transfer and original ego contact selection on CPU.

This writes private diagnostics only. It does not claim a controller rollout.
The source CLEAR implementation is imported, never edited.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
import torch

from sumo_task_transfer import RigidTaskObject


@contextmanager
def transfer_factories(obj, translation):
    import clear.maze.mjlab_runtime as runtime
    import experiments.exp3.trajectory_v3.native_sumo as native
    original_spec, original_inputs = runtime.box_spec, native.metric_runtime_inputs

    def object_spec(description, cell_m, support_z=0., pose=None):
        if description.object_id != 0:
            return original_spec(description, cell_m, support_z, pose)
        position = obj.initial_position + obj.center + translation
        return obj.spec(position, obj.initial_quaternion)

    def scene_inputs(scene):
        grid, kwargs = original_inputs(scene)
        position = obj.initial_position + obj.center + translation
        kwargs['initial_object_poses'][0] = [*position, 0.]
        return grid, kwargs

    runtime.box_spec, native.metric_runtime_inputs = object_spec, scene_inputs
    try:
        yield
    finally:
        runtime.box_spec, native.metric_runtime_inputs = original_spec, original_inputs


def make_scene(obj, translation):
    start = obj.initial_robot[:2]+translation[:2]
    position = obj.initial_position[:2]+translation[:2]
    goal = np.asarray(obj.result['taskConfig']['goal_position'])[:2]+translation[:2]
    return dict(base_scene_id='native-rigid-object-transfer', world_size=[8., 8.],
                terrain=[], walls=[], floor_friction=1., start=[*start, 0.], goal=[*goal, 0.],
                objects=[dict(object_id=0, pose=[*position, 0.], size=obj.size.tolist(),
                              mass_kg=float(obj.physics.body_mass[obj.body]), friction=.5)])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--contact-checkpoint', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--contact-height', type=float, default=.8)
    parser.add_argument('--furniture-contacts', action='store_true')
    args = parser.parse_args()
    torch.set_num_threads(2)
    obj = RigidTaskObject(args.folder)
    verification = obj.verify()
    args.output.mkdir(parents=True, exist_ok=True)
    translation = np.array([4., 4., 0.])
    scene = make_scene(obj, translation)
    with transfer_factories(obj, translation):
        from experiments.exp3.trajectory_v3.native_sumo import NativeG1World
        from clear.maze.ego_affordance import EgoAffordance
        from clear.maze.robot_registry import BodyPart
        world = NativeG1World(scene, 'cpu', seed=0, g1_contact_palms=True)
        world.state(0)
        assembled_verification = obj.verify(world.model, world.cpu, 'object/', translation)
        frame = world.rt.ego_frame()
        if args.furniture_contacts:
            from furniture_contacts import FurnitureEgoAffordance
            EgoAffordance = FurnitureEgoAffordance
        scorer = EgoAffordance(args.contact_checkpoint, device='cpu', seed=0,
                              contact_prior_height_m=args.contact_height, scoring_mode='learned', pair_mode='feasible')
        part = BodyPart('both_hands', 'arm', 8., .9, .3, 1.2, .55, n_contacts=2, pair_separation_m=.28)
        pose = world.poses(0)[0]
        contact = scorer.contact_set(frame, 0, pose[:2], pose[2], *obj.size, scene['goal'][:2], part, support_z=0.)
        Image.fromarray(frame.rgb).save(args.output/'ego.png')
        np.savez_compressed(args.output/'ego.npz', rgb=frame.rgb, depth=frame.depth, seg=frame.seg,
                            cam_xpos=frame.cam_xpos, cam_xmat=frame.cam_xmat)
        result = dict(scope='Geometry and initial ego contact diagnostic only. No controller rollout.',
                      geometry=verification, assembled_geometry=assembled_verification, scene=scene, contact=contact.to_record(),
                      dt=world.dt, contact_checkpoint_sha256=hashlib.sha256(args.contact_checkpoint.read_bytes()).hexdigest())
        (args.output/'probe.json').write_text(json.dumps(result, indent=2)+'\n')
        print('PROBE COMPLETE', json.dumps(result['contact']), flush=True)
