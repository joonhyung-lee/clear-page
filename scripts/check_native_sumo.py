"""Check native replay fidelity against the source physical states.

Run with the same MuJoCo version as the supplied recording.
"""
import argparse
import json
from pathlib import Path
import re

import msgpack
import mujoco
import numpy as np
import zstandard

p=argparse.ArgumentParser(description=__doc__);p.add_argument('recording',type=Path);args=p.parse_args()
root=Path(__file__).resolve().parents[1]
a=dict(np.load(args.recording/'task.npz'));r=dict(np.load(args.recording/'task.rollouts.npz'));meta=json.loads(str(r['metadata']))
assert meta['runtime']=='SUMO native G1 C++ and Judo CEM' and meta['task']=='g1_box'
assert np.isfinite(a['qpos']).all() and np.isfinite(r['eef_world']).all()
assert np.allclose(np.diff(a['time']),.02) and np.allclose(np.diff(r['time_s']),.05)
assert r['eef_world'].shape[1]==25 and r['eef_world'].shape[2]==len(meta['future_times'])
assert np.all(r['applied_candidate']==24)
m=mujoco.MjModel.from_binary_path(str(args.recording/'task.mjb'));d=mujoco.MjData(m)
positions=[];orientations=[];physical_contacts=0
for q in a['qpos']:
 d.qpos[:]=q;mujoco.mj_forward(m,d);positions.append(d.xpos.copy());orientations.append(d.xquat.copy())
 for c in d.contact:
  names=[m.body(int(m.geom_bodyid[g])).name for g in c.geom]
  if 'table' in names and any('hip' in name or 'torso' in name for name in names):physical_contacts+=1
positions=np.array(positions);orientations=np.array(orientations)
payload=zstandard.ZstdDecompressor().decompress((root/'assets/recordings/mpc-baseline.viser').read_bytes()[8:]);size=int.from_bytes(payload[:8],'little');replay=msgpack.unpackb(payload[8:8+size],raw=False)
counts={'position':0,'orientation':0};error=0.
for t,msg in replay['messages']:
 match=re.fullmatch(r'/tracking/body-(\d+)',msg.get('name',''))
 if not match or msg['type'] not in ('SetPositionMessage','SetOrientationMessage'):continue
 k=int(np.argmin(abs(a['time']-t)));b=int(match[1]);pos=msg['type']=='SetPositionMessage';counts['position' if pos else 'orientation']+=1
 error=max(error,float(np.max(abs(np.array(msg['position' if pos else 'wxyz'])-(positions if pos else orientations)[k,b]))))
assert error<1e-7 and physical_contacts>0
manifest=next(x for x in json.loads((root/'assets/mpc-comparison.json').read_text()) if x['scene']=='mpc-baseline')
address=meta['object_qposadr'];xy=a['qpos'][:,address:address+2];displacement=float(np.linalg.norm(xy[-1]-xy[0]))
assert abs(displacement-manifest['objectDisplacement'])<1e-8
assert manifest['goalReached'] is False and displacement>.5
process=json.loads((root/'assets/mpc-process-data.js').read_text().split('=',1)[1].rstrip(';\n'))['baseline']
assert process['sourceUpdates']==len(r['time_s'])
for update in process['updates']:
 i=update['sourceIndex']-1
 assert abs(update['time']-r['time_s'][i])<1e-6
 assert np.max(abs(np.asarray(update['paths'])-r['eef_world'][i]))<=.0000051
 assert update['applied']==int(r['applied_candidate'][i])
 assert update['elites']==r['elite_indices'][i].tolist()
print('PASS native replay:',counts,'maximum error',error,'body contacts',physical_contacts,'object displacement',round(displacement,4),'m')
print('PASS process explorer: source timestamps, candidates, elites and applied means')
