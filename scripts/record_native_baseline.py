"""Record native SUMO CEM without importing the CLEAR controller.

Use the pinned SUMO interpreter. --source transfers scene geometry and layout,
not controller code or arm commands. Raw source paths remain in private outputs.
"""
import argparse
from dataclasses import asdict
import hashlib
import inspect
import json
from pathlib import Path
import time

import mujoco
import numpy as np
import sumo.tasks
import sumo.controller
from sumo.run_mpc.run_mpc import _create_sim
from sumo.controller import Controller, ControllerConfig
from sumo.utils.mujoco import G1RolloutBackend
from judo.tasks import get_registered_tasks
from judo.optimizers import get_registered_optimizers
from judo.app.structs import MujocoState


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, default=lambda x: x.tolist())+'\n')


def prepare_spot_assets(path, output):
    # Offline path resolution only. Keep the original MJCF and mesh content.
    import sumo.tasks.spot.spot_base as module
    cache = output/'asset-paths'
    cache.mkdir()
    (cache/'assets').symlink_to(path/'meshes', target_is_directory=True)
    (cache/'spot.png').symlink_to(path/'spot.png')
    module._get_spot_menagerie_dir = lambda: cache


def shared_scene(sim, robot, source, physics_path=None):
    task = sim.task
    if robot == 'g1':
        from sumo.tasks.g1.g1_box import G1Box
        archive = np.load(source/'task.npz')
        initial = archive['qpos'][0].copy()
        native = task.reset_pose.copy()
        # Native joint reset; never inherit CLEAR's prepared palm posture.
        initial[7:36] = native[7:36]
        initial[2] = native[2]
        class SceneTask(G1Box):
            @property
            def reset_pose(self):
                return initial.copy()
        task = SceneTask(model_path=str(source/'scene.xml'))
        sim.task = task
        sim._sim_backend.task_to_sim_ctrl = task.task_to_sim_ctrl
        task.reset()
        scene = json.loads(str(archive['scene']))
        reference = json.loads(str(archive['reference_paths']))[0]['poses']
        size = scene['objects'][0]['size']
        task.config.goal_position = np.array([0., 0., size[2]/2])
        return scene, reference, size

    original = json.loads((source/'result.json').read_text())
    scene = original['input_scene']
    reference = original['reference_plan']['paths'][0]['poses']
    obj = scene['objects'][0]
    assert physics_path, 'Shared Spot scenes require the source model contact parameters'
    physics = json.loads(physics_path.read_text())
    spec = task.spec
    body = spec.body('box_body')
    size = np.asarray(obj['size'])
    body.mass = physics['mass']
    body.inertia = physics['inertia']
    body.ipos = physics['ipos']
    for name in ['box_collision', 'box_visual']:
        geom = spec.geom(name)
        geom.size = size/2
    for name, params in [('box_collision', physics['box']), ('ground', physics['floor'])]:
        for key, value in params.items():
            setattr(spec.geom(name), key, value)
    for i, (x0, y0, x1, y1) in enumerate(scene['walls']):
        spec.worldbody.add_geom(name=f'boundary_{i}', type=mujoco.mjtGeom.mjGEOM_BOX,
            pos=[(x0+x1)/2, (y0+y1)/2, .65], size=[(x1-x0)/2, (y1-y0)/2, .65],
            rgba=[.82, .85, .84, 1.])
    task.model = spec.compile()
    task.sim_model = task.model
    task.data = mujoco.MjData(task.model)
    initial = task.reset_pose.copy()
    initial[:2] = scene['start'][:2]
    initial[3:7] = [np.cos(scene['start'][2]/2), 0, 0, np.sin(scene['start'][2]/2)]
    index = task.object_pose_idx
    initial[index:index+7] = [*obj['pose'][:2], size[2]/2, np.cos(obj['pose'][2]/2),
        0, 0, np.sin(obj['pose'][2]/2)]
    task.data.qpos[:] = initial
    task.config.goal_position = np.array([*reference[-1][:2], size[2]/2])
    mujoco.mj_forward(task.model, task.data)
    sim._init_cpp_systems(get_registered_tasks()['spot_box_push'].locomotion_policy_path)
    sim.reset_policy_state()
    return scene, reference, size.tolist()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--robot', choices=['g1', 'spot_arm'], required=True)
    p.add_argument('--source', type=Path)
    p.add_argument('--spot-assets', type=Path)
    p.add_argument('--scene-physics', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seconds', type=float, default=40.)
    p.add_argument('--seed', type=int, default=0)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    if a.robot == 'spot_arm' and a.spot_assets:
        prepare_spot_assets(a.spot_assets, a.output)
    name = 'g1_box' if a.robot == 'g1' else 'spot_box_push'
    np.random.seed(a.seed)
    sim = _create_sim(name)
    if a.source:
        scene, reference, size = shared_scene(sim, a.robot, a.source, a.scene_physics)
    task = sim.task
    model, data = task.model, task.data
    target = int(model.jnt_bodyid[model.joint('box_joint').id])
    address = int(np.asarray(task.object_pose_idx).ravel()[0])
    if not a.source:
        geoms = np.flatnonzero(model.geom_bodyid == target)
        box = next(i for i in geoms if model.geom_type[i] == mujoco.mjtGeom.mjGEOM_BOX)
        size = (2*model.geom_size[box]).tolist()
        start = data.qpos[address:address+2].copy()
        goal = np.asarray(task.config.goal_position)[:2]
        reference = np.column_stack([np.linspace(start, goal, 8), np.zeros(8)]).tolist()
        scene = dict(scope='Native stock task')
    sites = ['left_palm', 'right_palm'] if a.robot == 'g1' else ['site_arm_link_fngr']
    site_ids = [model.site(n).id for n in sites]
    body_ids = [int(model.site_bodyid[i]) for i in site_ids]

    # The SUMO Spot config omits fields required by inherited JUDO success().
    # Restore JUDO's default terminal fields only. Reward and actions are untouched.
    terminal_compatibility = {}
    if a.robot == 'spot_arm':
        from judo.tasks.spot.spot_box_push import SpotBoxPushConfig as NativeConfig
        defaults = NativeConfig()
        for key, val in dict(goal_pos=task.config.goal_position.copy(),
                goal_distance_threshold=defaults.goal_distance_threshold,
                spot_fallen_threshold=defaults.spot_fallen_threshold).items():
            if not hasattr(task.config, key):
                setattr(task.config, key, val)
                terminal_compatibility[key] = val
        from judo.tasks.spot.spot_constants import ARM_UNSTOWED_POS, ARM_JOINT_NAMES
        arm_addresses = [int(model.joint(n).qposadr[0]) for n in ARM_JOINT_NAMES]
        assert np.allclose(data.qpos[arm_addresses], ARM_UNSTOWED_POS)
        assert task.nu == 10
    else:
        arm_addresses = []
        assert not task.use_left_arm and not task.use_right_arm and task.nu == 3

    cls, config_cls = get_registered_optimizers()['cem']
    oc = config_cls(); oc.set_override(name)
    cc = ControllerConfig(); cc.set_override(name)
    # Wall-clock cutoff is relaxed only for offline recording. No padded forecasts.
    if a.robot == 'spot_arm':
        import judo.utils.hierarchical_mj_rollout_backend as backend_module
        backend_module.DEFAULT_SPOT_ROLLOUT_CUTOFF_TIME = 60.
    initial_qpos = data.qpos.copy()
    controller = Controller(cc, task, cls(oc, task.nu),
        rollout_backend=get_registered_tasks()[name].rollout_backend,
        rollout_backend_registry={'mujoco_g1': G1RolloutBackend},
        rollout_backend_kwargs={'cutoff_time': 60.} if a.robot == 'g1' else None)
    # Controller.reset() resets its task again. Restore the requested scene's
    # observed initial state, with native joint posture, before any planning.
    data.qpos[:] = initial_qpos
    data.qvel[:] = 0.
    data.time = 0.
    mujoco.mj_forward(model, data)
    modules = [inspect.getfile(type(task).reward), inspect.getfile(Controller),
               inspect.getfile(cls), inspect.getfile(type(sim)), inspect.getfile(type(task).task_to_sim_ctrl)]
    hashes = {str(Path(x)): hashlib.sha256(Path(x).read_bytes()).hexdigest() for x in modules}
    protocol = dict(robot=a.robot, task=name, nativeController=True, seed=a.seed,
        controllerConfig=asdict(cc), optimizerConfig=asdict(oc), taskConfig=asdict(task.config),
        terminalCompatibility=terminal_compatibility, sourceSHA256=hashes,
        cartesianTracking=False, addedJointSmoothing=False, addedJitter=False,
        gainOverride=False, commandHoldOverride=False, nativeArmReset=True,
        actionDimension=task.nu, controlDt=float(task.dt), offlineRolloutCutoff=60.,
        layout='Shared task geometry and initial base placement' if a.source else 'Native stock reset',
        initialQpos=data.qpos.copy(), armJointAddresses=arm_addresses,
        note='Original CEM, costs, command mapping, policy and actuator settings. Native spline interpolation retained.')
    if a.scene_physics:
        protocol['scenePhysics'] = json.loads(a.scene_physics.read_text())
    dump(a.output/'protocol.json', protocol)
    mujoco.mj_saveModel(model, str(a.output/'task.mjb'))
    fields = ['geom_type', 'geom_size', 'geom_pos', 'geom_quat', 'geom_bodyid', 'geom_dataid',
              'geom_rgba', 'geom_matid', 'geom_group', 'mat_rgba', 'mesh_vert', 'mesh_face',
              'mesh_vertadr', 'mesh_vertnum', 'mesh_faceadr', 'mesh_facenum']
    np.savez_compressed(a.output/'geometry.npz', **{key: np.asarray(getattr(model, key)) for key in fields})
    times, qpos, qvel, positions, quaternions, eef, commands, command_times = [], [], [], [], [], [], [], []
    plan_times, rewards, candidates, forecast_eef = [], [], [], []
    initial_object = data.qpos[address:address+2].copy()
    sensor_names = ['trace_left_palm', 'trace_right_palm'] if a.robot == 'g1' else ['trace_fngr_site']
    sensor_adr = [int(model.sensor_adr[model.sensor(n).id]) for n in sensor_names]
    began = time.monotonic(); next_plan = next_record = next_progress = 0.
    success = failed = False
    while True:
        now = float(data.time)
        if now+1e-8 >= next_record or success or failed or now >= a.seconds-1e-8:
            times.append(now); qpos.append(data.qpos.copy()); qvel.append(data.qvel.copy())
            positions.append(data.xpos.copy()); quaternions.append(data.xquat.copy())
            eef.append(data.site_xpos[site_ids].copy()); next_record += .02
        if success or failed or now >= a.seconds-1e-8:
            break
        if now+1e-8 >= next_plan:
            controller.update_states(MujocoState(time=now, qpos=data.qpos.copy(), qvel=data.qvel.copy(),
                mocap_pos=data.mocap_pos.copy(), mocap_quat=data.mocap_quat.copy(), sim_metadata=task.get_sim_metadata()))
            controller.update_action()
            assert np.all(np.isfinite(controller.states)) and np.all(np.isfinite(controller.rewards))
            assert not np.any(np.all(controller.states[:, -1] == controller.states[:, -2], axis=1)), 'Padded forecast'
            plan_times.append(now); rewards.append(controller.rewards.copy())
            candidates.append(controller.candidate_knots.copy())
            forecast_eef.append(np.stack([controller.sensors[:, ::5, adr:adr+3] for adr in sensor_adr], axis=2))
            next_plan += 1/cc.control_freq
        if now+1e-8 >= next_progress:
            progress = dict(time=now, elapsedWallSeconds=time.monotonic()-began,
                displacement=float(np.linalg.norm(data.qpos[address:address+2]-initial_object)),
                goalError=float(np.linalg.norm(data.qpos[address:address+2]-task.config.goal_position[:2])))
            dump(a.output/'progress.json', progress)
            np.savez_compressed(a.output/'checkpoint.npz', time=times, qpos=qpos)
            print(name, json.dumps(progress), flush=True); next_progress += 2.
        action = controller.action(now)
        commands.append(action.copy()); command_times.append(now)
        sim.step(action)
        assert abs(float(data.time)-now-task.dt) < 1e-7
        controller.system_metadata = task.get_sim_metadata()
        success = bool(task.success(task.sim_model, data))
        failure = getattr(task, 'failure', None)
        failed = bool(failure(task.sim_model, data)) if failure else False
    np.savez_compressed(a.output/'states.npz', time=times, qpos=qpos, qvel=qvel,
        positions=positions, quaternions=quaternions, eef=eef)
    np.savez_compressed(a.output/'commands.npz', time=command_times, action=commands,
        planTime=plan_times, rewards=rewards, candidateKnots=candidates, forecastEEF=forecast_eef)
    fall_threshold = task.config.fall_threshold if a.robot == 'g1' else task.config.spot_fallen_threshold
    fall_frames = np.flatnonzero(np.asarray(qpos)[:, 2] <= fall_threshold)
    result = dict(task=name, robot=a.robot, nativeController=True, taskConfig=asdict(task.config),
        objectBodyId=int(target), gripperBodyId=body_ids[-1], eefBodyIds=body_ids, eefSites=sites,
        objectReference=reference, objectSize=size, duration=times[-1],
        moved=float(np.linalg.norm(data.qpos[address:address+2]-initial_object)),
        goalError=float(np.linalg.norm(data.qpos[address:address+2]-task.config.goal_position[:2])),
        controller='cem', pushReportedSuccess=success, fell=bool(len(fall_frames)),
        firstFallTime=float(times[fall_frames[0]]) if len(fall_frames) else None, sourceSeed=a.seed,
        interval=dict(start=0., end=times[-1]), scope=protocol['layout']+'. '+protocol['note'],
        terminalRule=f'Original native task success condition; otherwise {a.seconds:g} s recording limit.',
        protocol={k:v for k,v in protocol.items() if k not in ['sourceSHA256','initialQpos','terminalCompatibility']})
    if a.robot == 'spot_arm' and a.source:
        result['camera'] = dict(target=[6.05,6.,.5], position=[2.05,1.,3.9], fov=.75)
    dump(a.output/'result.json', result)
    print('COMPLETE', name, result['duration'], result['moved'], result['goalError'], success, flush=True)


if __name__ == '__main__':
    main()
