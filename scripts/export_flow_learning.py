"""Export fixed-noise generation from actual checkpoints in one training lineage."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import torch

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('project',type=Path);p.add_argument('training',type=Path)
a=p.parse_args();sys.path.insert(0,str(a.project))
from experiments.common.manifests import SceneManifest
from experiments.exp1.dataset import manifest_to_example,commit_order
from experiments.exp1.models import build_clear
protocol=json.loads((a.training/'run/protocol.json').read_text())
source=a.project/protocol['config']['data']
assert hashlib.sha256(source.read_bytes()).hexdigest()==protocol['train_sha256']
# First compact training example with at least two interactions. Selection is
# deterministic, independent of model predictions and apparent improvement.
chosen=None
for line in source.read_text().splitlines():
    row=json.loads(line)
    if max(row['environment']['height'],row['environment']['width'])>16:continue
    ex=manifest_to_example(SceneManifest.from_dict(row),(32,32))
    orders=sorted(set(map(tuple,ex.valid_orders or ex.orders))) if ex else []
    order=next((o for o in orders if len(o)>=2),None)
    if order is not None:chosen=(row,commit_order(ex,order),order);break
assert chosen,'No compact two-interaction training scene found'
row,example,order=chosen
stages=[];noise=None
for record in json.loads((a.training/'checkpoints.json').read_text()):
    path=a.training/record['file'];assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256']
    ck=torch.load(path,map_location='cpu',weights_only=False)
    assert ck['step']==record['step'] and ck['protocol_sha256']==record['protocolSHA256']
    model=build_clear(ck['model_cfg'],(32,32));model.load_state_dict(ck['model']);model.eval();torch.set_num_threads(2)
    batch=model.make_batch([example],device='cpu',include_targets=True)
    with torch.no_grad():
        h=model.encode(batch);trace=[]
        rank=batch['rank'];selected=rank>=0
        code=model.generate_targets(h,batch,rank,selected,steps=30,generator=torch.Generator().manual_seed(0),trace=trace)
        reference=model.generate_targets(h,batch,rank,selected,steps=30,generator=torch.Generator().manual_seed(0))
        assert torch.equal(code,reference) and torch.equal(trace[-1][1],code)
        assert len(trace)==31 and float(trace[0][0])==0 and abs(float(trace[-1][0])-1)<1e-6
        assert all(torch.isfinite(y).all() for t,y in trace)
    n=len(example.x0)
    initial=trace[0][1].detach().numpy()
    if noise is None:noise=initial
    else:np.testing.assert_array_equal(noise,initial)
    states=[(batch['x0'][0,:n]+y[0,:n]*y.new_tensor(model.code_scale())).detach().numpy().tolist() for t,y in trace]
    target=(batch['x0'][0,:n]+batch['target_code'][0,:n]*code.new_tensor(model.code_scale())).detach().numpy()
    stages.append(dict(step=record['step'],times=[float(t) for t,y in trace],states=states,
                       targetError=float(np.linalg.norm(np.asarray(states[-1])[list(order),:2]-target[list(order),:2],axis=-1).mean())))
    print('Exported training step',record['step'],'target distance',stages[-1]['targetError'],flush=True)
output=dict(grid=row['environment']['grid'],start=row['robot']['start'] if 'start' in row['robot'] else row.get('start'),
            goal=row['goal']['cell'],objects=np.asarray(example.x0).tolist(),targets=target.tolist(),order=list(order),
            stages=stages,scope='Independent CPU training run using the original CLEAR objective. Same scene, reference order and Gaussian seed at every checkpoint.')
root=Path(__file__).resolve().parents[1]
(root/'assets/flow-learning-data.js').write_text('window.CLEAR_FLOW_LEARNING='+json.dumps(output,separators=(',',':'),allow_nan=False)+';\n')
