"""Explicit command-rate diagnostic shared by actual and forecast controllers."""
import numpy as np


def install_sample_hold(controller_class, frequency=None, *, intervals=None, hold_base=False):
    if intervals is None:
        if frequency is None or not np.isfinite(frequency) or frequency <= 0:
            raise ValueError('A positive command frequency is required')
        intervals = (1. / frequency,)
    intervals = tuple(float(x) for x in intervals)
    if not intervals or any(not np.isfinite(x) or x <= 0 for x in intervals):
        raise ValueError('Command hold intervals must be finite and positive')
    original_command = controller_class.command
    original_copy = controller_class.copy_from

    def command(self, residual):
        result = original_command(self, residual)
        remaining = getattr(self, '_diagnostic_arm_remaining', 0.)
        if remaining <= 1e-9 or not hasattr(self, '_diagnostic_arm_target'):
            self._diagnostic_arm_target = self.rt.arm_override.copy()
            slot = getattr(self, '_diagnostic_interval_index', 0)
            remaining += intervals[slot % len(intervals)]
            self._diagnostic_interval_index = slot + 1
            if hold_base:
                self._diagnostic_base_target = np.array(result, copy=True)
        self.rt.arm_override = self._diagnostic_arm_target.copy()
        self._diagnostic_arm_remaining = remaining - self.rt.dt
        return self._diagnostic_base_target.copy() if hold_base else result

    def copy_from(self, source):
        original_copy(self, source)
        self._diagnostic_arm_remaining = getattr(source, '_diagnostic_arm_remaining', 0.)
        self._diagnostic_interval_index = getattr(source, '_diagnostic_interval_index', 0)
        if hasattr(source, '_diagnostic_arm_target'):
            self._diagnostic_arm_target = np.repeat(source._diagnostic_arm_target[:1], self.rt.num_envs, axis=0)
        elif hasattr(self, '_diagnostic_arm_target'):
            del self._diagnostic_arm_target
        if hold_base and hasattr(source, '_diagnostic_base_target'):
            self._diagnostic_base_target = np.repeat(source._diagnostic_base_target[:1], self.rt.num_envs, axis=0)
        elif hasattr(self, '_diagnostic_base_target'):
            del self._diagnostic_base_target

    controller_class.command = command
    controller_class.copy_from = copy_from
