"""Deterministic illustrative object motion for the scene-state explanation."""
import numpy as np

PALETTE = [(173,207,213),(232,197,173),(191,213,177),(208,191,218)]
rng = np.random.default_rng(41)
CENTERS = np.array([[-.88,-.76,.20],[.91,-.69,.23],[-.78,.86,.20],[.88,.91,.23]])
angles = rng.uniform(-np.pi,np.pi,4)
lengths = rng.uniform(.34,.47,4)
DELTAS = np.column_stack([np.cos(angles)*lengths,np.sin(angles)*lengths,np.zeros(4)])
STARTS, ENDS = CENTERS-DELTAS, CENTERS+DELTAS
PERIODS = [6.,12.,6.,12.]
OFFSETS = [0.,.12,.25,.38]

def sample_object(index, seconds):
    phase = (seconds/PERIODS[index]+OFFSETS[index])%1
    progress = .5-.5*np.cos(2*np.pi*phase)
    position = STARTS[index]+(ENDS[index]-STARTS[index])*progress
    forward = phase < .5
    target = ENDS[index] if forward else STARTS[index]
    direction = DELTAS[index]*(1 if forward else -1)
    yaw = -.32+.64*progress
    return dict(position=position,yaw=yaw,target=target,
                target_yaw=.32 if forward else -.32,
                heading=float(np.arctan2(direction[1],direction[0])),
                ghost_visible=bool(np.linalg.norm(target-position)>.065))
