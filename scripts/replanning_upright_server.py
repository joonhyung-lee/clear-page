"""Explicit upright runtime variant of the pinned native physics server.

The planner still uses its trained controller-conditioning identity. This new
physical controller is recorded separately and is not a certified frozen run.
No recorded robot state is rewritten to create the new posture.
"""
from copy import deepcopy
import hashlib
import json
import numpy as np
from replanning_upright_profile import PROFILE, PROFILE_SHA256, upright_command
from experiments.exp4.sprint6h import physics_server as native
from replanning_terminal_control import install

install()


class UprightServer(native.Server):
    def init(self, controller, row, seed, device, worlds, out):
        original_hash = controller['controller_hash']
        controller = deepcopy(controller)
        controller['command'] = upright_command(controller['command'])
        profile = deepcopy(PROFILE)
        if row.get('diagnostic_guide_only', False):
            controller['command'].append('--guide-only')
            profile.update(diagnostic_guide_only=True, scope='Guide-only diagnosis, not the full MPC controller')
        profile_sha = hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()
        assert all(abs(o['size'][2]-PROFILE['box_height_m']) < 1e-8 for o in row['scene']['objects'])
        reply = super().init(controller, row, seed, device, worlds, out)
        b = self.backend
        assert b.real.rt.g1_low_contact_profile is None
        from clear.maze.fixed_palm import PALM_JOINTS
        assert np.allclose(b.real.rt.contact_palm.hold.cpu().numpy(), list(PALM_JOINTS.values()))
        b.mpc_kwargs['contact_height'] = PROFILE['contact_height_m']
        b.turn_budget_s = PROFILE['turn_budget_s']
        b.turn_min_rate = PROFILE['turn_min_rate']
        self.config.update(runtime_profile=profile, runtime_profile_sha256=profile_sha,
                           source_controller_hash=original_hash, controller_hash=profile_sha,
                           height_m=PROFILE['box_height_m'], low_contact_profile=None,
                           contact_height_m=PROFILE['contact_height_m'],
                           scope='Upright physical variant; frozen low-contact certification does not apply.')
        reply['config'] = json.loads(json.dumps(self.config, default=str))
        original_record = b._record
        robot = b.real.rt.env.scene['robot']
        joint_ids = [robot.joint_names.index(f'{side}_{joint}_joint')
                     for side in ['left', 'right'] for joint in ['knee', 'elbow']]
        last_progress = [-1.]

        def record_progress():
            original_record()
            if b.real.steps*b.real.dt-last_progress[0] >= 1.-1e-8:
                last_progress[0] = b.real.steps*b.real.dt
                payload = dict(time_s=float(b.real.steps*b.real.dt), unsafe=bool(b.unsafe),
                    root_z=float(robot.data.root_link_pos_w[0, 2]),
                    root_xyz=robot.data.root_link_pos_w[0].cpu().tolist(),
                    knee_elbow_rad=robot.data.joint_pos[0, joint_ids].cpu().tolist(),
                    palm_xyz=robot.data.site_pos_w[0, b.real.rt.contact_palm.sites].cpu().tolist(),
                    target=b.real.rt.target,
                    mode=b.real.rt.mode,
                    direction=b.real.rt.contact_palm.direction.cpu().tolist(),
                    object_poses={str(o['object_id']): b.real.poses(o['object_id'])[0].tolist() for o in row['scene']['objects']})
                (self.out/'upright-progress.json').write_text(json.dumps(payload, default=str)+'\n')
                with (self.out/'upright-progress.jsonl').open('a') as stream:
                    stream.write(json.dumps(payload, default=str)+'\n')
        b._record = record_progress
        return reply


native.Server = UprightServer
if __name__ == '__main__':
    native.main()
