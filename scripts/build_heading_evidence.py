"""Publish measured tracking samples without private paths or credentials."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
def build(source,body):
    audit=json.loads((source/f'{body}-audit.json').read_text())
    states=np.load(source/f'{body}-states.npz')
    telemetry=np.load(source/f'{body}-tracking.npz')
    origins=states['origins'];dt=float(telemetry['dt'])
    agents=[]
    for y in sorted(set(origins[:,1])):
        ids=np.flatnonzero(origins[:,1]==y)
        agents.append(int(min(ids,key=lambda i:(abs(origins[i,0]),origins[i,0]))))
    result=dict(schema=1,body=body,source='Deterministic checkpoint evaluation with forward velocity and heading feedback',
        selection='Fixed terrain row closest to world X=0; independent of reward or tracking error',
        display='Four rotated copies of each selected recorded rollout, not four independent measurements',
        protocol=dict(seed=audit['seed'],dt=dt,commandWorld=[.5,0.,0.],headingTargetRadians=0.,headingGain=1.,
                      commandYawRateLimit=.8,initialYawRadians=0.,durationSeconds=8.),
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
            entry['terrains'].append(dict(terrain=terrain,sourceAgent=agent,
                meanVelocityError=float(error.mean()),meanHeadingErrorDegrees=float(np.degrees(np.abs(heading)).mean()),
                forwardMotionFraction=float((forward[np.linalg.norm(velocity,axis=1)>.1]>0).mean()),
                samples=np.round(rows,6).tolist()))
        result['checkpoints'].append(entry)
    target=ROOT/f'assets/policy-tracking-{body}.json';target.write_text(json.dumps(result,separators=(',',':'))+'\n')
    name='g1-restored-data' if body=='g1' else 'spot_arm-restored-data'
    datafile=ROOT/f'assets/{name}.js';raw=datafile.read_text();prefix,contents=raw.rsplit(' = ',1)
    data=json.loads(contents.strip().removesuffix(';'))
    for stage in data['checkpoints']:
        stage['replay']['headingTracking']=True
        stage['replay']['trackingEvidence']=f'assets/policy-tracking-{body}.json'
    data['replayNote']='Videos are deterministic forward-command checkpoint evaluations with heading feedback. RGB axes show the measured heading basis; target and actual velocity arrows share one scale. Four directions are rotated copies of one selected rollout per terrain.'
    datafile.write_text(prefix+' = '+json.dumps(data,separators=(',',':'))+';\n')
    print(body,'published',len(result['checkpoints']),'checkpoints;',len(agents),'measured terrain rollouts each')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--body',choices=['g1','spot_arm'],required=True)
    args=parser.parse_args();build(args.source,args.body)
