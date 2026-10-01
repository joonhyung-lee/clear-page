"""Compare physical arm motion over each recording's measured pushing interval.

Writes only to an explicitly supplied private output. This single-episode
diagnostic does not estimate benchmark performance or a controller speedup.
"""
import argparse,json
from pathlib import Path
import mujoco
import numpy as np

def measure(folder):
    source=np.load(folder/'task.npz')
    model=mujoco.MjModel.from_binary_path(str(folder/'task.mjb'))
    times=source['time'];qpos=source['qpos'];dt=float(np.median(np.diff(times)))
    assert np.allclose(np.diff(times),dt,atol=1e-6)
    body=model.body('object/box').id
    address=model.jnt_qposadr[model.body_jntadr[body]]
    xy=qpos[:,address:address+2]
    displacement=np.linalg.norm(xy-xy[0],axis=1)
    moving=np.flatnonzero(displacement>.03)
    assert len(moving), 'No pushing observed'
    result=json.loads((folder/'result.json').read_text())
    pushes=[e for e in result['events'] if e['stage']=='push'];assert len(pushes)==1
    stop=min(float(pushes[0]['time_s']),float(times[-1]))
    speed=np.linalg.norm(np.diff(xy,axis=0),axis=1)/np.diff(times)
    final=np.flatnonzero((speed>.015)&(times[1:]<=stop))+1
    begin=max(float(times[0]),float(times[moving[0]])-1)
    end=min(stop,float(times[final[-1]])+.8)
    names=['arm_sh0','arm_sh1','arm_el0','arm_el1','arm_wr0','arm_wr1']
    joints=[model.joint('robot/'+name).id for name in names]
    positions=qpos[(times>=begin)&(times<=end)][:,model.jnt_qposadr[joints]]
    measurements={}
    for order,label in [(1,'velocity'),(2,'acceleration'),(3,'jerk')]:
        derivative=np.diff(positions,n=order,axis=0)/dt**order
        measurements[label]={'rms':float(np.sqrt(np.mean(derivative**2))),
                             'p95Abs':float(np.percentile(np.abs(derivative),95))}
    selected=(times>=begin)&(times<=end)
    motion=xy[selected]
    push_speed=np.linalg.norm(np.diff(motion,axis=0),axis=1)/dt
    object_motion=dict(displacement=float(np.linalg.norm(motion[-1]-motion[0])),
        meanSpeed=float(np.mean(push_speed)),speedStd=float(np.std(push_speed)),
        speedP95=float(np.percentile(push_speed,95)),
        stoppedFraction=float(np.mean(push_speed<.015)),
        accelerationRms=float(np.sqrt(np.mean((np.diff(motion,n=2,axis=0)/dt**2)**2))))
    return {'interval':[begin,end],'samples':len(positions),'dt':dt,'joints':names,
            'measurements':measurements,'objectMotion':object_motion,
            'scope':'Physical joint positions and box XY, unsmoothed finite differences. Each episode uses its own measured pushing interval.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('original',type=Path);p.add_argument('variant',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    a.output.write_text(json.dumps({'original':measure(a.original),'variant':measure(a.variant)},indent=2)+'\n')
