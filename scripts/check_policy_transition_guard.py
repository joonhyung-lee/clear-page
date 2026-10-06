"""Reproduce corrupt transitions without changing valid measured data."""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import torch
from policy_training_health import attach_transition_guard


def check(bad=None):
    obs = {'actor': torch.ones(2, 99)}
    reward = torch.tensor([1., -2.])
    qvel = torch.zeros(2, 35)
    result = (obs, reward, torch.zeros(2), {})
    env = SimpleNamespace(unwrapped=SimpleNamespace(sim=SimpleNamespace(data=SimpleNamespace(qvel=qvel))), step=lambda _: result)
    if bad == 'reward':
        reward[1] = -2396993024.
    elif bad == 'observation':
        obs['actor'][1, 0] = 18853484560384.
    elif bad == 'physics':
        qvel[1, 0] = float('nan')
    elif bad == 'physics_proxy':
        import warp as wp
        from mjlab.sim.sim_data import TorchArray
        wp.init()
        qvel[1, 0] = float('nan')
        env.unwrapped.sim.data.qvel = TorchArray(wp.from_torch(qvel))
    with tempfile.TemporaryDirectory() as folder:
        attach_transition_guard(env, folder)
        try:
            actual = env.step(torch.zeros(2, 29))
        except FloatingPointError:
            assert bad
            failure = json.loads(Path(folder, 'failure.json').read_text())
            assert failure['trainingStopped'] and failure['environmentStep'] == 1
            snapshot = torch.load(Path(folder, 'invalid-transition.pt'), weights_only=True)
            if bad == 'reward':
                assert snapshot['reward'][1] == reward[1], 'Preserve the original excursion'
        else:
            assert bad is None, 'Corrupt transition reached the caller'
            assert actual is result and torch.equal(actual[1], torch.tensor([1., -2.]))
    print('PASS', bad or 'unchanged valid transition')


for case in [None, 'reward', 'observation', 'physics', 'physics_proxy']:
    check(case)
