"""Shared physical settings for the upright-palm replanning recordings."""
import hashlib
import json

PROFILE = dict(
    name='upright-bilateral-palms-terminal-development',
    box_height_m=1.2,
    contact_height_m=1.0,
    arm_reference='clear.maze.fixed_palm.PALM_JOINTS',
    motor='original SUMO flat G1',
    low_contact_profile=False,
    crouch_offsets=False,
    palm_gain=1.0,
    turn_budget_s=30.,
    turn_min_rate=.4,
    terminal_contact_direction='last reference tangent',
    terminal_observation_s=.1,
    goal_position_tolerance_m=.08,
    goal_yaw_tolerance_rad=.12,
    settling_contact='original withdrawal, observed every native tick',
    terminal_overshoot_stop_m=.12,
    walker_arm_observation='relative to commanded upright arm pose',
    arm_gravity_support=False,
    qualification='unqualified; motor stopping and reverse tracking failed',
)
PROFILE_SHA256 = hashlib.sha256(json.dumps(PROFILE, sort_keys=True).encode()).hexdigest()


def upright_command(command):
    """Keep the Cartesian/MPC settings, remove the crouched motor and posture."""
    removed = {'--low-profile', '--symmetric-reference', '--reach-contract',
               '--dynamic-arm-observation-reference', '--no-crouch', '--upright-motor'}
    removed_values = {'--native-arm-stiffness-scale', '--native-arm-damping-scale', '--height', '--palm-gain'}
    result = []
    i = 0
    while i < len(command):
        if command[i] in removed_values:
            i += 2
        elif command[i] in removed:
            i += 1
        else:
            result.append(command[i])
            i += 1
    return result + ['--palm-gain', str(PROFILE['palm_gain'])]
