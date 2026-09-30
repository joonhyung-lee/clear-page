"""Check command timing and cloned forecast memory before a physical trial."""
from types import SimpleNamespace
import numpy as np
from arm_command_diagnostic import install_sample_hold


class Tracker:
    def __init__(self, worlds=1):
        self.rt = SimpleNamespace(dt=.02, num_envs=worlds)
        self.tick = 0

    def command(self, residual):
        self.rt.arm_override = np.full((self.rt.num_envs, 7), self.tick, dtype=float)
        self.tick += 1
        return 'unchanged base command'

    def copy_from(self, source):
        self.tick = source.tick


install_sample_hold(Tracker, 4.)
actual = Tracker()
values = []
for _ in range(50):
    assert actual.command(None) == 'unchanged base command'
    values.append(actual.rt.arm_override[0, 0])
assert sorted(set(values)) == [0., 13., 25., 38.], values
actual = Tracker()
for _ in range(10):
    actual.command(None)
forecast = Tracker(16)
forecast.copy_from(actual)
for _ in range(30):
    actual.command(None)
    forecast.command(None)
    assert np.all(forecast.rt.arm_override == actual.rt.arm_override)
assert not np.shares_memory(actual._diagnostic_arm_target, forecast._diagnostic_arm_target)
print('PASS 4 Hz command timing at a 50 Hz physics-control step, unchanged base commands and identical forecast sample-and-hold memory')
