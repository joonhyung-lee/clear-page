"""Extract actual palm and object motion in the recording's MuJoCo version."""
import argparse,json
from pathlib import Path
import mujoco,numpy as np
p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
z=dict(np.load(a.folder/'task.npz'));r=dict(np.load(a.folder/'task.rollouts.npz'));meta=json.loads(str(r['metadata']))
m=mujoco.MjModel.from_binary_path(str(a.folder/'task.mjb'));d=mujoco.MjData(m)
names=['left_palm','right_palm'] if 'runtime' in meta else ['robot/left_palm','robot/right_palm']
ids=[m.site(n).id for n in names]
address=meta.get('object_qposadr')
if address is None:
 b=m.body('object/box').id;address=int(m.jnt_qposadr[m.body_jntadr[b]])
first=float(r['time_s'][0]);last=float(r['valid_until_s'][np.flatnonzero(r['object_id']==r['object_id'][0])[-1]])
rows=[]
for i,t in enumerate(z['time']):
 if t<first-1e-6 or t>last+1e-6:continue
 d.qpos[:]=z['qpos'][i];mujoco.mj_forward(m,d)
 rows.append([float(t),*d.site_xpos[ids].ravel().tolist(),*d.qpos[address:address+3].tolist()])
np.savez_compressed(a.output,observed=rows)
print(len(rows),'physical observations')
