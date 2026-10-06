"""Exercise the real wrapper on the captured runaway previous-action pattern."""
import argparse
from pathlib import Path
from types import SimpleNamespace
import torch
import mjlab.tasks
from mjlab.rl import RslRlVecEnvWrapper
from mjlab.tasks.registry import load_rl_cfg
from policy_action_contract import configure_action_limit, checkpoint_action_limit, applied_actions

parser = argparse.ArgumentParser()
parser.add_argument('--legacy', action='store_true', help='Reproduce the missing action limit before the fix')
parser.add_argument('--snapshot', type=Path, help='Optional saved failing transition, kept outside the repository')
args = parser.parse_args()
cfg = load_rl_cfg('Mjlab-Velocity-BlindStairs-Unitree-G1')
if not args.legacy:
    cfg = configure_action_limit(cfg, 5.)
sample = torch.linspace(-10744.2646484375, 10744.2646484375, 58).reshape(2, 29)
if args.snapshot:
    sample = torch.load(args.snapshot, map_location='cpu', weights_only=True)['actions']
count = len(sample)
original = sample.clone()

class Environment:
    cfg = SimpleNamespace(is_finite_horizon=False)
    unwrapped = property(lambda self: self)
    def step(self, actions):
        return ({'actor': torch.cat([torch.zeros(count, 67), actions, torch.zeros(count, 3)], -1)},
                torch.ones(count), torch.zeros(count, dtype=torch.bool), torch.zeros(count, dtype=torch.bool), {})

wrapped = RslRlVecEnvWrapper.__new__(RslRlVecEnvWrapper)
wrapped.env = Environment()
wrapped.num_envs = count
wrapped.clip_actions = cfg.clip_actions
observations, *_ = wrapped.step(sample)
history = observations['actor'][:, 67:96]
assert history.abs().max() <= 5, f'Runaway action re-entered observation: {history.abs().max().item()}'
assert torch.equal(sample, original), 'Do not modify PPO samples or their log-probability inputs in place'
limit = checkpoint_action_limit({'curriculum': {'action_limit': cfg.clip_actions}})
assert torch.equal(history, applied_actions(sample, limit)), 'Evaluation and training commands differ'
assert checkpoint_action_limit(None) is None, 'Preserve historical contracts'
assert applied_actions(sample, None) is sample
print('PASS applied action/history bound, unchanged PPO samples, and matched checkpoint replay contract')
