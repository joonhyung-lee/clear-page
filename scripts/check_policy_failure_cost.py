"""Verify actual reward-manager termination costs and a captured early-fall case."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import torch
from mjlab.managers import RewardManager, RewardTermCfg
from progressive_policy_rewards import configure_failure_cost

parser = argparse.ArgumentParser()
parser.add_argument('--legacy', action='store_true')
parser.add_argument('--evidence', type=Path)
args = parser.parse_args()


def zero_reward(env):
    return torch.zeros(env.num_envs)


for dt in [.005, .02, .04]:
    for scale_by_dt in [True, False]:
        cfg = SimpleNamespace(sim=SimpleNamespace(mujoco=SimpleNamespace(timestep=dt)),
                              decimation=1, scale_rewards_by_dt=scale_by_dt,
                              rewards={'zero': RewardTermCfg(func=zero_reward, weight=1.)})
        env = SimpleNamespace(num_envs=3, device='cpu', termination_manager=SimpleNamespace(
            terminated=torch.tensor([False, True, False]), time_outs=torch.tensor([False, False, True])))
        if not args.legacy:
            configure_failure_cost(cfg, 20.)
        manager = RewardManager(cfg.rewards, env, scale_by_dt=scale_by_dt)
        actual = manager.compute(dt)
        torch.testing.assert_close(actual, torch.tensor([0., -20., 0.]))
        applied_cost = -float(actual[1])
print('PASS native reward manager: only failure costs20, timeout/alive cost0, independent of dt scaling')

if args.evidence:
    records = json.loads(args.evidence.read_text())['checkpoints']
    initial, later = records[0]['episodes'], records[-1]['episodes']
    assert len(initial) == len(later) == 20
    for start, short in zip(initial, later):
        assert start['initialStateHash'] == short['initialStateHash']
        assert start['fall'] and short['fall'] and start['duration'] > short['duration']
        assert short['discountedReturn'] > start['discountedReturn'], 'Captured incentive must reproduce'
        def corrected(episode):
            terminal_discount = episode['gamma'] ** (round(episode['duration'] / .02) - 1)
            return episode['discountedReturn'] - applied_cost * terminal_discount
        assert corrected(start) > corrected(short)
    print('PASS all20 captured stochastic episodes: native prefers earlyfall; measured terminal cost reverses that preference')
