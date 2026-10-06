"""Check the proposed ramp through native reward and curriculum managers."""
from types import SimpleNamespace
import torch
from mjlab.managers import RewardManager, RewardTermCfg, CurriculumManager
from mjlab.tasks.velocity.config.g1.blind_stairs_env_cfg import action_rate_l2_clipped
from progressive_policy_rewards import configure

env = SimpleNamespace(num_envs=2, device='cpu', common_step_counter=0,
                      action_manager=SimpleNamespace(action=torch.ones(2, 12), prev_action=torch.zeros(2, 12)))
cfg = SimpleNamespace(rewards={'action_rate_l2': RewardTermCfg(func=action_rate_l2_clipped, weight=-.1)}, curriculum={})
configure(cfg, ramp_steps=100)
env.reward_manager = RewardManager(cfg.rewards, env)
manager = CurriculumManager(cfg.curriculum, env)
previous = 0.
for step, expected in [(0, -.01), (25, -.0325), (50, -.055), (100, -.1), (200, -.1)]:
    env.common_step_counter = step
    manager.compute(torch.arange(2))
    weight = env.reward_manager.get_term_cfg('action_rate_l2').weight
    assert abs(weight - expected) < 1e-12 and abs(weight) >= previous
    torch.testing.assert_close(env.reward_manager.compute(.02), torch.full((2,), 12 * expected * .02))
    extras = manager.reset(torch.arange(2))
    assert abs(extras['Curriculum/action_regularization/weight'] - expected) < 1e-12
    previous = abs(weight)
print('PASS native reward computation and logged curriculum ramp from10percent to the original weight')
