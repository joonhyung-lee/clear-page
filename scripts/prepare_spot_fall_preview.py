"""Crop the saved Spot attempt at toppling + 5 seconds and tighten its camera.

Toppling is the first sampled pose whose local up axis points below horizontal.
Source trajectories and controller settings remain unchanged.
"""
import argparse,json,shutil
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 if a.source.resolve()==a.output.resolve():raise ValueError('Preserve the complete source recording')
 a.output.mkdir(parents=True,exist_ok=True)
 result=json.loads((a.source/'result.json').read_text());states=dict(np.load(a.source/'states.npz'))
 up=Rotation.from_quat(states['quaternions'][:,1],scalar_first=True).as_matrix()[:,2,2]
 fallen=np.flatnonzero(up<=0)
 if not len(fallen):raise ValueError('No recorded toppling event')
 topple=float(states['time'][fallen[0]]);cutoff=topple+5
 count=int(np.searchsorted(states['time'],cutoff+1e-8,side='right'))
 clipped={k:v[:count] for k,v in states.items()};np.savez_compressed(a.output/'states.npz',**clipped)
 shutil.copyfile(a.source/'geometry.npz',a.output/'geometry.npz')
 result['sourceRecordingDuration']=result['duration'];result['duration']=float(clipped['time'][-1])
 result['displayClip']=dict(start=0,end=result['duration'],toppleTime=topple,postToppleSeconds=5,
     criterion='First recorded base local up vector at or below the world horizontal plane',zoom=1.25)
 obj=clipped['positions'][:,result['objectBodyId']]
 result['moved']=float(np.linalg.norm(obj[-1,:2]-obj[0,:2]))
 result['goalError']=float(np.linalg.norm(obj[-1,:2]-result['taskConfig']['goal_position'][:2]))
 result['interval']=[0,result['duration']]
 result['scope']=result['scope'].replace('Full attempt from reset.','Shown from reset through five seconds after toppling.')
 result['verification']['sourceFrames']=result['verification']['frames']
 result['verification']['frames']=count;result['verification']['fullAttempt']=False
 eye=np.array(result['camera']['position']);at=np.array(result['camera']['target'])
 forward=(at-eye)/np.linalg.norm(at-eye);right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);upvec=np.cross(right,forward)
 shift=-.45*right-.2*upvec
 result['camera']['position']=(eye+shift).tolist();result['camera']['target']=(at+shift).tolist()
 result['camera']['fov']=float(2*np.arctan(np.tan(result['camera']['fov']/2)/1.25))
 (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print('Toppled:',topple,'end:',result['duration'],'frames:',count,'zoom: 1.25')
if __name__=='__main__':main()
