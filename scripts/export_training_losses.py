"""Export numeric samples for the original CLEAR objective from the frozen snapshot."""
import argparse
import hashlib
import json
import math
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
manifest = json.loads((args.source / 'training_loss.sources.json').read_text())
name = 'A_seed0'  # Original CLEAR, not the alternative matching objectives.
limits = manifest['runs'][name]
metrics = ['loss', 'selection', 'order', 'kl', 'flow', 'affordance']
raw = (args.source / name / 'training.jsonl').read_bytes()
rows = []
for line in raw.splitlines():
    row = json.loads(line)
    if 'loss' not in row or row['step'] > limits['last_step']:
        continue
    values = {key: row[key] for key in ['step', *metrics]}
    assert all(isinstance(v, (int, float)) and math.isfinite(v) for v in values.values())
    assert not rows or values['step'] > rows[-1]['step']
    total = row['selection'] + row['order'] + .001 * row['kl'] + row['flow'] + row['affordance']
    assert math.isclose(row['loss'], total, abs_tol=2e-6, rel_tol=2e-6), row['step']
    rows.append(values)
assert len(rows) == limits['records'] and rows[-1]['step'] == limits['last_step']
data = dict(samples=rows, maxStep=rows[-1]['step'], window=21)
(root / 'assets/training-loss-data.js').write_text(
    'window.CLEAR_TRAINING_LOSSES=' + json.dumps(data, separators=(',', ':'), allow_nan=False) + ';\n')
audit = dict(input=str(args.source / name / 'training.jsonl'),
             currentHash=hashlib.sha256(raw).hexdigest(), publishedSamples=len(rows),
             lastStep=rows[-1]['step'], band='Centered local population standard deviation, 21 samples, truncated at endpoints')
(root / '.git/training-loss-sources.json').write_text(json.dumps(audit, indent=2) + '\n')
print(f'Exported {len(rows)} original CLEAR samples. Every total matches its five components.')
