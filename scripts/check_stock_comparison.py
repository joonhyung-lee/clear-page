"""Verify transferred stock-box parameters and exported physical poses.

Run with the optimized recording's MuJoCo version. The contract is extracted
from the original task, independently of the transfer implementation.
"""
import argparse,json,re
from pathlib import Path
import msgpack,mujoco,numpy as np,zstandard
p=argparse.ArgumentParser();p.add_argument('recording',type=Path);p.add_argument('contract',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parents[1];contract=json.loads(a.contract.read_text());z=dict(np.load(a.recording/'task.npz'));roll=dict(np.load(a.recording/'task.rollouts.npz'))
m=mujoco.MjModel.from_binary_path(str(a.recording/'task.mjb'));d=mujoco.MjData(m);body=m.body('object/box').id;geom=np.flatnonzero(m.geom_bodyid==body)[0]
assert np.allclose(m.body_mass[body],contract['object_mass'])
assert np.allclose(m.body_inertia[body],contract['object_inertia'])
assert np.allclose(m.body_ipos[body],0)
assert np.allclose(m.geom_size[geom]*2,contract['object_size'])
assert np.allclose(m.geom_friction[geom],[.5,.005,.0001]) and m.geom_priority[geom]==1
address=int(m.jnt_qposadr[m.body_jntadr[body]])
assert np.allclose(z['qpos'][0,address:address+3],np.array(contract['qpos'][36:39])+[4.,4.,0.])
assert json.loads(str(roll['metadata']))['contact_palms']
positions=[];orientations=[]
for q in z['qpos']:
 d.qpos[:]=q;mujoco.mj_forward(m,d);positions.append(d.xpos.copy());orientations.append(d.xquat.copy())
payload=zstandard.ZstdDecompressor().decompress((root/'assets/recordings/mpc-stock-optimized.viser').read_bytes()[8:]);size=int.from_bytes(payload[:8],'little');replay=msgpack.unpackb(payload[8:8+size],raw=False)
count=0;error=0
for t,message in replay['messages']:
 match=re.fullmatch(r'/tracking/body-(\d+)',message.get('name',''))
 if not match or message['type'] not in ('SetPositionMessage','SetOrientationMessage'):continue
 k=np.argmin(abs(z['time']-(t+roll['time_s'][0])));b=int(match[1]);position=message['type']=='SetPositionMessage'
 expected=(positions if position else orientations)[k][b];value=message['position' if position else 'wxyz'];error=max(error,float(np.max(abs(np.array(value)-expected))));count+=1
assert count>1000 and error<1e-7
xy=z['qpos'][:,address:address+2];reference=json.loads(str(z['reference_paths']))[0]['poses'];displacement=float(np.linalg.norm(xy[-1]-xy[0]));goal_error=float(np.linalg.norm(xy[-1]-reference[-1][:2]))
manifest=next(row for row in json.loads((root/'assets/mpc-comparison.json').read_text()) if row['scene']=='mpc-stock-optimized')
assert abs(manifest['objectDisplacement']-displacement)<1e-6 and abs(manifest['goalError']-goal_error)<1e-6
result=json.loads((a.recording/'result.json').read_text())['result'];assert result['failure_type']=='CONTROLLER_TIMEOUT' and not result['success']
print('PASS original box mass, inertia, COM, size, friction, priority and initial position')
print('PASS',count,'exported poses; maximum error',error,'displacement',displacement,'goal error',goal_error)
