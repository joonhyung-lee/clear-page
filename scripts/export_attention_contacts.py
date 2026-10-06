"""Extract saved MPC references and reconstruct contact manifolds at saved poses."""
import argparse
import json
from pathlib import Path
import mujoco
import numpy as np

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--project',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'attention/videos/video-attention.json').read_text())
names=['e03_highmass_g1_clear','e03_highmass_spot_arm_clear','e03_parallel_terrain_g1_clear']
cases={}
for case,name in zip(data['cases'],names,strict=True):
    folder=a.project/'visualization/replays/exp3'/name
    episode=json.loads((folder/'episode.json').read_text())
    targets=[];push_windows=[]
    for attempt in episode.get('attempt_log',[]):
        info=attempt.get('info',{});trace=info.get('mpc_trace',[])
        if 'push_window_s' in info:
            push_windows.append(dict(object_id=attempt['object_id'],start=info['push_window_s'][0],end=info['push_window_s'][1],
                poses=attempt['reference_path']['poses']))
        for k,row in enumerate(trace):
            if 'contact' not in row:continue
            until=min(trace[k+1]['t'] if k+1<len(trace) else row['t']+.1,info['push_window_s'][1])
            targets.append(dict(time=row['t'],until=until,object_id=attempt['object_id'],position=row['contact'],candidate=row.get('execution_index')))
    model=mujoco.MjModel.from_binary_path(str(folder/'task.mjb'));state=mujoco.MjData(model)
    eef_names=['robot/left_palm','robot/right_palm'] if case['body']=='g1' else ['robot/site_arm_link_fngr']
    eef_ids=[model.site(name).id for name in eef_names]
    poses=np.load(folder/'task.npz');state.qpos[:]=poses['qpos'][0];mujoco.mj_forward(model,state)
    objects={}
    for obj in case['frames'][0]['scene']['objects']:
        matches=[i for i in range(1,model.nbody) if (model.body(i).name or '').startswith('object') and np.linalg.norm(state.xpos[i,:2]-obj['pose'][:2])<1e-4]
        assert len(matches)==1,(case['id'],obj['object_id'],matches)
        objects[matches[0]]=obj['object_id']
    rows=[];counts={}
    for index,t in enumerate(poses['time']):
        state.qpos[:]=poses['qpos'][index]
        for field in ['mocap_pos','mocap_quat']:
            if field in poses:getattr(state,field)[:]=poses[field][index]
        mujoco.mj_forward(model,state);groups={}
        for contact in state.contact:
            if contact.dist>.001:continue
            ga,gb=map(int,contact.geom);ba,bb=int(model.geom_bodyid[ga]),int(model.geom_bodyid[gb])
            for obj,robot in [(ba,bb),(bb,ba)]:
                if obj not in objects:continue
                link=model.body(robot).name or ''
                if not link.startswith('robot/'):continue
                allowed=('arm_' in link) if case['body']=='spot_arm' else any(part in link for part in ['wrist','hand','elbow'])
                if allowed:groups.setdefault((objects[obj],link),[]).append(contact.pos.copy())
        points=[]
        for (oid,link),values in groups.items():
            points.append(dict(object_id=oid,link=link.removeprefix('robot/'),position=np.mean(values,axis=0).tolist(),manifold=[v.tolist() for v in values]))
            counts[link]=counts.get(link,0)+1
        rows.append(dict(time=float(t),contacts=points,eef=state.site_xpos[eef_ids].tolist()))
    audit=folder/'CONTACT_AUDIT.json'
    if audit.exists():
        expected=json.loads(audit.read_text())['whole_episode_contact_frames_by_body']
        assert counts==expected,(case['id'],counts,expected)
    cases[case['id']]=dict(targets=targets,eefTargets=[],eefTargetSource='No Cartesian EEF target time series was saved. Spot tracking.eef_world is observed body_link_pos_w, not a target. Contact references remain separate.',frames=rows,counts=counts,pushWindows=push_windows,eefSites=[name.removeprefix('robot/') for name in eef_names],
        eefSource='End-effector site positions reconstructed from every saved native pose. G1 uses distinct left_palm and right_palm sites. Spot arm uses its single finger site.',
        targetSource='Saved MPC contact reference at each update' if targets else 'No saved MPC contact target in this recording',
        contactSource='MuJoCo contact manifolds reconstructed at saved native poses, distance <= 1 mm. Marker is the manifold centroid, not a force measurement.')
    print('PASS',case['id'],'MPC targets',len(targets),'contact frames',sum(bool(r['contacts']) for r in rows),'audit',counts,flush=True)
a.output.write_text(json.dumps(dict(cases=cases),separators=(',',':'))+'\n')
