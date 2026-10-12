"""Verify coincident checkpoint initialization and orthogonal replay directions."""
import sys,json,tempfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from recording_io import read_recording
from policy_matrix_scene import arrange
from render_policy_videos import data
for dataset in ['g1-restored-data','spot_arm-restored-data','spot-curriculum-data']:
 d=data(dataset)
 for stage in d.get('checkpoints',d['stages']):
  if not stage.get('replay'):continue
  replay=stage['replay'];scene=replay['scene'];start=replay.get('startTime',0)
  raw=bytes.fromhex(json.loads((ROOT/f'assets/recordings/{scene}.hex.js').read_text().rsplit(' = ',1)[1].strip().removesuffix(';')))
  with tempfile.NamedTemporaryFile() as f:
   f.write(raw);f.flush();record,buffers=read_recording(f.name)
  record,buffers,views,meta=arrange(record,buffers,start)
  first=next(m for _,m in record['messages'] if m['type']=='BatchedMeshesMessage')
  def sample(t):
   ref=first['props']['batched_positions']
   for ts,m in record['messages']:
    if ts<=t and m.get('name')==first['name'] and 'batched_positions' in m.get('updates',{}):ref=m['updates']['batched_positions']
   return np.frombuffer(buffers[ref['__binary_index']],dtype=ref['dtype']).reshape(-1,3)
  initial=sample(start);end=sample(start+6)
  for group in range(len(views)):
   xy=initial[group*4:group*4+4,:2]
   assert np.max(np.abs(xy-xy[0]))<1e-5,(scene,start,group,xy)
   assert len({m['sourceAgent'] for m in meta[group*4:group*4+4]})==1
   delta=end[group*4:group*4+4,:2]-xy
   lengths=np.linalg.norm(delta,axis=1)
   assert lengths.max()-lengths.min()<1e-4
   if lengths.max()>.001:assert abs(np.dot(delta[0],delta[1]))<1e-3
  print(scene,start,': shared initialization and four orthogonal replay directions PASS',flush=True)
