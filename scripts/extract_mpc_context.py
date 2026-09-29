"""Extract measured body poses and palms using the recording's MuJoCo version."""
import argparse,json
from pathlib import Path
import mujoco,numpy as np
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--start',type=float,default=0);p.add_argument('--duration',type=float,default=40);a=p.parse_args()
s=np.load(a.source/'task.npz');m=mujoco.MjModel.from_binary_path(str(a.source/'task.mjb'));d=mujoco.MjData(m)
prefix='robot/' if mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_SITE,'robot/left_palm')>=0 else ''
palms=[m.site(prefix+h+'_palm').id for h in ['left','right']]
root=m.body(prefix+'pelvis').id
robot=[i for i in range(1,m.nbody) if int(m.body_rootid[i])==root]
edges=np.asarray([[int(m.body_parentid[i]),i] for i in robot if i!=root])
ref=json.loads(str(s['reference_paths']))[0];oid=ref['object_id'];meta=json.loads(str(np.load(a.source/'task.rollouts.npz')['metadata']));target=m.body('object/box' if prefix else meta['target_body']).id;address=int(m.jnt_qposadr[m.body_jntadr[target]])
rows=[];positions=[];orientations=[];times=[]
# 10 Hz is the optimized record cadence and a subset of the 50 Hz native record.
for t in np.arange(a.start,a.start+a.duration+.00001,.1):
 i=int(np.argmin(abs(s['time']-t)));assert abs(s['time'][i]-t)<1e-5,(t,s['time'][i])
 d.qpos[:]=s['qpos'][i];mujoco.mj_forward(m,d)
 rows.append([float(s['time'][i]),*d.site_xpos[palms].ravel(),*d.qpos[address:address+3]])
 positions.append(d.xpos.copy());orientations.append(d.xquat.copy());times.append(float(s['time'][i]-a.start))
np.savez_compressed(a.output,time=times,positions=positions,orientations=orientations,observed=rows,edges=edges,robot=robot,objects=[i for i in range(1,m.nbody) if i not in robot and m.body_jntnum[i]>0 and m.jnt_type[m.body_jntadr[i]]==0])
print(f'{len(times)} measured frames, {len(robot)} robot bodies, {times[-1]:.1f} s')
