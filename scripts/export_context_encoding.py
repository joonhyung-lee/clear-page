"""Export actual shared context features for the displayed maze, without source metadata."""
import argparse,json,sys
from pathlib import Path
import torch
p=argparse.ArgumentParser();p.add_argument('project',type=Path);p.add_argument('case',type=Path);p.add_argument('checkpoint',type=Path);a=p.parse_args();sys.path.insert(0,str(a.project))
from experiments.exp3.trajectory_v3.shared_morphology import load_shared_checkpoint,SharedTraversalPredictor
from experiments.exp3.trajectory_v3.navigation import EmbodimentSpec,TerrainNavigator
from experiments.exp3.trajectory_v3.calibration import digest
from experiments.exp3.trajectory_v3.data import collate
model,record=load_shared_checkpoint(a.checkpoint);model.eval();torch.set_num_threads(2)
scene=json.loads((a.case/'scene.json').read_text());structure=json.loads((a.project/'assets/checkpoints/exp3/structures.json').read_text())['g1'];controller=record['controller_profiles'][digest(structure)]
navigator=TerrainNavigator(SharedTraversalPredictor(model,record['controller_profiles']),**record['navigation']);context=navigator.analyze(scene,EmbodimentSpec(structure,.35,controller)).model_context()
batch=collate([dict(scene=scene,structure_rows=structure,navigation_context=context)],model.config['waypoints'],scene_dim=model.config['scene_dim'],include_targets=False)
with torch.no_grad():h=model._encode(batch)
root=Path(__file__).resolve().parents[1];previous=json.loads((root/'assets/maze-method-trace.js').read_text().split(' = ',1)[1].rstrip(';\n'))
assert torch.allclose(h['mu'][0],torch.tensor(previous['mu']),atol=1e-5)
assert torch.allclose(h['selection'][0].sigmoid(),torch.tensor(previous['selection']),atol=1e-5)
valid=h['tokens'][0,h['key_mask'][0]];count=len(scene['objects']);indices=list(range(min(len(valid),1+count+3)))
value=dict(dimensions=int(valid.shape[1]),validTokens=len(valid),displayDimensions=12,
 labels=['G1']+[f'Object {i}' for i in range(count)]+[f'Scene {i}' for i in range(len(indices)-count-1)],
 features=valid[indices,:12].tolist(),selection=previous['selection'],mu=previous['mu'],sigma=previous['sigma'],
 targetRanks=previous['supervision']['rank'],losses=previous['supervision']['losses'])
(root/'assets/context-encoding.js').write_text('window.CLEAR_CONTEXT='+json.dumps(value,separators=(',',':'))+';\n')
print('Verified checkpoint predictions; exported',len(indices),'rows of',value['dimensions'],'dimensions')
