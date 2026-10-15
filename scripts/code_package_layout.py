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

Source code and pretrained models for the CLEAR planner (anonymous review copy).

## Layout

```
run.py                      one entry point: train / plan / evaluate / refine / report
runtime/clear/              model, data and planning implementation
runtime/experiments/        experiment code and inputs: exp1 grid, exp2 manipulation,
                            exp3 maze, exp4 replanning, exp5 maze v4
runtime/assets/             robot models and simulation assets
runtime/data/               probe scenes, rosters and plan cohorts
runtime/tests/              unit tests
checkpoints/                pretrained models, downloaded by tools/fetch_checkpoints.py
tools/fetch_checkpoints.py  downloads the checkpoints and links them
tools/link_checkpoints.py   links already extracted checkpoints to the paths the experiment code loads
docs/checkpoint_paths.json  path map and SHA-256 of every checkpoint
```

## Setup

```bash
unzip clear-source.zip && cd clear
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.7"
python -m pip install numpy einops pyyaml scipy
python tools/fetch_checkpoints.py
```

`fetch_checkpoints.py` downloads the 1.8 GB of checkpoints into `checkpoints/`
(verifying each SHA-256, resumable) and links them to the paths the experiment
code loads. If `clear-pretrained.zip` was obtained separately, extract it next to
`clear-source.zip` and run `python tools/link_checkpoints.py` instead. Both steps
are idempotent and never overwrite files.

Planning and evaluation run on CPU with these packages. Physical simulation and
the manipulation experiments need the optional extras listed in `pyproject.toml`.

## Planning example

```bash
python run.py plan maze \\
  --checkpoint ../checkpoints/maze/reference/seed0/clear.pt \\
  --input experiments/exp3/data/example_g1.json \\
  --out outputs/reproduction/plan.json --device cpu
```

`python run.py --help` lists every action/task pair. Relative paths resolve
inside `runtime/`.

## Checkpoints

`checkpoints/grid/`, `checkpoints/maze/` and `checkpoints/locomotion/` group the
153 models by task. Reference models are the ones used for the reported results;
`training_history/` and the variant directories are provided as trained, for
inspection. Planning and evaluation with the reference checkpoints are verified;
retraining every experiment end to end is not claimed.
'''
