"""An explicit, logged action-regularization curriculum for diagnostic training."""


def configure_failure_cost(cfg, cost):
    """Add one finite cost for a non-timeout termination, independent of dt."""
    if cost is None:
        return cfg
    import math
    from mjlab.envs.mdp import is_terminated
    from mjlab.managers import RewardTermCfg
    if not math.isfinite(cost) or cost <= 0:
        raise ValueError('Failure cost must be finite and positive')
    scale = cfg.sim.mujoco.timestep * cfg.decimation if cfg.scale_rewards_by_dt else 1.
    cfg.rewards['failure'] = RewardTermCfg(func=is_terminated, weight=-cost / scale)
    return cfg


def action_regularization(env, env_ids, target_weight, ramp_steps, initial_fraction=.1):
    del env_ids
    progress = min(1., max(0., env.common_step_counter / ramp_steps))
    weight = target_weight * (initial_fraction + (1. - initial_fraction) * progress)
    env.reward_manager.get_term_cfg('action_rate_l2').weight = weight
    return {'weight': weight, 'progress': progress}


def configure(cfg, ramp_steps, initial_fraction=.1):
    from dataclasses import replace
    from mjlab.managers import CurriculumTermCfg
    if ramp_steps <= 0 or not 0 < initial_fraction <= 1:
        raise ValueError('Use a positive ramp duration and an initial fraction in (0, 1]')
    target = cfg.rewards['action_rate_l2'].weight
    cfg.rewards['action_rate_l2'] = replace(cfg.rewards['action_rate_l2'], weight=target * initial_fraction)
    cfg.curriculum['action_regularization'] = CurriculumTermCfg(func=action_regularization,
        params={'target_weight': target, 'ramp_steps': ramp_steps, 'initial_fraction': initial_fraction})
    return cfg
