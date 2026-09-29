"""Compare the displayed replay objective with the supplied controller source."""
import argparse,ast,math,types
from pathlib import Path
import numpy as np,torch
from bs4 import BeautifulSoup
p=argparse.ArgumentParser();p.add_argument('source',type=Path);a=p.parse_args()
def function(file,name,namespace):
 tree=ast.parse(file.read_text());node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
 exec(compile(ast.Module(body=[node],type_ignores=[]),str(file),'exec'),namespace);return namespace[name]
ns={'torch':torch,'np':np,'angle_delta':lambda a,b:(a-b+np.pi)%(2*np.pi)-np.pi}
cost=function(a.source/'native_sumo.py','_cost',ns);evaluate=function(a.source/'native_sumo.py','_evaluate_controls',ns);path_cost=function(a.source/'tracking.py','rollout_cost',ns)
T=lambda x:torch.tensor(x,dtype=torch.float64)
S=types.SimpleNamespace
hands=np.array([[[.65,2.25,1.4],[.6,1.8,1.4],[.5,.5,.1]],[[.8,1.6,1.4],[1.2,1.6,1.4],[2.5,2.5,.1]]])
g=np.array([[.1,.2,-.97],[.8,0,-.6]])
obj=S(root_link_pos_w=T([[1,2,.6],[1,2,.6]]),root_link_quat_w=T([[1,0,0,0],[0,1,0,0]]))
robot=S(body_link_pos_w=T(hands),projected_gravity_b=T(g));other=S(root_link_pos_w=T([[.5,1,0],[1,1.5,0]]));runtime=S(device='cpu',num_envs=2,object_entities={0:S(data=obj),1:S(data=other)},env=S(scene={'robot':S(data=robot)}))
poses=np.array([[[0,0,0],[.5,0,.1],[1,0,0]],[[.1,0,math.pi/2],[.4,.1,.2],[.8,.1,.3]]]);cursor=[-1]
runtime.step=lambda **kwargs:cursor.__setitem__(0,cursor[0]+1)
self=S(br=runtime,bank=S(K=2),oid=0,residual_space='normalized',hand_ids=[0,1],contact_local=T([[-.4,.2,.8],[-.4,-.2,.8]]),contact_weight=4.,yaw_weight=2.,smoothing=S(strength=0),other_initial={1:[.5,1.]},real=S(original={'walls':[[0,0,1,1],[2,2,3,3]]}))
self.poses=lambda rt,oid:T(poses[:,max(0,cursor[0])]);self._cost=types.MethodType(cost,self)
reference=np.array([[0,0,0],[.5,0,.1],[1,0,0]])
tracker=S(index=0,path=S(poses=reference));tracker._reached=lambda pose,target:np.linalg.norm(pose-target)<.05;tracker.rollout_cost=types.MethodType(path_cost,tracker)
controls=np.arange(66,dtype=float).reshape(2,3,11)/100
actual=evaluate(self,controls,tracker)[0]
expected=[]
for world in range(2):
 total=0.;path_sum=0.;i=0
 for k in range(3):
  theta=poses[world,k,2];R=np.array([[math.cos(theta),-math.sin(theta)],[math.sin(theta),math.cos(theta)]]);targets=np.array([[-.4,.2,.8],[-.4,-.2,.8]]);targets[:,:2]=targets[:,:2]@R.T;targets+=np.array([1,2,.6])
  contact=min(np.linalg.norm(hands[world,:2]-targets,axis=1).sum(),np.linalg.norm(hands[world,:2]-targets[::-1],axis=1).sum())
  wall=0.
  for point in hands[world,:,:2]:
   distances=[]
   for box in [[0,0,1,1],[2,2,3,3]]:
    lo,hi=np.array(box[:2]),np.array(box[2:]);delta=abs(point-(lo+hi)/2)-(hi-lo)/2;distances.append(np.linalg.norm(np.maximum(delta,0))+min(max(delta),0))
   wall+=max(0,.06-min(distances))
  other_distance=np.linalg.norm(np.array([[.5,1],[1,1.5]])[world]-[.5,1])
  total+=4*contact+20*np.linalg.norm(g[world,:2])+500*(int(g[world,2]>-.8)+int(world==1))+100*wall+100*other_distance+.2*np.square(controls[world,k]).sum()
  distance=lambda x,y:math.sqrt(np.square(x[:2]-y[:2]).sum()+2*((x[2]-y[2]+np.pi)%(2*np.pi)-np.pi)**2)
  path_sum+=distance(poses[world,k],reference[min(i,2)])+sum(distance(reference[j],reference[j+1]) for j in range(i,2))
  while i<3 and np.linalg.norm(poses[world,k]-reference[i])<.05:i+=1
 expected.append(total/3+50*path_sum/3)
# The controller accumulates step costs in float32; the independent sum is float64.
assert np.allclose(actual,expected,atol=1e-5,rtol=3e-7),(actual,expected)
html=BeautifulSoup((Path(__file__).resolve().parents[1]/'index.html').read_text(),'html.parser');tex=html.select_one('.mpc-objective-row>.equation')['data-tex']
for term in [r'\lambda_p\mathcal L_{\rm path}',r'\lambda_c\mathcal L_{\rm contact}',r'\lambda_t\mathcal L_{\rm tilt}',r'\lambda_s\mathcal L_{\rm unsafe}',r'\lambda_w\mathcal L_{\rm wall}',r'\lambda_o\mathcal L_{\rm other}',r'\lambda_u\lVert',r'\frac1H']:
 assert term in tex,term
print('PASS displayed objective matches source rollout evaluation:',actual.tolist())
