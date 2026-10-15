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


RUNS = [
    ('train_grid', 'scripts.train', ('--experiment', 'grid2d'), 'Train the grid (exp1) models.'),
    ('evaluate_grid', 'evaluation.exp1', (), 'Evaluate CLEAR or an ordering baseline on the grid (exp1): --method clear | clear_ro | clear_ho | autoregressive | gumbel_sinkhorn | polynet.'),
    ('train_manipulation', 'experiments.exp2.train_comparison', (), 'Train the manipulation (exp2) comparison arms.'),
    ('refine_manipulation', 'experiments.exp2.refine_flow_comparison', (), 'Refine the manipulation (exp2) flow checkpoints.'),
    ('evaluate_manipulation', 'experiments.exp2.evaluate_comparison', (), 'Evaluate the manipulation (exp2) comparison.'),
    ('train_maze', 'experiments.exp3.trajectory_v3.shared_cli', ('train',), 'Train the maze (exp3) shared-morphology planner.'),
    ('evaluate_maze', 'experiments.exp3.trajectory_v3.evaluate_frozen', (), 'Evaluate frozen maze (exp3) plans.'),
    ('train_replanning', 'experiments.exp4.sprint6h.train_adapt', ('train',), 'Train the replanning (exp4) adaptation.'),
    ('evaluate_replanning', 'experiments.exp4.sprint6h.runner', (), 'Run the replanning (exp4) evaluation.'),
    ('train_maze_v4', 'experiments.exp5_maze_v4.train', (), 'Train the maze v4 (exp5) models.'),
    ('evaluate_maze_v4', 'experiments.exp5_maze_v4.evaluate', (), 'Evaluate the maze v4 (exp5) models.'),
    ('report_maze_v4', 'experiments.exp5_maze_v4.report', (), 'Aggregate the maze v4 (exp5) evaluation tables.'),
]

README = '''# CLEAR

Source code and 153 pretrained checkpoints of the CLEAR planner.

- `run_01` to `run_13`: entry points, one per experiment stage (`python run_XX_name.py --help`)
- `clear/`: model, data and planning implementation
- `experiments/`: exp1 grid, exp2 manipulation, exp3 maze, exp4 replanning, exp5 maze v4
- `ckpts/`: `grid/`, `maze/`, `locomotion/`; `docs/checkpoint_paths.json` maps each file to the path the code loads
- `assets/`, `data/`, `tests/`, `tools/`

## Setup (CPU, Python 3.11)

```bash
curl -LO https://anonymous-hf.com/api/a/p5icltdspejh/resolve/get.py
python get.py clear && cd clear
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.7"
python -m pip install numpy einops pyyaml scipy matplotlib imageio-ffmpeg
```

`get.py` downloads the source tree and the checkpoints (1.8 GB, SHA-256 verified) and links them.

## Demo

```bash
python run_01_plan_maze.py --input experiments/exp3/data/example_g1.json                 # plan, then open the window
python run_01_plan_maze.py --input experiments/exp3/data/example_g1.json --video demo.mp4  # headless, writes the mp4
```

Writes `outputs/reproduction/plan.json` and `plan.png`; the animation plays the object interactions, then the route.

## Experiments

| `run_01` demo | `run_02`–`03` exp1 grid | `run_04`–`06` exp2 manipulation |
|---|---|---|
| ![](https://anonymous-hf.com/api/a/p5icltdspejh/resolve/docs/teasers/demo_plan.png) | ![](https://anonymous-hf.com/api/a/p5icltdspejh/resolve/docs/teasers/exp1_grid.png) | ![](https://anonymous-hf.com/api/a/p5icltdspejh/resolve/docs/teasers/exp2_manipulation.png) |

| `run_07`–`08` exp3 maze | `run_09`–`10` exp4 replanning | `run_11`–`13` exp5 maze v4 |
|---|---|---|
| ![](https://anonymous-hf.com/api/a/p5icltdspejh/resolve/docs/teasers/exp3_maze.png) | ![](https://anonymous-hf.com/api/a/p5icltdspejh/resolve/docs/teasers/exp4_replanning.png) | ![](https://anonymous-hf.com/api/a/p5icltdspejh/resolve/docs/teasers/exp5_maze_v4.png) |

`run_03_evaluate_grid.py --method` selects CLEAR or a baseline (`clear`, `clear_ro`, `clear_ho`, `autoregressive`, `gumbel_sinkhorn`, `polynet`).
Physical simulation and the manipulation experiments need the optional extras in `pyproject.toml`.
'''
