"""Arm gravity support independent of the deprecated crouch implementation."""
import torch


def install_arm_gravity_support(rt):
    if getattr(rt, '_upright_arm_gravity_support', False):
        return
    c = rt.contact_palm
    names = list(c.robot.joint_names)
    actuators = [rt.model.actuator('robot/'+names[j]).id for j in c.ids]
    gains = c.goal.new_tensor(rt.model.actuator_gainprm[actuators, 0])
    if not bool((gains > 0).all()):
        raise ValueError('Positive native arm PD stiffness is required')
    original = c.term._run_low_level

    @torch.inference_mode()
    def targets():
        result = original()
        # Gravity/Coriolis feedforward through the native position actuators.
        # Do not alter leg targets, motor observations, gains or physical state.
        result[:, c.ids] = (result[:, c.ids] + rt.env.sim.data.qfrc_bias[:, c.dofs]/gains).clamp(
            c.limits[:, :, 0], c.limits[:, :, 1])
        return result

    c.term._run_low_level = targets
    rt._upright_arm_gravity_support = True
