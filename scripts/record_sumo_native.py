"""Record SUMO's native G1 backend and CEM on an existing box scene.

Run in the pinned SUMO environment. Inputs are private CLI paths. The scene is
expressed in a rigid goal-centered frame; robot model, walker, reward, optimizer and
whole-body contact remain SUMO's. This is an adapted scene, not a stock task.
"""
import argparse
import json
import math
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation
import sumo.tasks
import sumo.controller
from sumo import MODEL_PATH
from sumo.tasks.g1.g1_table_push import G1TablePush
from sumo.tasks.g1.g1_box import G1Box
from sumo.app.dora.g1_simulation import SimBackendG1
from sumo.controller import Controller, ControllerConfig
from sumo.utils.mujoco import G1RolloutBackend
from judo.app.structs import MujocoState
from judo.optimizers.cem import CrossEntropyMethod, CrossEntropyMethodConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--seconds', type=float, default=40.)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--stock', action='store_true', help='Run the unmodified upstream G1 box scene and reset pose')
    parser.add_argument('--task', choices=['g1_table_push', 'g1_box'], default='g1_box')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.stock:
        assert args.task == 'g1_box'
        task = G1Box()
        initial_pose = task.reset_pose.copy()
        object_address = int(task.object_pose_idx[0])
        target_id = int(task.model.jnt_bodyid[task.model.joint('box_joint').id])
        size = (task.model.geom_size[task.model.geom('large_box_collision').id] * 2).tolist()
        floor = next(i for i in range(task.model.ngeom) if task.model.geom_type[i] == mujoco.mjtGeom.mjGEOM_PLANE)
        scene = dict(base_scene_id='sumo-original-box', world_size=[12.,12.], walls=[], terrain=[],
            floor_friction=float(task.model.geom_friction[floor,0]),
            start=[*initial_pose[:2],0.], goal=[*task.config.goal_position[:2],0.],
            objects=[dict(object_id=0,pose=[*initial_pose[object_address:object_address+2],0.],
                size=size,mass_kg=float(task.model.body_mass[target_id]),friction=.5)])
        ref = np.column_stack([np.linspace(initial_pose[object_address], task.config.goal_position[0], 8),
            np.linspace(initial_pose[object_address+1],task.config.goal_position[1],8), np.zeros(8)])
    else:
        archive = np.load(args.source / 'task.npz', allow_pickle=False)
        scene = json.loads(str(archive['scene']))
        ref = np.asarray(json.loads(str(archive['reference_paths']))[0]['poses'])
        direction = ref[-1, :2] - ref[0, :2]
        angle = math.atan2(direction[1], direction[0])
        rotation = Rotation.from_euler('z', -angle)
        matrix = rotation.as_matrix()[:2, :2]
        goal = ref[-1, :2].copy()
        def local(xy):
            return (np.asarray(xy) - goal) @ matrix.T
        ref[:, :2] = local(ref[:, :2])
        ref[:, 2] -= angle
        original_rollouts = np.load(args.source / 'task.rollouts.npz')
        k = np.argmin(abs(archive['time'] - original_rollouts['time_s'][0]))
        initial = archive['qpos'][k].astype(float).copy()
        initial[:2] = local(initial[:2])
        initial[3:7] = (rotation * Rotation.from_quat(initial[[4, 5, 6, 3]])).as_quat()[[3, 0, 1, 2]]
        # Native G1 uses the same named joint order. Save that contract for checking.
        tree = ET.parse(MODEL_PATH / 'xml/g1/g1.xml')
        root = tree.getroot()
        root.find('compiler').set('meshdir', str(MODEL_PATH / 'meshes/g1'))
        world = root.find('worldbody')
        floor = next((g for g in world.iter('geom') if g.get('type') == 'plane'), None)
        if floor is None: floor = ET.SubElement(world, 'geom', name='floor', type='plane', size='20 20 .1', rgba='.92 .93 .90 1')
        floor.set('friction', f'{scene["floor_friction"]} 0.005 0.0001')
        for i, bounds in enumerate(scene['walls']):
            corners = local(np.array([[bounds[0], bounds[1]], [bounds[2], bounds[1]], [bounds[2], bounds[3]], [bounds[0], bounds[3]]]))
            center = corners.mean(0)
            # Preserve orientation instead of expanding an oblique wall into its AABB.
            ET.SubElement(world, 'geom', name=f'wall_{i}', type='box', pos=f'{center[0]} {center[1]} .65', size=f'{(bounds[2]-bounds[0])/2} {(bounds[3]-bounds[1])/2} .65', euler=f'0 0 {-angle}', rgba='.65 .68 .66 1')
        object_states = []
        for obj in scene['objects']:
            oid = obj['object_id']; center = local(obj['pose'][:2]); yaw = obj['pose'][2] - angle
            body = ET.SubElement(world, 'body', name='table' if oid == 0 else f'object_{oid}', pos=f'{center[0]} {center[1]} {obj["size"][2]/2}', euler=f'0 0 {yaw}')
            ET.SubElement(body, 'freejoint', name=('box_joint' if args.task=='g1_box' else 'table_joint') if oid == 0 else f'object_{oid}_joint')
            ET.SubElement(body, 'geom', name=f'object_{oid}_box', type='box', size=' '.join(str(v/2) for v in obj['size']), mass=str(obj['mass_kg']), friction=f'{obj["friction"]} .005 .0001', rgba='.72 .78 .67 1')
            if oid == 0:
                ET.SubElement(body, 'site', name='trace_table', size='.01')
                ET.SubElement(body, 'site', name='site_table_object', size='.01')
            q = Rotation.from_euler('z', yaw).as_quat()[[3, 0, 1, 2]]
            object_states.extend([*center, obj['size'][2]/2, *q])
        camera_parent = next(b for b in root.iter('body') if b.get('name') == 'torso_link')
        camera_rotation = Rotation.from_matrix(np.array([[0., 0., -1.], [-1., 0., 0.], [0., 1., 0.]])).as_quat()[[3, 0, 1, 2]]
        ET.SubElement(camera_parent, 'camera', name='ego', pos='.14 0 .30', quat=' '.join(map(str, camera_rotation)), fovy='60')
        sensor = root.find('sensor')
        if sensor is None: sensor = ET.SubElement(root, 'sensor')
        for name, site in [('trace_pelvis', 'site_pelvis'), ('trace_table', 'trace_table'), ('trace_left_palm', 'left_palm'), ('trace_right_palm', 'right_palm')]:
            ET.SubElement(sensor, 'framepos', name=name, objtype='site', objname=site)
        ET.SubElement(sensor, 'frameyaxis', name='object_y_axis' if args.task=='g1_box' else 'table_y_axis', objtype='site', objname='site_table_object')
        xml = args.output / 'scene.xml'; tree.write(xml)
        initial_pose = np.r_[initial[:36], object_states]
        class BoxSceneTask(G1Box if args.task=='g1_box' else G1TablePush):
            @property
            def reset_pose(self):
                return initial_pose.copy()
        task = BoxSceneTask(model_path=str(xml))
        if args.task=='g1_box': task.config.goal_position=np.array([0.,0.,scene['objects'][0]['size'][2]/2])
    task.data.qpos[:] = initial_pose
    task.data.qvel[:] = 0
    mujoco.mj_forward(task.model, task.data)
    backend = SimBackendG1(task.task_to_sim_ctrl)
    np.random.seed(args.seed)
    cfg = CrossEntropyMethodConfig(num_rollouts=24, num_nodes=4, num_elites=2)
    cc = ControllerConfig(horizon=2.5, spline_order='cubic', control_freq=20.)
    controller = Controller(cc, task, CrossEntropyMethod(cfg, task.nu), rollout_backend='mujoco_g1', rollout_backend_registry={'mujoco_g1': G1RolloutBackend}, rollout_backend_kwargs={'cutoff_time': 60.})
    preview = G1RolloutBackend(task.model, 1, cutoff_time=60.)
    palm_ids = [task.model.site(name).id for name in ['left_palm', 'right_palm']]
    sensor_ids = [int(task.model.sensor_adr[task.model.sensor(name).id]) for name in ['trace_left_palm', 'trace_right_palm']]
    dt = task.dt; plan_steps = round(.05 / dt); record_steps = round(.02 / dt)
    future_times = np.r_[0., np.arange(.1, 2.50001, .1)]
    future_indices = np.round(future_times[1:] / dt).astype(int) - 1
    def paths(sensors):
        start = np.broadcast_to(task.data.site_xpos[palm_ids], (sensors.shape[0], 1, 2, 3))
        samples = np.stack([sensors[:, future_indices, adr:adr+3] for adr in sensor_ids], axis=2)
        return np.concatenate([start, samples], axis=1)
    rows = []; times = []; qpos = []; qvel = []; contacts = []; began = time.monotonic(); failed = False; reached = False
    initial_object = task.data.qpos[task.object_pose_idx[:2]].copy()
    target_body = task.model.body(int(task.model.jnt_bodyid[task.model.joint('box_joint' if args.task=='g1_box' else 'table_joint').id])).name
    for step in range(round(args.seconds / dt) + 1):
        now = step * dt
        if step % plan_steps == 0:
            controller.update_states(MujocoState(time=now, qpos=task.data.qpos.copy(), qvel=task.data.qvel.copy(), mocap_pos=task.data.mocap_pos.copy(), mocap_quat=task.data.mocap_quat.copy(), sim_metadata={}))
            controller.update_action()
            controls = controller.spline(now + controller.rollout_times)[None]
            states, sensors, _ = preview.rollout(controller.current_state, task.task_to_sim_ctrl(controls))
            preview_reward = task.reward(states, sensors, controls)
            # A complete future must not contain cutoff padding.
            assert not np.array_equal(states[0, -1], states[0, -2]), 'Native rollout cutoff reached'
            rows.append(dict(time_s=now, valid_until_s=now+.05, object_id=0,
                eef_world=np.concatenate([paths(controller.sensors), paths(sensors)]),
                elite_indices=np.argsort(controller.rewards)[-2:], applied_candidate=24,
                knots=np.concatenate([controller.candidate_knots, controller.nominal_knots[None]]),
                costs=-np.r_[controller.rewards, preview_reward]))
        if step % record_steps == 0:
            times.append(now); qpos.append(task.data.qpos.copy()); qvel.append(task.data.qvel.copy())
        if step % round(1/dt) == 0:
            position=task.data.qpos[task.object_pose_idx[:2]]
            print(f't={now:.1f} object={position.round(3).tolist()} moved={np.linalg.norm(position-initial_object):.3f} height={task.data.qpos[2]:.3f} wall={time.monotonic()-began:.1f}s',flush=True)
            np.savez_compressed(args.output/'checkpoint.npz',time=times,qpos=qpos)
        if step:
            failed = bool(task.failure(task.sim_model, task.data))
            reached = bool(task.success(task.sim_model, task.data)) if args.stock else np.linalg.norm(task.data.qpos[task.object_pose_idx[:2]]) < .08
            if failed or reached: break
        backend.sim(task.sim_model, task.data, controller.action(now))
        for c in task.data.contact:
            names=[task.model.body(int(task.model.geom_bodyid[g])).name for g in c.geom]
            if target_body in names and any(n not in ('world', target_body, 'terrain') and not n.startswith('object_') for n in names):
                contacts.append(dict(time_s=now,bodies=names,distance_m=float(c.dist)))
    if times[-1] < now-1e-8: times.append(now);qpos.append(task.data.qpos.copy());qvel.append(task.data.qvel.copy())
    meta=dict(version=4,executed=True,fixed_palms=False,contact_palms=False,selector='topk',step_s=.05,horizon_s=2.5,future_times=future_times.tolist(),coordinates='world metres',eef_sites=['left_palm','right_palm'],search_population=24,execution_preview_rows=1,executed_command='elite mean',runtime='SUMO native G1 C++ and Judo CEM',task=args.task,scope=('Unmodified upstream G1 box scene, reset, reward, arm settings and success condition. Native runtime with 24 candidates and complete offline rollouts.' if args.stock else f'SUMO {args.task} reward and native G1 dynamics adapted to the shared box scene in a goal-centered rigid coordinate frame. Population 24, complete offline rollouts, and whole-body target contact. Different runtime and action representation from the optimized controller. Not an isolated selector ablation.'),target_body=target_body,object_qposadr=int(task.object_pose_idx[0]),object_size=scene['objects'][0]['size'],ego_camera='ego',record_dt=.02,stock_scene=args.stock,arm_commands_enabled=bool(task.use_left_arm or task.use_right_arm))
    np.savez_compressed(args.output/'task.npz',time=times,qpos=qpos,qvel=qvel,reference_paths=json.dumps([dict(object_id=0,poses=ref.tolist())]),scene=json.dumps(scene))
    np.savez_compressed(args.output/'task.rollouts.npz',**{key:np.asarray([row[key] for row in rows]) for key in rows[0]},metadata=json.dumps(meta))
    mujoco.mj_saveModel(task.model,str(args.output/'task.mjb'))
    summary=dict(seed=args.seed,elapsed_s=now,fell=failed,goal_reached=bool(reached),displacement_m=float(np.linalg.norm(task.data.qpos[task.object_pose_idx[:2]]-initial_object)),goal_error_m=float(np.linalg.norm(task.data.qpos[task.object_pose_idx[:2]])),contacts=contacts,metadata=meta)
    (args.output/'result.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('COMPLETE', {k:v for k,v in summary.items() if k not in ('contacts','metadata')},flush=True)

if __name__ == '__main__': main()
