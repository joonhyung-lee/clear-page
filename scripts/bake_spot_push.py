"""Bake a recorded Spot arm pushing interval with its matching MuJoCo version.

No controller or motion is simulated. Forward kinematics is evaluated on saved
qpos. Private source metadata is replaced with a small numerical export record.
"""
import argparse
import json
from pathlib import Path

import mujoco
import numpy as np


def bake(folder, output, include_failed_attempt=False):
    result=json.loads((folder/'result.json').read_text())
    source=np.load(folder/'task.npz')
    model=mujoco.MjModel.from_binary_path(str(folder/'task.mjb'))
    data=mujoco.MjData(model)
    times=source['time'];qpos=source['qpos']
    assert len(times)==len(qpos) and np.all(np.diff(times)>0)
    body=model.body('object/box').id
    joint=model.body_jntadr[body];address=model.jnt_qposadr[joint]
    assert model.jnt_type[joint]==mujoco.mjtJoint.mjJNT_FREE
    xy=qpos[:,address:address+2]
    displaced=np.flatnonzero(np.linalg.norm(xy-xy[0],axis=1)>.03)
    pushes=[e for e in result['events'] if e['stage']=='push']
    assert len(pushes)==1,'Expected exactly one object interaction'
    stop=min(float(pushes[0]['time_s']),float(times[-1]))
    speed=np.linalg.norm(np.diff(xy,axis=0),axis=1)/np.diff(times)
    moving=np.flatnonzero((speed>.015)&(times[1:]<=stop))+1
    no_push=not len(displaced)
    if no_push:
        if not include_failed_attempt:raise ValueError('No measured object push to export; use --include-failed-attempt for the complete failed attempt')
        assert not pushes[0]['success'],'Successful runs require measured motion'
        begin=float(times[0]);end=float(times[-1])
    else:
        assert len(moving)
        begin=max(float(times[0]),float(times[displaced[0]])-1.)
        end=min(stop,float(times[moving[-1]])+.8)
    assert end>begin
    available=np.flatnonzero((times>=begin)&(times<=end))
    # Retain at least 25 physical frames per second, including the final state.
    stride=max(1,int(round(1/(25*np.median(np.diff(times))))))
    indices=available[::stride]
    if indices[-1]!=available[-1]:indices=np.r_[indices,available[-1]]
    positions=[];quaternions=[]
    for index in indices:
        data.qpos[:]=qpos[index]
        if model.nmocap:
            data.mocap_pos[:]=source['mocap_pos'][index]
            data.mocap_quat[:]=source['mocap_quat'][index]
        mujoco.mj_forward(model,data)
        positions.append(data.xpos.copy());quaternions.append(data.xquat.copy())
    fields=['geom_type','geom_size','geom_pos','geom_quat','geom_bodyid','geom_dataid',
            'geom_rgba','geom_matid','geom_group','mat_rgba','mesh_vert','mesh_face',
            'mesh_vertadr','mesh_vertnum','mesh_faceadr','mesh_facenum']
    geometry={key:np.asarray(getattr(model,key)) for key in fields}
    geometry['geom_rgba']=geometry['geom_rgba'].copy()
    geometry['geom_matid']=geometry['geom_matid'].copy()
    for i in range(model.ngeom):
        if model.geom_bodyid[i]==0 and model.geom_type[i]==mujoco.mjtGeom.mjGEOM_BOX:
            geometry['geom_matid'][i]=-1
            geometry['geom_rgba'][i]=[.82,.85,.84,1.]
    # Hide collision-only shapes for links that also have visual meshes.
    robot_bodies={i for i in range(model.nbody) if model.body(i).name.startswith('robot/')}
    visual_bodies={int(model.geom_bodyid[i]) for i in range(model.ngeom) if model.geom_group[i]==2}
    groups=geometry['geom_group'].copy()
    for i in range(model.ngeom):
        if int(model.geom_bodyid[i]) in robot_bodies&visual_bodies and model.geom_group[i]!=2:groups[i]=3
    geometry['geom_group']=groups
    target=np.asarray(result['reference_plan']['paths'][0]['poses'][-1][:2])
    start_xy=xy[indices[0]];final_xy=xy[indices[-1]]
    public=dict(task='spot_box',taskConfig=dict(goal_position=[*target,.3]),
        objectBodyId=int(body),gripperBodyId=int(model.body('robot/arm_link_fngr').id),
        objectReference=result['reference_plan']['paths'][0]['poses'],
        objectSize=result['input_scene']['objects'][0]['size'],
        camera=dict(target=[6.15,6.,.45],position=[3.15,2.25,3.075],fov=.75),
        interval=dict(start=float(times[indices[0]]),end=float(times[indices[-1]])),
        duration=float(times[indices[-1]]-times[indices[0]]),
        moved=float(np.linalg.norm(final_xy-start_xy)),goalError=float(np.linalg.norm(final_xy-target)),
        controller=result['config']['interaction']['selector'],
        pushReportedSuccess=bool(pushes[0]['success']),
        costAblation=result.get('costAblation'),
        gainDiagnostic=result.get('gainDiagnostic'),
        failedAttempt=no_push,
        failureReason=pushes[0].get('info',{}).get('reason') if no_push else None,
        commandSettings=dict(armCommandShaping=result.get('armCommandShaping','bounded'),
                             armCommandHz=result.get('armCommandHz'),
                             commandHoldIntervals=result.get('commandHoldIntervals'),
                             armTrustRegion=result['config']['interaction']['spot_trust_region_rad']),
        scope=('Complete failed attempt, including approach and contact preparation. No object push occurred. '+pushes[0].get('info',{}).get('reason','Interaction failed')+'.') if no_push else 'Recorded object pushing interval. Subsequent arm stow and navigation are outside this clip.')
    if no_push:
        # The complete attempt includes the distant approach. Keep it visible
        # with a wider camera than the cropped contact-only comparisons.
        public['camera']=dict(target=[5.45,6.,.45],position=[1.55,1.125,3.8625],fov=.75)
    output.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(output/'geometry.npz',**geometry)
    np.savez_compressed(output/'states.npz',time=times[indices]-times[indices[0]],
                        positions=positions,quaternions=quaternions)
    (output/'result.json').write_text(json.dumps(public,indent=2))
    (output/'source-indices.json').write_text(json.dumps(indices.tolist()))
    print(json.dumps(public),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('folder',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--include-failed-attempt',action='store_true',help='Export the complete failed attempt when no object push occurred')
    a=p.parse_args();bake(a.folder,a.output,a.include_failed_attempt)
