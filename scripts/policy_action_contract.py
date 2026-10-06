"""Persist the applied action limit so training and replay use the same inputs."""
import math


def validate_limit(limit):
    if limit is not None and (not math.isfinite(limit) or limit <= 0):
        raise ValueError('Action limit must be finite and positive')
    return limit


def configure_action_limit(rl, limit):
    if limit is not None:
        rl.clip_actions = validate_limit(limit)
    return rl


def checkpoint_action_limit(infos, fallback=None):
    return validate_limit((infos or {}).get('curriculum', {}).get('action_limit', fallback))


def applied_actions(actions, limit):
    return actions if limit is None else actions.clamp(-limit, limit)
