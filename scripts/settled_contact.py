"""Measured palm acquisition for a low furniture surface.

The original acquisition permits 10 cm position error before tracking. During
the final approach, pause translation while either palm is too high or too low.
Require measured bilateral contact and tighter position error before releasing
the original MPC. This changes preparation only, not physics or success tests.
"""
import math
import numpy as np
import torch
from experiments.exp3.trajectory_v3.native_sumo import G1WholePathMPC, ContactUnavailable


class SettledContactMPC(G1WholePathMPC):
    def acquire_palms(self, path):
        rt = self.rt
        c = rt.contact_palm
        c.set_path(path.poses)
        self._refresh_contact(path.poses[1], allow_reposition=False)
        c.set_contact(self.oid, self.contacts[-1]['points'])
        original = rt.policy
        began = rt.steps * rt.dt
        observed_yaw = float(self.real.poses(self.oid)[0, 2])
        record = dict(stage='height_settled_palm_acquisition', start_s=began,
                      ready=False, timeout_s=20., samples=[],
                      align_contact_face=getattr(self, 'align_contact_face', False))
        self.posture_preparations.append(record)
        try:
            while rt.steps * rt.dt + rt.dt <= min(began + record['timeout_s'], self.deadline):
                c._update()
                actual = c.robot.data.site_pos_w[:, c.sites]
                error = c.target_position - actual
                norms = error.norm(dim=-1)
                state = self.observe()
                bilateral = set(self.contact_measurements[-1]['sides']) == {'left', 'right'}
                near = bool((error[0, :, :2].norm(dim=-1) < .07).all())
                settling = near and bool((error[0, :, 2].abs() > .03).any())
                record['samples'].append(dict(
                    time_s=rt.steps * rt.dt, error_m=norms[0].cpu().tolist(),
                    active_fraction=c.active_fraction[0].cpu().tolist(),
                    target_world=c.target_position[0].cpu().tolist(),
                    actual_world=actual[0].cpu().tolist(),
                    bilateral_contact=bilateral, settling_height=settling))
                if state['collision'] or state['fell']:
                    break
                if bilateral and bool((norms < .04).all()):
                    record['ready'] = True
                    return
                world = (1.2 * error.mean(1)[:, :2]).clamp(-.10, .10)
                if settling:
                    world.zero_()
                yaw = float(self.real.base()[0, 2])
                heading = math.atan2(float(c.direction[1]), float(c.direction[0])) - yaw
                if record['align_contact_face']:
                    # The observed pair belongs to a rigid object face. Rotate
                    # the approach heading with that face to keep both hands
                    # within reach after incidental object yaw during approach.
                    heading += float(self.real.poses(self.oid)[0, 2]) - observed_yaw
                heading = math.atan2(math.sin(heading), math.cos(heading))
                action = torch.zeros((rt.num_envs, 11), device=rt.device)
                twist = torch.stack((
                    math.cos(yaw) * world[:, 0] + math.sin(yaw) * world[:, 1],
                    -math.sin(yaw) * world[:, 0] + math.cos(yaw) * world[:, 1],
                    world.new_full((rt.num_envs,), float(np.clip(heading, -.2, .2)))), 1)
                action[:, :3] = torch.atanh((twist / c.term._twist_scale).clamp(-.999, .999))
                rt.policy = lambda observation, action=action: action
                rt.step(push=True)
                self.record()
        finally:
            rt.policy = original
            record['duration_s'] = rt.steps * rt.dt - began
        raise ContactUnavailable('measured bilateral palm acquisition did not settle')
