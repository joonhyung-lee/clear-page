"""Verify the contact-loss explanation against a native physical recording."""
import argparse,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('recording',type=Path);a=p.parse_args()
s=np.load(a.recording/'task.npz');roll=np.load(a.recording/'task.rollouts.npz');meta=json.loads(str(roll['metadata']));result=json.loads((a.recording/'result.json').read_text())
last=max(c['time_s'] for c in result['contacts']);assert abs(last-14.14)<1e-8
k=np.searchsorted(s['time'],15);address=meta['object_qposadr'];box=s['qpos'][:,address:address+3];robot=s['qpos'][:,:3]
assert np.max(np.linalg.norm(box[k:]-box[k],axis=1))<1e-8
moved=np.linalg.norm(box[-1,:2]-box[0,:2]);assert abs(moved-result['displacement_m'])<1e-8
robot_moved=np.linalg.norm(robot[-1,:2]-robot[k,:2]);assert abs(robot_moved-1.08)<.005
assert not result['fell'] and not result['goal_reached'] and roll['knots'].shape[-1]==3
assert any('hip' in body for c in result['contacts'] for body in c['bodies'])
print(f'PASS last contact {last:.2f} s, box displacement {moved:.6f} m, post-contact robot displacement {robot_moved:.6f} m, whole-body contacts permitted')
