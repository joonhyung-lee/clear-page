"""Export numerical encoder activations and actual Euler states from a checkpoint.

Inputs remain local. Public output contains only the chosen scene's geometry,
network values, and explicit model settings. It never copies source metadata.
"""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import torch

p=argparse.ArgumentParser()
p.add_argument('source',type=Path)
p.add_argument('checkpoint',type=Path)
p.add_argument('bundle',type=Path)
p.add_argument('manifest',type=Path)
a=p.parse_args()
sys.path.insert(0,str(a.source))
from experiments.exp1.models import load_checkpoint
from experiments.exp1.dataset import manifest_to_example
from experiments.common.manifests import SceneManifest

torch.set_num_threads(2)
model,checkpoint=load_checkpoint(str(a.checkpoint))
model.eval()
meta=json.loads((a.bundle/'bundle.json').read_text())
with a.manifest.open() as stream:
 record=next(json.loads(line) for line in stream if json.loads(line)['scene_id']==meta['scene_id'])
example=manifest_to_example(SceneManifest.from_dict(record),checkpoint['canvas_hw'])
batch=model.make_batch([example],device='cpu',include_targets=True)
def array(t):return t.detach().cpu().numpy().round(6).tolist()
with torch.no_grad():
 h=model.encode(batch)
 n=int(batch['object_mask'][0].sum())
 order=meta['plan']['order']
 rank=torch.full_like(batch['rank'],-1)
 if order:rank[0,order]=torch.arange(len(order))
 selected=rank>=0
 traces=[]
 for seed in [0,1,2,3]:
  trace=[]
  code=model.generate_targets(h,batch,rank,selected,steps=30,generator=torch.Generator().manual_seed(seed),trace=trace)
  ref=model.generate_targets(h,batch,rank,selected,steps=30,generator=torch.Generator().manual_seed(seed))
  assert torch.equal(code,ref) and torch.equal(trace[-1][1],ref) and len(trace)==31
  poses=[array(batch['x0'][0,:n]+state[0,:n]*state.new_tensor(model.code_scale())) for t,state in trace]
  traces.append(dict(seed=seed,times=[float(t) for t,state in trace],codes=[array(state[0,:n]) for t,state in trace],xy=poses))
 output=dict(
  description='Checkpoint inference with the recorded interaction order held fixed. Flow time is not execution time.',
  grid=meta['grid'],start=meta['start'],goal=meta['goal'],objects=[o['cell'] for o in meta['objects']],order=order,
  selection=array(h['selection'][0,:n].sigmoid()),mu=array(h['mu'][0,:n]),sigma=array(h['sigma'][0,:n]),
  affordance=array(h['interaction_affordance_logits'][0,:n].sigmoid()),
  structure=array(batch['structure'][0][batch['structure_mask'][0]]),objectFeatures=array(batch['object_features'][0,:n]),
  context=array(h['tokens'][0][h['key_mask'][0]]),embodiment=array(h['embodiment'][0]),sceneTokenCount=int(h['scene_mask'][0].sum()),
  target=array(batch['target_code'][0,:n]),active=selected[0,:n].tolist(),traces=traces,
  settings=dict(dim=int(model.encoder.object_in[-1].out_features),kl=float(model.kl_weight),flow=1.,affordance=1.,availability=0.,
   cardinality=float(model.cardinality_weight),rankSelectedOnly=bool(model.rank_selected_only),sigmaMin=float(model.ordering.sigma_min),
   sigmaMax=float(model.ordering.sigma_max),noiseStd=1.,targetScale=model.code_scale(),integrationSteps=30))
root=Path(__file__).resolve().parents[1]
(root/'assets/method-trace.js').write_text('window.CLEAR_METHOD_TRACE = '+json.dumps(output,separators=(',',':'),allow_nan=False)+';\n')
print('Exported',len(output['context']),'context tokens,',len(traces),'actual 31-state flow integrations; endpoints verified.')
print('Settings',output['settings'])
