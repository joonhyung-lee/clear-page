"""Add recorded palm-site markers to a native replay, preserving all physical poses."""
import argparse,copy
from pathlib import Path
import mujoco,numpy as np
from recording_io import read_recording,write_recording
p=argparse.ArgumentParser();p.add_argument('model',type=Path);p.add_argument('recording',type=Path);a=p.parse_args()
m=mujoco.MjModel.from_binary_path(str(a.model));record,buffers=read_recording(a.recording)
assert not any('/palm-centers-' in message.get('name','') for _,message in record['messages']),'Palm markers already exist'
def array(value,dtype):
 data=np.asarray(value,dtype=dtype);index=len(buffers);buffers.append(data.tobytes());return {'__binary_index':index,'dtype':data.dtype.str}
new=[]
for side in ['left','right']:
 site=m.site(side+'_palm');name=f'/tracking/body-{int(site.bodyid[0])}/palm-centers-{side}'
 for outline in [True,False]:
  points=site.pos.copy()[None,:]
  if not outline:points[:,2]+=.004
  props=dict(points=array(points,'<f4'),colors=array([25,27,26] if outline else [207,154,151],'u1'),point_size=.055*(1.22 if outline else 1),point_shape='circle',point_shading='flat',precision='float32',scale=1.)
  new.append((0.,dict(name=name+('-outline' if outline else ''),owner='',virtual=False,props=props,type='PointCloudMessage')))
cut=next((i for i,(t,_) in enumerate(record['messages']) if t>0),len(record['messages']));record['messages'][cut:cut]=new
write_recording(a.recording,record,buffers);print(a.recording.name,': added both recorded palm anchors')
