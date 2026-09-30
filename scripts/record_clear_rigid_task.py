"""Record the original CLEAR controller on a verified rigid task transfer.

The optional low contact profile selects an existing source controller posture.
An optional furniture contact adapter changes the observed surface filter.
MPC costs and success conditions remain unchanged.
Raw records stay in the requested private output directory.
"""
import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import time

import mujoco
import numpy as np
import torch

from probe_clear_rigid_task import make_scene, transfer_factories
from sumo_task_transfer import RigidTaskObject
from clear_cpu_arrays import empty_cpu_arrays


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--contact-checkpoint', type=Path, required=True)
    parser.add_argument('--controller-record', type=Path,
                        help='Apply recorded G1 palm and MPC settings, overriding their constructor defaults')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=60.)
    parser.add_argument('--contact-height', type=float, default=.8)
    parser.add_argument('--contact-height-band', type=float, nargs=2, metavar=('MIN','MAX'))
    parser.add_argument('--palm-separation', type=float, default=.28)
    parser.add_argument('--low-contact-profile', type=Path)
    parser.add_argument('--furniture-contacts', action='store_true')
    parser.add_argument('--force-contact-memory-s', type=float, default=0.)
    parser.add_argument('--replan-after-contact', action='store_true')
    parser.add_argument('--palm-trust-region', type=float, default=.25)
    parser.add_argument('--palm-gain', type=float, default=.25)
    parser.add_argument('--single-hand-forward-scale', type=float, default=1.)
    parser.add_argument('--surface-contact-targets', action='store_true')
    parser.add_argument('--surface-target-mode', choices=['normal','point'], default='normal')
    parser.add_argument('--settle-palm-height', action='store_true')
    parser.add_argument('--align-contact-face', action='store_true')
    parser.add_argument('--contact-memory-s', type=float, default=0.)
    parser.add_argument('--observed-contact-memory-s', type=float, default=0.,
                        help='Bounded rigid mapping of an earlier observed pair using measured object pose')
    parser.add_argument('--contact-pairing', choices=['feasible','centered'], default='feasible')
    parser.add_argument('--upright', action='store_true', help='Use the low arm reference without the optional leg crouch')
    args = parser.parse_args()
    recorded = json.loads(args.controller_record.read_text()) if args.controller_record else None
    config = recorded['config'] if recorded else {}
    if recorded and (recorded['body'] != 'g1' or config.get('selector') != 'laqdpp'):
        parser.error('--controller-record must describe the G1 LA-QDPP controller')
    palm_gain = config.get('palm_gain', args.palm_gain)
    if args.palm_separation <= 0 or (args.contact_height_band and not 0 <= args.contact_height_band[0] < args.contact_height_band[1]):
        parser.error('Positive palm separation and an increasing nonnegative height band are required')
    if args.upright and not args.low_contact_profile:
        parser.error('--upright requires --low-contact-profile')
    if args.settle_palm_height and not args.low_contact_profile:
        parser.error('--settle-palm-height requires --low-contact-profile')
    if args.align_contact_face and not args.settle_palm_height:
        parser.error('--align-contact-face requires --settle-palm-height')
    if args.surface_target_mode == 'point' and not args.surface_contact_targets:
        parser.error('--surface-target-mode point requires --surface-contact-targets')
    profile = None
    if args.low_contact_profile:
        profile = json.loads(args.low_contact_profile.read_text())
        checkpoint = Path(profile['checkpoint'])
        if not checkpoint.is_absolute():
            checkpoint = args.low_contact_profile.resolve().parents[1] / checkpoint
        profile['checkpoint'] = str(checkpoint)
        if args.upright:
            profile['crouch'] = False
        assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == profile['checkpoint_sha256']
        if args.settle_palm_height and not profile.get('reach_contract'):
            parser.error('--settle-palm-height requires a profile with reach_contract enabled')
    torch.set_num_threads(2)
    obj = RigidTaskObject(args.folder)
    args.output.mkdir(parents=True, exist_ok=True)
    translation = np.array([4., 4., 0.])
    scene = make_scene(obj, translation)
    from palm_surface_points import surface_point_conversion
    with surface_point_conversion(args.surface_target_mode == 'point'), empty_cpu_arrays(), transfer_factories(obj, translation):
        from experiments.exp3.trajectory_v3.native_sumo import NativeG1World, G1WholePathMPC, ContactUnavailable
        if args.settle_palm_height:
            from settled_contact import SettledContactMPC
            G1WholePathMPC = SettledContactMPC
        from experiments.exp3.trajectory_v3.contracts import ObjectPath
        from experiments.exp3.trajectory_v3.execution import MPCPathExecutor
        from clear.maze.sampling_mpc import SampleBank
        real = NativeG1World(scene, 'cpu', seed=0, g1_contact_palms=True,
                             g1_contact_palm_gain=palm_gain,
                             g1_low_contact_profile=profile,
                             contact_wrench_telemetry=args.force_contact_memory_s>0)
        palm = real.rt.contact_palm
        palm.trust_region_rad = config.get('palm_trust_region', args.palm_trust_region)
        palm.single_hand_forward_scale = config.get('single_hand_forward_scale', args.single_hand_forward_scale)
        palm.contact_surface_offset = config.get('surface_target', args.surface_contact_targets)
        if recorded:
            # Same setting application order as the source g1_metric_path runner.
            palm.normal_force_target_n = config.get('normal_force_target_n')
            palm.yaw_balance_gain = config['yaw_balance_gain']
            palm.stabilize_palm_yaw = config['stabilize_palm_yaw']
            palm.progress_braking_enabled = config['progress_braking']
            if config['eef_cross_track']:
                palm.eef_lateral_gain = .5
                palm.eef_lateral_limit_m = config['eef_lateral_limit_m']
                palm.cross_track_enabled = False
            if config['corrected_cross_track']:
                palm.cross_track_gain = -1.2
            if config['base_cross_track_gain'] is not None:
                palm.cross_track_enabled = True
                palm.cross_track_gain = config['base_cross_track_gain']
        real.state(0)
        verification = obj.verify(real.model, real.cpu, 'object/', translation)
        bank = SampleBank(real.rt, 24)
        bank.broadcast()
        assert bank.rt.contact_palm.gain == palm.gain == palm_gain
        for key in ('trust_region_rad','single_hand_forward_scale','contact_surface_offset',
                    'yaw_balance_gain','stabilize_palm_yaw','progress_braking_enabled',
                    'eef_lateral_gain','eef_lateral_limit_m','cross_track_enabled','cross_track_gain'):
            assert getattr(bank.rt.contact_palm,key) == getattr(palm,key), key
        cloning = bank.verify()
        assert max(cloning.values()) < 1e-5, cloning
        print('GEOMETRY VERIFIED', json.dumps(verification), 'BANK VERIFIED', cloning, flush=True)
        model = real.model
        fields = ['geom_type', 'geom_size', 'geom_pos', 'geom_quat', 'geom_bodyid', 'geom_dataid',
                  'geom_rgba', 'geom_matid', 'geom_group', 'mat_rgba', 'mesh_vert', 'mesh_face',
                  'mesh_vertadr', 'mesh_vertnum', 'mesh_faceadr', 'mesh_facenum']
        np.savez_compressed(args.output/'geometry.npz', **{key: np.asarray(getattr(model, key)) for key in fields})
        mujoco.mj_saveModel(model, str(args.output/'task.mjb'))
        times, qpos, qvel, positions, quaternions = [], [], [], [], []
        began = time.monotonic()

        def record():
            real.state(0)  # Recompute derived transforms from the measured integration state.
            times.append(float(real.steps*real.dt))
            qpos.append(real.cpu.qpos.copy())
            qvel.append(real.cpu.qvel.copy())
            positions.append(real.cpu.xpos.copy())
            quaternions.append(real.cpu.xquat.copy())
            if len(times) == 1 or times[-1]-getattr(record, 'last_report', -1) >= 1.-1e-6:
                record.last_report = times[-1]
                print('CLEAR', obj.result['task'], f't={times[-1]:.2f}',
                      f'wall={time.monotonic()-began:.1f}s', flush=True)
                np.savez_compressed(args.output/'checkpoint.npz', time=times, qpos=qpos, qvel=qvel,
                                    positions=positions, quaternions=quaternions)

        backend = G1WholePathMPC(real, bank, contact_checkpoint=args.contact_checkpoint, seed=0,
                                record=record, worlds=24, horizon_s=.6,
                                residual_scale=.05 if config.get('bounded_residual') else .2,
                                residual_space='normalized' if config.get('bounded_residual') else 'raw',
                                local_tangent_guide=config.get('local_tangent_guide',False),
                                apply_steps=max(1, round(.1/real.dt)),
                                contact_height=args.contact_height, contact_pairing=args.contact_pairing,
                                contact_max_age_s=args.contact_memory_s, record_rollouts=True)
        backend.force_contact_memory_s = args.force_contact_memory_s
        backend.observed_contact_memory_s = args.observed_contact_memory_s
        backend.align_contact_face = args.align_contact_face
        backend.part = replace(backend.part, pair_separation_m=args.palm_separation)
        if args.contact_height_band:
            backend.part = replace(backend.part, h_min=args.contact_height_band[0], h_max=args.contact_height_band[1])
        if args.furniture_contacts:
            from furniture_contacts import FurnitureEgoAffordance
            backend.ego = FurnitureEgoAffordance(args.contact_checkpoint, device='cpu', seed=0,
                contact_prior_height_m=args.contact_height, scoring_mode='learned', pair_mode=args.contact_pairing)
        start = real.poses(0)[0].copy()
        goal = np.r_[scene['goal'][:2], 0.]
        path = ObjectPath(0, tuple(map(tuple, np.linspace(start, goal, 12))))
        record()
        try:
            driver = backend
            if args.replan_after_contact:
                # Contact acquisition can move or rotate a light object. Plan
                # from that measured pose without resetting the physical world.
                backend.begin_interaction(path)
                acquired = real.poses(0)[0].copy()
                path = ObjectPath(0, tuple(map(tuple, np.linspace(acquired, goal, 12))))
                class PreparedBackend:
                    def __getattr__(self, name):
                        return getattr(backend, name)
                    def begin_interaction(self, next_path):
                        np.testing.assert_allclose(real.poses(0)[0], next_path.start, atol=1e-6)
                        backend.path = next_path
                        real.rt.contact_palm.set_path(next_path.poses)
                driver = PreparedBackend()
            result = MPCPathExecutor(driver, timeout_s=args.seconds, settle_s=.3,
                                     position_tolerance=.15, yaw_tolerance=np.deg2rad(15),
                                     goal_position_tolerance=.08, goal_yaw_tolerance=.12).interact_trajectory(path)
            execution = asdict(result)
        except ContactUnavailable as error:
            execution = dict(success=False, failure='CONTACT_UNAVAILABLE', details=dict(reason=str(error)))
        np.savez_compressed(args.output/'states.npz', time=times, qpos=qpos, qvel=qvel,
                            positions=positions, quaternions=quaternions)
        target = model.body('object/box').id
        metadata = dict(task=obj.result['task'], controller='CLEAR Cartesian contact tracking with LA-QDPP MPC',
            seed=0, duration=times[-1], goalReached=bool(execution['success']),
            fell=bool(real.state(0)['fell']), population=24, elites=3, horizon=.6,
            controlInterval=backend.apply_steps*real.dt, mujoco=mujoco.__version__, targetBody=target,
            taskConfig=dict(goal_position=[*goal[:2], obj.center[2]]), robotBody=real.robot_root,
            objectDisplacement=float(np.linalg.norm(positions[-1][target, :2]-positions[0][target, :2])),
            goalError=float(np.linalg.norm(real.poses(0)[0, :2]-goal[:2])),
            geometrySHA256=hashlib.sha256((args.output/'geometry.npz').read_bytes()).hexdigest(),
            contactCheckpointSHA256=hashlib.sha256(args.contact_checkpoint.read_bytes()).hexdigest(),
            scope='CLEAR MPC and learned weights on transferred rigid SUMO object physics. Optional contact adaptations are recorded below. '
                  'Translation is (4, 4) metres. Robot reset, runtime, reward, and stopping conditions differ from SUMO.',
            geometryVerification=verification, bankVerification=cloning, execution=execution,
            controllerSettings=real.rt.contact_palm.metadata(),
            lowContactProfile=profile, contactPairing=args.contact_pairing,
            furnitureContacts=args.furniture_contacts, forceContactMemorySeconds=args.force_contact_memory_s,
            replanAfterContact=args.replan_after_contact, measuredContactMemorySeconds=args.contact_memory_s,
            observedContactMemorySeconds=args.observed_contact_memory_s,
            contactHeightBand=args.contact_height_band, palmSeparation=args.palm_separation,
            settlePalmHeight=args.settle_palm_height,
            alignContactFace=args.align_contact_face,
            surfaceTargetMode=args.surface_target_mode,
            controllerRecordSHA256=hashlib.sha256(args.controller_record.read_bytes()).hexdigest() if recorded else None,
            residualSpace=backend.residual_space, localTangentGuide=backend.local_tangent_guide,
            bilateralContactObservations=sum(set(m["sides"])=={"left","right"} for m in backend.contact_measurements),
            posturePreparations=backend.posture_preparations)
        serialize = lambda value: value.tolist() if isinstance(value, np.ndarray) else value.item()
        (args.output/'result.json').write_text(json.dumps(metadata, indent=2, default=serialize)+'\n')
        (args.output/'contacts.json').write_text(json.dumps(backend.contacts, default=serialize)+'\n')
        (args.output/'contact-measurements.json').write_text(json.dumps(backend.contact_measurements, default=serialize)+'\n')
        if hasattr(backend, 'last_frame'):
            frame = backend.last_frame
            np.savez_compressed(args.output/'last-ego.npz', rgb=frame.rgb, depth=frame.depth,
                                seg=frame.seg, cam_xpos=frame.cam_xpos, cam_xmat=frame.cam_xmat,
                                fovy=frame.fovy)
            (args.output/'last-ego-geoms.json').write_text(json.dumps(dict(
                object_geoms=frame.object_geoms, robot_geoms=frame.robot_geoms), default=serialize)+'\n')
        (args.output/'commands.json').write_text(json.dumps(backend.execution_commands, default=serialize)+'\n')
        (args.output/'optimizer.json').write_text(json.dumps(backend.stats, default=serialize)+'\n')
        if backend.rollout_records:
            np.savez_compressed(args.output/'rollouts.npz',
                **{key: np.array([r[key] for r in backend.rollout_records]) for key in backend.rollout_records[0]})
        print('COMPLETE', json.dumps(dict(duration=times[-1], execution=execution), default=serialize), flush=True)


if __name__ == '__main__':
    main()
