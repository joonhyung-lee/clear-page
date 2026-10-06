"""The actor, critic and reward must observe one torso target per episode."""
from types import SimpleNamespace
import torch
from mjlab.tasks.velocity.config.spot import spot_mdp
from progressive_policy_mdp import configure_command_consistency

torch.manual_seed(42)
cfg = configure_command_consistency(SimpleNamespace(events={}))
env = SimpleNamespace(num_envs=2, device='cpu', reset_buf=torch.tensor([True, True]))
first = spot_mdp._torso_command(env).clone()
second = spot_mdp._torso_command(env).clone()
assert torch.equal(first, second), f'Torso command changes between consumers at the same reset: {first.tolist()} versus {second.tolist()}'
event = cfg.events['reset_torso_command']
event.func(env, torch.tensor([1]))
new = spot_mdp._torso_command(env).clone()
assert torch.equal(new[0], first[0]), 'Resetting env 1 must preserve env 0'
assert not torch.equal(new[1], first[1]), 'An actual reset must sample a new command'
for _ in range(5):
    assert torch.equal(spot_mdp._torso_command(env), new), 'Reward/actor/critic reads must be idempotent'
print('PASS stable torso target across consumers, resampled exactly at sparse environment reset')
