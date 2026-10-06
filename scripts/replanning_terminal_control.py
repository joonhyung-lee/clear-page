"""Geometric terminal fixes with unchanged physical success criteria.

This adapter is not a qualified upright motor. Failed braking and observation
experiments remain diagnostic evidence and are not enabled here.
"""
import numpy as np
from experiments.exp3.trajectory_v3.native_sumo import G1WholePathMPC, ContactUnavailable


class ContactDirectionTracker:
    """Keep the last reference tangent after all waypoints have been visited."""
    def __init__(self, tracker):
        self.tracker = tracker

    @property
    def done(self):
        return False

    def __getattr__(self, name):
        return getattr(self.tracker, name)


class UprightTerminalMPC(G1WholePathMPC):
    def observe(self):
        state = super().observe()
        self.contact_measurements[-1].update(
            object_speed_m_s=state['object_speed_m_s'],
            object_angular_speed_rad_s=state['object_angular_speed_rad_s'])
        return state

    def plan_object_path(self, path, tracker):
        reference = np.asarray(path.poses)
        direction = reference[-1, :2]-reference[-2, :2]
        direction /= np.linalg.norm(direction)
        remaining = (reference[-1, :2]-self.real.poses(self.oid)[0, :2]) @ direction
        if tracker.done and remaining < -.12:
            raise ContactUnavailable('terminal overshoot requires a new approach; forward pushing cannot recover it')
        # The original cost, target, waypoint index and success check remain.
        return super().plan_object_path(path, ContactDirectionTracker(tracker))

    def apply(self, commands):
        for command in commands:
            super().apply(np.asarray([command]))
            state = self.observe()
            pose, goal = np.asarray(state['object_pose']), np.asarray(self.path.goal)
            yaw_error = np.arctan2(np.sin(pose[2]-goal[2]), np.cos(pose[2]-goal[2]))
            if (np.linalg.norm(pose[:2]-goal[:2]) <= .08 and abs(yaw_error) <= .12
                    or state['collision'] or state['fell']):
                break

    def hold(self):
        # Let the unchanged executor observe settling every native tick.
        count = self.apply_steps
        try:
            self.apply_steps = 1
            super().hold()
        finally:
            self.apply_steps = count


def install():
    from experiments.exp3.trajectory_v3 import native_sumo_task
    native_sumo_task.G1WholePathMPC = UprightTerminalMPC
