"""Stop corrupt simulator transitions before they enter PPO rollout storage.

The limits are diagnostic tripwires, not reward/observation clipping. A failing
transition is saved verbatim and the run fails. Nothing is silently repaired,
dropped from a continuing run, or published as successful training.
"""
import json
from pathlib import Path
import torch


def attach_transition_guard(wrapped, output, observation_limit=1e4, reward_limit=1e4):
    output = Path(output)
    step = wrapped.step
    counter = 0

    def checked_step(actions):
        nonlocal counter
        counter += 1
        result = step(actions)
        observations, rewards, dones, extras = result
        tensors = {f'observation/{key}': value for key, value in observations.items()}
        tensors['reward'] = rewards
        tensors['policy/sample'] = actions
        sim_data = getattr(getattr(wrapped.unwrapped, 'sim', None), 'data', None)
        for name in ['qpos', 'qvel']:
            value = getattr(sim_data, name, None)
            # MuJoCo-Warp exposes TorchArray proxies, not Tensor subclasses.
            # detach() returns their shared backing tensor without a copy.
            if value is not None and callable(getattr(value, 'detach', None)):
                value = value.detach()
            if isinstance(value, torch.Tensor):
                tensors[f'physics/{name}'] = value
        reasons = []
        for name, value in tensors.items():
            if not torch.isfinite(value).all():
                reasons.append(f'{name}: nonfinite tensor')
            limit = reward_limit if name == 'reward' else observation_limit if name.startswith('observation/') else None
            if limit is not None and torch.any(value.abs() > limit):
                reasons.append(f'{name}: diagnostic magnitude limit {limit} exceeded')
        if reasons:
            output.mkdir(parents=True, exist_ok=True)
            torch.save({**{name: value.detach().cpu().clone() for name, value in tensors.items()},
                        'actions': actions.detach().cpu().clone(), 'dones': dones.detach().cpu().clone()},
                       output / 'invalid-transition.pt')
            (output / 'failure.json').write_text(json.dumps({'environmentStep': counter,
                'reasons': reasons, 'observationLimit': observation_limit, 'rewardLimit': reward_limit,
                'trainingStopped': True}, indent=2) + '\n')
            raise FloatingPointError('; '.join(reasons))
        return result

    wrapped.step = checked_step
