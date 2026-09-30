"""Transfer a rigid SUMO object into a CLEAR runtime without changing its shape.

Only the object coordinate origin changes to match the controller's center-height
convention. Visual and collision geometry, mass, inertia, and contact parameters
are preserved. Articulated objects require a separate controller adapter.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from replay_geometry import mesh


class RigidTaskObject:
    def __init__(self, folder):
        folder = Path(folder)
        self.physics = SimpleNamespace(**dict(np.load(folder/'physics.npz')))
        self.result = json.loads((folder/'result.json').read_text())
        self.body = int(self.result['targetBody'])
        p, body = self.physics, self.body
        joints = p.jnt_type[p.body_jntadr[body]:p.body_jntadr[body]+p.body_jntnum[body]]
        if len(joints) != 1 or joints[0] != int(mujoco.mjtJoint.mjJNT_FREE):
            raise ValueError('This object is articulated. A free-object controller cannot represent its joint.')
        if np.any(p.body_parentid == body):
            raise ValueError('Rigid transfer requires all target geometry on the same body')
        self.geoms = np.flatnonzero(p.geom_bodyid == body)
        vertices = []
        for i in self.geoms:
            shape = mesh(p, i)
            vertices.append(Rotation.from_quat(p.geom_quat[i], scalar_first=True).apply(shape.vertices)+p.geom_pos[i])
        points = np.concatenate(vertices)
        low, high = points.min(0), points.max(0)
        self.size = np.array([2*np.abs(points[:, 0]).max(), 2*np.abs(points[:, 1]).max(), high[2]-low[2]])
        # CLEAR subtracts size[2]/2 when converting observed contact points into
        # object coordinates. Use that same origin, including for source meshes
        # whose lowest vertex lies slightly below their body origin.
        self.center = np.array([0., 0., self.size[2]/2])
        self.source_low = low
        with np.load(folder/'states.npz') as states:
            self.initial_position = states['positions'][0, body].copy()
            self.initial_quaternion = states['quaternions'][0, body].copy()
            self.initial_robot = states['qpos'][0, :7].copy()

    def spec(self, position, quaternion=(1., 0., 0., 0.)):
        p, source_body = self.physics, self.body
        spec = mujoco.MjSpec()
        body = spec.worldbody.add_body(name='box', pos=position, quat=quaternion,
            mass=float(p.body_mass[source_body]), ipos=p.body_ipos[source_body]-self.center,
            iquat=p.body_iquat[source_body], inertia=p.body_inertia[source_body], explicitinertial=True)
        body.add_freejoint(name='object_free')
        for index, i in enumerate(self.geoms):
            mesh_name = ''
            if p.geom_type[i] == int(mujoco.mjtGeom.mjGEOM_MESH):
                source_mesh = int(p.geom_dataid[i])
                v, nv = p.mesh_vertadr[source_mesh], p.mesh_vertnum[source_mesh]
                f, nf = p.mesh_faceadr[source_mesh], p.mesh_facenum[source_mesh]
                mesh_name = f'shape_{index}'
                spec.add_mesh(name=mesh_name, uservert=p.mesh_vert[v:v+nv].reshape(-1),
                              userface=p.mesh_face[f:f+nf].reshape(-1))
            color = p.geom_rgba[i] if p.geom_matid[i] < 0 else p.mat_rgba[p.geom_matid[i]]
            body.add_geom(name=f'surface_{index}', type=mujoco.mjtGeom(int(p.geom_type[i])),
                size=p.geom_size[i], pos=p.geom_pos[i]-self.center, quat=p.geom_quat[i],
                rgba=color, group=int(p.geom_group[i]), meshname=mesh_name,
                contype=int(p.geom_contype[i]), conaffinity=int(p.geom_conaffinity[i]),
                condim=int(p.geom_condim[i]), friction=p.geom_friction[i], solmix=float(p.geom_solmix[i]),
                solref=p.geom_solref[i], solimp=p.geom_solimp[i], margin=float(p.geom_margin[i]),
                gap=float(p.geom_gap[i]), priority=int(p.geom_priority[i]))
        return spec

    def verify(self, model=None, data=None, prefix='', translation=None):
        """Check the compiled model, including mesh compiler transforms."""
        p, body = self.physics, self.body
        standalone = model is None
        if standalone:
            model = self.spec(self.center).compile()
            data = mujoco.MjData(model)
            mujoco.mj_forward(model, data)
        transferred = model.body(prefix+'box').id
        np.testing.assert_allclose(model.body_mass[transferred], p.body_mass[body], atol=1e-9)
        np.testing.assert_allclose(model.body_inertia[transferred], p.body_inertia[body], atol=1e-9)
        np.testing.assert_allclose(model.body_ipos[transferred]+self.center, p.body_ipos[body], atol=1e-9)
        np.testing.assert_allclose(model.body_iquat[transferred], p.body_iquat[body], atol=1e-9)
        errors = []
        for index, original in enumerate(self.geoms):
            i = model.geom(f'{prefix}surface_{index}').id
            source = mesh(p, original)
            target = mesh(model, i)
            source_points = Rotation.from_quat(p.geom_quat[original], scalar_first=True).apply(source.vertices)+p.geom_pos[original]
            if not standalone:
                source_points = Rotation.from_quat(self.initial_quaternion, scalar_first=True).apply(source_points)
                source_points += self.initial_position+np.asarray(translation)
            target_points = target.vertices @ data.geom_xmat[i].reshape(3, 3).T + data.geom_xpos[i]
            np.testing.assert_allclose(source_points, target_points, atol=2e-6)
            np.testing.assert_array_equal(source.faces, target.faces)
            for field in ['geom_friction', 'geom_solref', 'geom_solimp', 'geom_margin', 'geom_gap',
                          'geom_contype', 'geom_conaffinity', 'geom_condim', 'geom_solmix', 'geom_priority']:
                np.testing.assert_array_equal(getattr(p, field)[original], getattr(model, field)[i])
            errors.append(float(np.abs(source_points-target_points).max()))
        return dict(geometries=len(self.geoms), max_vertex_error_m=max(errors),
                    mass_kg=float(model.body_mass[transferred]), center_offset=self.center.tolist())


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    print(json.dumps(RigidTaskObject(args.folder).verify(), indent=2))
