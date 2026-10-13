"""Publish measured tracking samples without private paths or credentials."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from policy_matrix_scene import DISPLAY_TERRAIN

ROOT=Path(__file__).resolve().parents[1]
def build(source,body):
    audit=json.loads((source/f'{body}-audit.json').read_text())
    updates=[stage['iteration'] for stage in audit['stages']]
    if not 1<=len(updates)<=10 or updates!=sorted(set(updates)):
        raise ValueError('Replay indices require up to ten unique, chronological checkpoints')
    states=np.load(source/f'{body}-states.npz')
    telemetry=np.load(source/f'{body}-tracking.npz')
    origins=states['origins'];dt=float(telemetry['dt'])
    agents=[]
    for y in sorted(set(origins[:,1])):
        ids=np.flatnonzero(origins[:,1]==y)
        agents.append(int(max(ids,key=lambda i:origins[i,0]) if body=='g1' else min(ids,key=lambda i:(abs(origins[i,0]),origins[i,0]))))
    result=dict(schema=1,body=body,source='Deterministic checkpoint evaluation with forward velocity and heading feedback',
        selection=('Fixed highest available terrain row for every G1 checkpoint; challenging examples, not aggregate performance' if body=='g1' else 'Fixed terrain row closest to world X=0; independent of reward or tracking error'),
        terrainLabels='Traversal direction from the tile center outward; sourceTerrain retains the original pyramid-shape name',
        display='Four rotated copies of each selected recorded rollout, not four independent measurements',
        displayGround='Flat exterior ground continues the recorded tile visually; it does not change the simulated terrain or recorded poses',
        protocol=dict(seed=audit['seed'],dt=dt,commandWorld=[.5,0.,0.],headingTargetRadians=0.,headingGain=1.,
                      commandYawRateLimit=.8,initialYawRadians=0.,durationSeconds=8.,automaticFailureReset=audit.get('automaticFailureReset',True)),
        telemetrySHA256=hashlib.sha256((source/f'{body}-tracking.npz').read_bytes()).hexdigest(),
        columns=['time','target_vx','target_vy','actual_vx','actual_vy','heading_radians','command_yaw_rate','root_x','root_y','root_z'],checkpoints=[])
    for index,stage in enumerate(audit['stages']):
        entry=dict(update=stage['iteration'],checkpointSHA256=stage['sha256'],terrains=[])
        for terrain,agent in zip(audit['terrains'],agents):
            command=telemetry['command_world'][index,:,agent,:2]
            velocity=telemetry['velocity_world'][index,:,agent,:2]
            heading=telemetry['heading'][index,:,agent]
            error=np.linalg.norm(velocity-command,axis=1)
            forward=velocity[:,0]*np.cos(heading)+velocity[:,1]*np.sin(heading)
            rows=np.column_stack([np.arange(len(heading))*dt,command,velocity,heading,
                                  telemetry['command_body'][index,:,agent,2],telemetry['root_position'][index,:,agent]])
            entry['terrains'].append(dict(terrain=DISPLAY_TERRAIN.get(terrain,terrain),sourceTerrain=terrain,sourceAgent=agent,
                meanVelocityError=float(error.mean()),meanHeadingErrorDegrees=float(np.degrees(np.abs(heading)).mean()),
                forwardMotionFraction=float((forward[np.linalg.norm(velocity,axis=1)>.1]>0).mean()),
                samples=np.round(rows,6).tolist()))
        result['checkpoints'].append(entry)
    target=ROOT/f'assets/policy-tracking-{body}.json';target.write_text(json.dumps(result,separators=(',',':'))+'\n')
    name={'g1':'g1-restored-data','spot_arm':'spot_arm-restored-data','spot':'spot-curriculum-data'}[body]
    datafile=ROOT/f'assets/{name}.js';raw=datafile.read_text();prefix,contents=raw.rsplit(' = ',1)
    data=json.loads(contents.strip().removesuffix(';'))
    scene='learning-spot-heading' if body=='spot' else 'learning-'+body
    checkpoints=[]
    for index,stage in enumerate(audit['stages']):
        step=stage['iteration']
        phase=next((p for p in data['stages'] if p['cumulativeUpdates']>step),data['stages'][-1])
        label=('Pretrained initialization' if body=='g1' else 'Initialization') if step==0 else phase['label']
        checkpoints.append(dict(id=f'checkpoint-{step}',label=label,replay=dict(
            scene=scene,cumulativeUpdates=step,startTime=index*8,duration=5.5 if body=='g1' else 8,videoStartOffset=2.5 if body=='g1' else 0,body=body,
            video=f'assets/media/{scene}-update-{step:05d}.mp4',headingTracking=True,
            trackingEvidence=f'assets/policy-tracking-{body}.json')))
    data['checkpoints']=checkpoints
    if data.get('defaultCheckpoint') not in {stage['id'] for stage in checkpoints}:
        data['defaultCheckpoint']=checkpoints[0]['id']
    data['replayNote']=('G1 shows the same highest terrain row at every checkpoint, starting 2.5 seconds into each evaluation. ' if body=='g1' else '')+'Videos are deterministic forward-command checkpoint evaluations with heading feedback. Target and actual velocity arrows share one scale. Four directions are rotated copies of one selected rollout per terrain.'
    datafile.write_text(prefix+' = '+json.dumps(data,separators=(',',':'))+';\n')
    print(body,'published',len(result['checkpoints']),'checkpoints;',len(agents),'measured terrain rollouts each')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--body',choices=['g1','spot_arm','spot'],required=True)
    args=parser.parse_args();build(args.source,args.body)
