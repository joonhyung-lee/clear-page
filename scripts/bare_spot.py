"""Independent, arm-free Spot physics and 48-input locomotion policy contract.

The original task named Spot actually contains an arm. Remove the entire arm
subtree, its inertia, collisions, sensors and actuators before compiling physics.
This contract requires training from scratch; 84-input armed policies cannot load.
"""
from dataclasses import replace


def get_spec():
    from mjlab.asset_zoo.robots.boston_dynamics_spot import spot_constants as c
    spec = c.get_spec()
    for sensor in list(spec.sensors):
        if 'arm' in sensor.objname or sensor.name == 'trace_fngr_site':
            spec.delete(sensor)
    for pair in list(spec.excludes):
        if 'arm' in pair.bodyname1 or 'arm' in pair.bodyname2:
            spec.delete(pair)
    spec.delete(spec.body('arm_link_sh0'))
    return spec


def configure(cfg):
    from mjlab.asset_zoo.robots.boston_dynamics_spot import spot_constants as c
    from mjlab.envs import mdp
    from mjlab.envs.mdp.actions import JointPositionActionCfg
    from mjlab.managers.observation_manager import ObservationTermCfg
    robot = cfg.scene.entities['robot']
    robot.spec_fn = get_spec
    robot.init_state = replace(robot.init_state, joint_pos={k: v for k, v in
        robot.init_state.joint_pos.items() if not k.startswith('arm_')})
    robot.articulation = replace(robot.articulation, actuators=robot.articulation.actuators[:2])
    cfg.actions = {'joint_pos': JointPositionActionCfg(entity_name='robot',
        actuator_names=(".*",), scale=.2, use_default_offset=True)}
    terms = {
        'base_lin_vel': ObservationTermCfg(func=mdp.base_lin_vel),
        'base_ang_vel': ObservationTermCfg(func=mdp.base_ang_vel),
        'projected_gravity': ObservationTermCfg(func=mdp.projected_gravity),
        'command': ObservationTermCfg(func=mdp.generated_commands, params={'command_name': 'twist'}),
        'joint_pos': ObservationTermCfg(func=mdp.joint_pos_rel),
        'joint_vel': ObservationTermCfg(func=mdp.joint_vel_rel),
        'actions': ObservationTermCfg(func=mdp.last_action),
    }
    cfg.observations = {key: replace(group, terms={name: replace(term, clip=(-100., 100.))
        for name, term in terms.items()}) for key, group in cfg.observations.items()}
    for name in ('track_arm', 'track_torso'):
        cfg.rewards.pop(name, None)
    cfg.curriculum.pop('arm_stow', None)
    for name in ('std_walking', 'std_running'):
        cfg.rewards['pose'].params[name].pop(r'arm_.*', None)
    return cfg


def verify_model(model):
    """Fail before training/export if any arm physics survives the adapter."""
    import mujoco
    names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i) or ''
             for i in range(model.njnt)]
    assert not any('arm' in name for name in names), names
    assert model.nu == 12, model.nu
    assert model.nq == 19 and model.nv == 18, (model.nq, model.nv)
    return {'body': 'spot', 'armJoints': 0, 'actuators': 12,
            'observations': 48, 'physics': 'arm-free'}
