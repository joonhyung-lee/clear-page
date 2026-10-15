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
    # (name, docstring, {stage: (module, *prefix)}); run_03_maze.py is a hand-written template with a `plan` demo stage.
    ('grid', 'Grid (exp1): train the models, or evaluate CLEAR / an ordering baseline (--method clear | clear_ro | clear_ho | autoregressive | gumbel_sinkhorn | polynet).',
     {'train': ('scripts.train', '--experiment', 'grid2d'), 'evaluate': ('evaluation.exp1',)}),
    ('manipulation', 'Ordered manipulation (exp2): train the comparison arms, refine the flow checkpoints, evaluate the comparison.',
     {'train': ('experiments.exp2.train_comparison',), 'refine': ('experiments.exp2.refine_flow_comparison',), 'evaluate': ('experiments.exp2.evaluate_comparison',)}),
    ('maze', None, None),
    ('replanning', 'Replanning (exp4): train the adaptation, run the evaluation.',
     {'train': ('experiments.exp4.sprint6h.train_adapt', 'train'), 'evaluate': ('experiments.exp4.sprint6h.runner',)}),
    ('maze_v4', 'Maze v4 (exp5): train, evaluate, aggregate the evaluation tables.',
     {'train': ('experiments.exp5_maze_v4.train',), 'evaluate': ('experiments.exp5_maze_v4.evaluate',), 'report': ('experiments.exp5_maze_v4.report',)}),
]


README = '''# CLEAR

Source code and 153 pretrained checkpoints of the CLEAR planner.

- `run_01_grid.py` to `run_05_maze_v4.py`: one entry point per experiment, `python run_0N_name.py <stage> [args]` (`<stage> --help` lists the arguments): grid `train|evaluate`, manipulation `train|refine|evaluate`, maze `plan|train|evaluate`, replanning `train|evaluate`, maze_v4 `train|evaluate|report`
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

`get.py` downloads the source tree and the checkpoints (1.8 GB, SHA-256 verified) and links them. Physical simulation and the manipulation experiments need the optional extras in `pyproject.toml`.

## Demo

```bash
python run_03_maze.py plan --input experiments/exp3/data/example_g1.json                 # plan, then open the window
python run_03_maze.py plan --input experiments/exp3/data/example_g1.json --video demo.mp4  # headless, writes the mp4
```

Writes `outputs/reproduction/plan.json` and `plan.png`; the animation plays the object interactions, then the route.

## Experiments

| (a) 2D Grid | (b) Ordered Manipulation | (c) Maze Navigation | (d) Long Horizon Planning |
|---|---|---|---|
| ![](https://anonymous-hf.com/api/a/p5icltdspejh/resolve/docs/teasers/a_grid.png) | ![](https://anonymous-hf.com/api/a/p5icltdspejh/resolve/docs/teasers/b_ordered_manipulation.png) | ![](https://anonymous-hf.com/api/a/p5icltdspejh/resolve/docs/teasers/c_maze_navigation.png) | ![](https://anonymous-hf.com/api/a/p5icltdspejh/resolve/docs/teasers/d_long_horizon_planning.png) |
| Select and relocate obstacles to connect start and goal. | Order interactions so later objects remain accessible. | Plan around terrain and movable objects for each body. | Update the plan when object placement or access changes. |
'''
