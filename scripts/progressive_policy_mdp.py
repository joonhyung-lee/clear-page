"""Training adapters for consistent per-episode Spot commands."""


def stable_torso_command(env):
    import torch
    from mjlab.tasks.velocity.config.spot import spot_mdp
    buffer = spot_mdp._TORSO_CACHE.get(id(env))
    if buffer is None or buffer.shape[0] != env.num_envs:
        buffer = torch.zeros((env.num_envs, 3), device=env.device)
        spot_mdp._TORSO_CACHE[id(env)] = buffer
        spot_mdp._resample_torso(env, buffer, slice(None))
    return buffer


def reset_torso_command(env, env_ids):
    from mjlab.tasks.velocity.config.spot import spot_mdp
    buffer = stable_torso_command(env)
    spot_mdp._resample_torso(env, buffer, slice(None) if env_ids is None else env_ids)


def configure_command_consistency(cfg):
    from mjlab.managers import EventTermCfg
    from mjlab.tasks.velocity.config.spot import spot_mdp
    # Reading a command must not mutate it. The upstream implementation used
    # reset_buf as a trigger on every consumer call, re-sampling multiple times
    # within one simulation step. Resample at the actual reset event instead.
    spot_mdp._torso_command = stable_torso_command
    cfg.events['reset_torso_command'] = EventTermCfg(func=reset_torso_command, mode='reset')
    return cfg


def configure_forward_locomotion(cfg):
    """Private curriculum experiment: learn straight walking before terrain.

    Only the first training stage calls this adapter. Later stages restore the
    native multidirectional command distribution and inherit the learned state.
    Physics, rewards and evaluation queries remain unchanged.
    """
    command = cfg.commands['twist']
    command.heading_command = False
    command.ranges.heading = None
    command.rel_heading_envs = command.rel_standing_envs = 0.
    command.rel_world_envs = command.rel_forward_envs = 0.
    command.init_velocity_prob = 0.
    command.ranges.lin_vel_x = (.3, .6)
    command.ranges.lin_vel_y = (0., 0.)
    command.ranges.ang_vel_z = (0., 0.)
    # This native callback overwrites ranges at reset, including update zero.
    cfg.curriculum.pop('command_vel', None)
    return cfg
