"""Cache measured model navigation features for frozen-encoder plan adaptation."""
import argparse
import json
from pathlib import Path
import sys
p = argparse.ArgumentParser()
p.add_argument('--project', type=Path, required=True)
p.add_argument('--rows', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
sys.path.insert(0, str(a.project))
import torch
from experiments.exp3.trajectory_v3.data import collate
from experiments.exp3.trajectory_v3.shared_cli import make_navigator, add_current_navigation
from experiments.exp3.trajectory_v3.shared_morphology import load_shared_checkpoint
torch.set_num_threads(2)
model, record = load_shared_checkpoint(a.project/'assets/checkpoints/exp4/paper_axis.pt')
navigator = make_navigator(model, record['controller_profiles'], record['navigation'])
features, indices = [], []
for item in map(json.loads, a.rows.read_text().splitlines()):
    index, row = item['index'], item['row']
    batch = collate([row], model.config['waypoints'], 'cpu', scene_dim=model.config['scene_dim'])
    features.append(add_current_navigation(batch, [row], navigator)['navigation_features'][0])
    indices.append(index)
    if len(indices) % 8 == 0:
        print('navigation rows', len(indices), flush=True)
torch.save(dict(indices=indices, features=torch.stack(features), predictor_hash=navigator.predictor.identity), a.output)
print('complete', len(indices), flush=True)
