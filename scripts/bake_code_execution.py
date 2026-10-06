"""Bake source physics with its MuJoCo version for the offline figure writer."""
import argparse,json
from pathlib import Path
import mujoco,numpy as np
p=argparse.ArgumentParser();p.add_argument('replay',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
m=mujoco.MjModel.from_binary_path(str(a.replay/'task.mjb'));s=mujoco.MjData(m);track=np.load(a.replay/'task.npz')
xpos=[];xquat=[]
for k,t in enumerate(track['time']):
 s.qpos[:]=track['qpos'][k]
 if m.nmocap:s.mocap_pos[:]=track['mocap_pos'][k];s.mocap_quat[:]=track['mocap_quat'][k]
 mujoco.mj_forward(m,s);xpos.append(s.xpos.copy());xquat.append(s.xquat.copy())
rgba=m.geom_rgba.copy()
for i in range(m.ngeom):
 if m.geom_matid[i]>=0:rgba[i]=m.mat_rgba[m.geom_matid[i]]
np.savez_compressed(a.output,time=track['time'],xpos=xpos,xquat=xquat,body_names=[m.body(i).name for i in range(m.nbody)],
 geom_body=m.geom_bodyid,geom_type=m.geom_type,geom_group=m.geom_group,geom_size=m.geom_size,geom_rgba=rgba,
 geom_pos=m.geom_pos,geom_quat=m.geom_quat,geom_dataid=m.geom_dataid,mesh_vert=m.mesh_vert,mesh_face=m.mesh_face,
 mesh_vertadr=m.mesh_vertadr,mesh_vertnum=m.mesh_vertnum,mesh_faceadr=m.mesh_faceadr,mesh_facenum=m.mesh_facenum)
print('Baked',len(xpos),'native poses',flush=True)
