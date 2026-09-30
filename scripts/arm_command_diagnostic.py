"""Explicit command-rate diagnostic shared by actual and forecast controllers."""
import numpy as np


def install_sample_hold(controller_class, frequency):
    original_command = controller_class.command
    original_copy = controller_class.copy_from

    def command(self, residual):
        result = original_command(self, residual)
        remaining = getattr(self, '_diagnostic_arm_remaining', 0.)
        if remaining <= 1e-9 or not hasattr(self, '_diagnostic_arm_target'):
            self._diagnostic_arm_target = self.rt.arm_override.copy()
            remaining += 1. / frequency
        self.rt.arm_override = self._diagnostic_arm_target.copy()
        self._diagnostic_arm_remaining = remaining - self.rt.dt
        return result

    def copy_from(self, source):
        original_copy(self, source)
        self._diagnostic_arm_remaining = getattr(source, '_diagnostic_arm_remaining', 0.)
        if hasattr(source, '_diagnostic_arm_target'):
            self._diagnostic_arm_target = np.repeat(source._diagnostic_arm_target[:1], self.rt.num_envs, axis=0)
        elif hasattr(self, '_diagnostic_arm_target'):
            del self._diagnostic_arm_target

    controller_class.command = command
    controller_class.copy_from = copy_from
