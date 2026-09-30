"""Measure saved palm contacts and rigid object motion at a fixed replay time.

Use the MuJoCo version that created the binary model. Contacts are recomputed
at saved poses. Counts describe sampled geometric contact, not force telemetry
or contact throughout the intervals between recorded frames.
"""
import argparse
import json
from pathlib import Path
import mujoco
import numpy as np


def audit(folder, seconds=None):
    result_file = folder/'result.json'
    result = json.loads(result_file.read_text()) if result_file.exists() else None
    model = mujoco.MjModel.from_binary_path(str(folder/'task.mjb'))
    data = mujoco.MjData(model)
    target = int(result['targetBody']) if result else model.body('object/box').id
    source = folder/'states.npz'
    if not source.exists():
        source = folder/'checkpoint.npz'
    with np.load(source) as raw:
        states = {k:raw[k] for k in ['time','qpos','positions','quaternions']}
    assert np.all(np.diff(states['time']) > 0)
    ids = np.flatnonzero(states['time'] <= (seconds if seconds is not None else np.inf)+1e-8)
    hands = {side:model.geom('robot/'+side+'_hand_collision').id for side in ['left','right']}
    contacts = []
    for i in ids:
        data.qpos[:] = states['qpos'][i]
        mujoco.mj_forward(model, data)
        touched = set()
        for contact in data.contact:
            if contact.dist > 0:
                continue
            a, b = map(int, contact.geom)
            for side, geom in hands.items():
                if (a == geom and model.geom_bodyid[b] == target or
                        b == geom and model.geom_bodyid[a] == target):
                    touched.add(side)
        if touched:
            contacts.append(dict(time=float(states['time'][i]), hands=sorted(touched)))
    initial, final = states['positions'][ids[[0,-1]], target]
    return dict(terminal=result is not None, endTime=float(states['time'][ids[-1]]),
                frames=len(ids), displacementXY=float(np.linalg.norm(final[:2]-initial[:2])),
                leftFrames=sum('left' in c['hands'] for c in contacts),
                rightFrames=sum('right' in c['hands'] for c in contacts),
                bilateralFrames=sum(len(c['hands'])==2 for c in contacts), contacts=contacts,
                scope='Geometric contacts at saved frames. No inference of continuous contact or force.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    parser.add_argument('--seconds',type=float)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    value = audit(args.folder,args.seconds)
    if args.output:
        args.output.write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='contacts'},indent=2))
