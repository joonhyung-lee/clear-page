"""Development-only CLEAR plan adaptation on explicit tall-box geometry teachers.

Keeps the original selection/ranking/flow objective. No physical success labels
are invented. Prospective comparison families (506+) never enter training.
Uses a fixed final checkpoint, not selection by comparison outcome.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--project', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--steps', type=int, default=500)
p.add_argument('--teachers', type=Path, help='Reuse previously generated tall-box geometric teachers')
p.add_argument('--navigation-cache', type=Path, help='Reuse identical frozen-model navigation features')
p.add_argument('--lr', type=float, default=5e-5)
a = p.parse_args()
root = a.project.resolve()
a.output = a.output.resolve()
a.output.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(root))
os.chdir(root)
import torch
from experiments.exp4.sprint6h import families
from experiments.exp4.sprint6h.build_dataset import family_rows
from experiments.exp3.trajectory_v3.data import collate
from experiments.exp3.trajectory_v3.navigation_cache import GeometryCache
from experiments.exp3.trajectory_v3.shared_cli import add_current_navigation, make_navigator
from experiments.exp3.trajectory_v3.shared_morphology import load_shared_checkpoint, checkpoint_record
from replanning_upright_profile import PROFILE

torch.set_num_threads(2)
torch.manual_seed(0)
families.BOX['size'][2] = PROFILE['box_height_m']
navigator, assessor = families.geometry_tools()
embodiment = families.g1_embodiment()
rows = []
if a.teachers:
    rows = list(map(json.loads, a.teachers.read_text().splitlines()))
else:
    for split, seeds in [('train', range(100, 132)), ('val', range(200, 203))]:
        for seed in seeds:
            family = families.make_family(seed)
            new = family_rows({'N6': {'family': family}}, split, navigator, assessor,
                              embodiment, direction_rule='negative_y', repair_prefixes=True)
            rows.extend(new)
            print(json.dumps(dict(event='geometry_teachers', family_seed=seed, rows=len(new))), flush=True)
assert rows and all(all(o['size'][2] == PROFILE['box_height_m'] for o in r['scene']['objects']) for r in rows)
data = ''.join(json.dumps(r)+'\n' for r in rows)
(a.output/'teachers.jsonl').write_text(data)
train = [r for r in rows if r['split'] == 'train']
val = [r for r in rows if r['split'] == 'val']
assert train and val
parent = root/'assets/checkpoints/exp4/paper_axis.pt'
model, record = load_shared_checkpoint(parent)
for name, param in model.named_parameters():
    param.requires_grad_(not name.startswith(('encoder.', 'traversal_affordance.')))
config = model.config
metadata = dict(training_mode='tall_box_geometric_plan_adaptation', seed=0,
                exp4_decoder=record['exp4_decoder'],
                parent_sha256=hashlib.sha256(parent.read_bytes()).hexdigest(),
                data_sha256=hashlib.sha256(data.encode()).hexdigest(),
                train_family_seeds=list(range(100,132)), validation_family_seeds=list(range(200,203)),
                excluded_comparison_family_seeds=list(range(506,518)),
                box_height_m=PROFILE['box_height_m'], steps=a.steps,
                learning_rate=a.lr,
                objective='Original CLEAR selection, ranking, regularization and flow plan loss',
                scope='Geometric plan teachers only. No new physical feasibility labels or certification.',
                checkpoint_selection='Fixed final step; no selection on comparison outcomes',
                trainable_modules='Ordering and flow heads only; shared encoder and traversal predictor frozen',
                groups=dict(Counter(r['group'] for r in train)))
(a.output/'training.json').write_text(json.dumps(metadata, indent=2)+'\n')
optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=.01)
generator = torch.Generator().manual_seed(0)
sampling = torch.Generator().manual_seed(0)
full = collate(train, config['waypoints'], 'cpu', scene_dim=config['scene_dim'])
# The encoder never changes, so these are the exact current-model features at
# every step. Separate worker processes keep CPU preprocessing bounded.
workers = []
for worker in range(8):
    if a.navigation_cache:
        continue
    subset = a.output/f'navigation-{worker}.jsonl'
    subset.write_text(''.join(json.dumps(dict(index=i, row=row))+'\n' for i,row in enumerate(train+val) if i % 8 == worker))
    log = (a.output/f'navigation-{worker}.log').open('w')
    command = [sys.executable, str(Path(__file__).with_name('precompute_replanning_navigation.py')),
               '--project', str(root), '--rows', str(subset), '--output', str(a.output/f'navigation-{worker}.pt')]
    workers.append((subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT), log))
for proc, log in workers:
    status = proc.wait()
    log.close()
    assert status == 0, 'Navigation worker failed; inspect its log'
features = {}
identities = set()
for worker in range(8):
    cached = torch.load((a.navigation_cache or a.output)/f'navigation-{worker}.pt', weights_only=True)
    identities.add(cached['predictor_hash'])
    features.update(zip(cached['indices'], cached['features']))
assert len(identities) == 1
if a.navigation_cache:
    assert (a.navigation_cache/'teachers.jsonl').read_text() == data
navigation = torch.stack([features[i] for i in range(len(train)+len(val))])
full['navigation_features'] = navigation[:len(train)]
assert make_navigator(model, record['controller_profiles'], record['navigation']).predictor.identity in identities
print('PASS frozen-model navigation features cached for', len(navigation), 'rows', flush=True)
history = []
start = time.monotonic()
for step in range(1, a.steps+1):
    indices = torch.randint(len(train), (16,), generator=sampling).tolist()
    model.eval()
    batch = {k: v[indices] for k,v in full.items()}
    model.train()
    model.encoder.eval()
    optimizer.zero_grad(set_to_none=True)
    loss, terms = model.loss(batch, generator)
    if not torch.isfinite(loss):
        raise FloatingPointError('Nonfinite plan loss')
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
    optimizer.step()
    if step == 1 or step % 20 == 0 or step == a.steps:
        value = dict(step=step, loss=float(loss.detach()), terms=terms, elapsed_s=time.monotonic()-start)
        history.append(value)
        (a.output/'loss.json').write_text(json.dumps(history, indent=2)+'\n')
        print(json.dumps(value), flush=True)
model.eval()
total = 0.
with torch.no_grad():
    navigator = make_navigator(model, record['controller_profiles'], record['navigation'])
    assert navigator.predictor.identity in identities, 'Cached navigation became stale'
    for i in range(0, len(val), 16):
        part = val[i:i+16]
        batch = collate(part, config['waypoints'], 'cpu', scene_dim=config['scene_dim'])
        batch['navigation_features'] = navigation[len(train)+i:len(train)+i+len(part)]
        loss, _ = model.loss(batch, generator)
        assert torch.isfinite(loss)
        total += float(loss)*len(part)
metadata.update(validation_loss=total/len(val), elapsed_s=time.monotonic()-start, status='complete; physical evaluation pending')
torch.save(checkpoint_record(model, record['controller_profiles'], record['navigation'], step=a.steps, **metadata), a.output/'last.pending.pt')
(a.output/'last.pending.pt').replace(a.output/'last.pt')
(a.output/'training.json').write_text(json.dumps(metadata, indent=2)+'\n')
print(json.dumps(dict(event='complete', checkpoint=str(a.output/'last.pt'), validation_loss=total/len(val))), flush=True)
