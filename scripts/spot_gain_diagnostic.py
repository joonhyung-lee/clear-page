"""Isolated arm PD stiffness experiment, shared by real and rollout worlds."""
from copy import deepcopy
import math

ARM_JOINTS=('arm_sh0','arm_sh1','arm_el0','arm_el1','arm_wr0','arm_wr1')


def scale_arm_config(config,scale):
    if not math.isfinite(scale) or scale<=1:
        raise ValueError('Arm P gain scale must be finite and greater than one')
    config=deepcopy(config)
    matched=[];entries=[]
    for actuator in config.articulation.actuators:
        names=tuple(actuator.target_names_expr)
        if not set(names)&set(ARM_JOINTS):continue
        if not set(names)<=set(ARM_JOINTS):raise ValueError('Mixed arm/non-arm actuator group')
        original=float(actuator.stiffness)
        actuator.stiffness=original*scale
        for name in names:
            matched.append(name)
            entries.append(dict(joint=name,originalKp=original,kp=float(actuator.stiffness),
                                kd=float(actuator.damping),effortLimit=float(actuator.effort_limit)))
    if sorted(matched)!=sorted(ARM_JOINTS):raise ValueError('Expected exactly six arm joints')
    return config,dict(scale=float(scale),actuators=entries)


def install_arm_gain_diagnostic(scale):
    import numpy as np
    from mjlab.asset_zoo.robots.boston_dynamics_spot import spot_constants
    from clear.maze.mjlab_runtime import NativeRuntime
    original_factory=spot_constants.get_spot_robot_cfg
    _,metadata=scale_arm_config(original_factory(),scale)
    checked_worlds=[]

    def factory(*args,**kwargs):
        return scale_arm_config(original_factory(*args,**kwargs),scale)[0]

    original_init=NativeRuntime.__init__
    def initialize(self,*args,**kwargs):
        original_init(self,*args,**kwargs)
        if self.body!='spot_arm':return
        for entry in metadata['actuators']:
            idx=self.model.actuator('robot/'+entry['joint']).id
            assert np.isclose(self.model.actuator_gainprm[idx,0],entry['kp'])
            assert np.isclose(self.model.actuator_biasprm[idx,1],-entry['kp'])
            assert np.isclose(self.model.actuator_biasprm[idx,2],-entry['kd'])
            assert np.allclose(self.model.actuator_forcerange[idx],[-entry['effortLimit'],entry['effortLimit']])
            assert not self.model.actuator_ctrllimited[idx], 'Stiffness-derived informational ranges must not clip targets'
        checked_worlds.append(self.num_envs)
        print(f'PROGRESS verified arm Kp x{scale:g}, Kd and torque limits unchanged in {self.num_envs} physical worlds',flush=True)

    spot_constants.get_spot_robot_cfg=factory
    NativeRuntime.__init__=initialize
    return metadata,checked_worlds
