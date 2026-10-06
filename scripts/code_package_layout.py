"""Task-oriented public checkpoint paths, derived from recorded provenance."""
import json
from pathlib import PurePosixPath
import re


def checkpoint_layout(package, audit):
    artifacts = json.loads((package / 'docs/artifact_manifest.json').read_text())['files']
    mapping = {}
    for old, row in sorted(audit['scanned_files'].items()):
        if not old.endswith('.pt'):
            continue
        path = PurePosixPath(old)
        origin = artifacts.get(old, {}).get('source_path', '')
        if '/pretrained/' in old:
            relative = old.split('/pretrained/', 1)[1]
            new = 'locomotion/' + relative
        elif '/exp3/paper/' in old:
            new = 'maze/reference/' + old.split('/exp3/paper/', 1)[1]
        elif '/leap2026/V4/' in old:
            new = 'maze/joint_planning/' + path.name
        elif '/leap2026/WP-4/' in old:
            new = 'maze/body_transfer/' + path.name
        elif '/leap2026/WP-1/' in old:
            new = 'grid/reference/' + path.name
        elif '/exp1/ancestry/' in old:
            tail = old.split('/exp1/ancestry/', 1)[1]
            if tail.startswith('experiments/exp1/runs/'):
                tail = tail.removeprefix('experiments/exp1/runs/')
            else:
                tail = tail.replace('structural_replay_20260913_c/', 'structure_replay/').replace('structural_training_20260913_a/', 'structure_training/')
            new = 'grid/training_history/' + tail
        elif '/anonymous/' in old:
            if 'exp1_grid/clear_rankmask_scratch/' in origin:
                run = origin.split('/train/', 1)[1].split('/')[0]
                new = 'grid/reachability_variants/' + run + '.pt'
            elif 'exp1_grid/plancode_fsq/' in origin:
                run = origin.split('/train/', 1)[1].split('/')[0]
                new = 'grid/plan_encoding/' + run + '.pt'
            elif 'assets/checkpoints/exp3/paper/' in origin:
                new = 'maze/reference/' + origin.split('/exp3/paper/', 1)[1]
            elif 'exp3_maze/holdout_spotarm/' in origin:
                run = origin.split('/holdout_spotarm/', 1)[1].split('/')[0]
                new = 'maze/body_transfer/' + run + '.pt'
            else:
                raise ValueError('Unclassified checkpoint: ' + old)
        else:
            raise ValueError('Unclassified checkpoint: ' + old)
        # Hash suffixes are provenance keys, retained in the path map instead.
        new = re.sub(r'-[a-f0-9]{10}(?=\.pt$)', '', new)
        mapping[old] = dict(path='checkpoints/' + new, sha256=row['sha256'])
    paths = [entry['path'] for entry in mapping.values()]
    if len(paths) != len(set(paths)):
        raise ValueError('Checkpoint path collision')
    return mapping


README = '''# CLEAR

## Setup

Extract `clear-source.zip` and `clear-pretrained.zip` into the same directory.
From `clear/`, run `python tools/link_checkpoints.py` to connect the organized
checkpoint files to the paths used by the original experiment code.
The link step is idempotent and does not overwrite existing files.

## Contents

- `runtime/clear/`: model and planning implementation.
- `runtime/experiments/`: experiment configurations, inputs and evaluation code.
- `runtime/assets/`: robot assets and runtime resources.
- `checkpoints/grid/`: reference models, variants and training history for 2D grids.
- `checkpoints/maze/`: reference navigation, body transfer and joint planning models.
- `checkpoints/locomotion/`: G1, Go1 and Spot locomotion policies.
- `docs/`: training recipes and provenance for the available snapshot.
- `tools/`: verification and checkpoint setup.

Checkpoints are grouped by task and experiment protocol, not collection directory.
All 153 checkpoint payloads are unchanged. The path map in
`docs/checkpoint_paths.json` records each original path and SHA-256.
The original source and provenance records retain their recorded paths.

## Planning example

```bash
python run.py plan maze \\
  --checkpoint ../checkpoints/maze/reference/seed0/clear.pt \\
  --input experiments/exp3/data/example_g1.json \\
  --out outputs/reproduction/plan.json --device cpu
```

The available snapshot is incomplete. See `docs/STATUS.md` for missing inputs
and validation scope. Historical runs are not interchangeable with reference
models. No end-to-end reproduction claim is made for every packaged experiment.
'''
