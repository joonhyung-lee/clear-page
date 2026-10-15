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
     {'train': ('experiments.common.dispatch', 'train', '--experiment', 'grid2d'), 'evaluate': ('experiments.exp1.evaluate',)}),
    ('manipulation', 'Ordered manipulation (exp2): train the comparison arms, refine the flow checkpoints.',
     {'train': ('experiments.exp2.train_comparison',), 'refine': ('experiments.exp2.refine_flow_comparison',)}),
    ('maze', None, None),
    ('replanning', 'Replanning (exp4): train the adaptation.',
     {'train': ('experiments.exp4.sprint6h.train_adapt', 'train')}),
]


README = '''# CLEAR

> **TL;DR**
>
> Source code and 129 pretrained checkpoints of the CLEAR planner. Download with `get.py`, install with `uv sync`, run one script per experiment.

## 0. Download

```bash
curl -LO https://anonymous-hf.com/api/a/p5icltdspejh/resolve/get.py
python3 get.py clear && cd clear
```

## 1. Install

```bash
uv sync                                           # Python 3.11, CPU torch (pyproject.toml has the CUDA note)
uv sync --extra manipulation                     # adds MuJoCo for 02
```

## 2. Run experiments

```bash
# 01 grid. --method clear | clear_ro | clear_ho | autoregressive | gumbel_sinkhorn | polynet
uv run run_01_grid.py evaluate --method clear --out outputs/grid/clear
uv run run_01_grid.py evaluate --method polynet --out outputs/grid/polynet
uv run run_01_grid.py train --method clear

# 02 ordered manipulation. --arm clear | bc | plan_bc | bc_shared | ar_bc | clear_nocausal | clear_regression | clear_noaffordance
uv run run_02_manipulation.py train --arm clear --data experiments/exp2/data/paper --seed 0 --out outputs/manipulation/clear.pt

# 03 maze. plan one scene (window, or --video demo.mp4), or train the planner
uv run run_03_maze.py plan --input experiments/exp3/data/example_g1.json --video demo.mp4
uv run run_03_maze.py train --help

# 04 long horizon planning. train the replanning adaptation
uv run run_04_replanning.py train --help
```

`<stage> --help` lists every argument. 01 and `03 plan` run from the released checkpoints. Executing plans on the
simulated robots (the paper's physical-success numbers) needs the controller runtime, which is not part of this
distribution; the planners, their training and the grid evaluation are.

## Layout

- `clear/` → planner
  - `model/` → `clear.py` (CLEAR core, PAMO), `ordernet.py`, `causalflownet.py`, `affordancenet.py`, `encoders.py`, `quantizers.py`
  - `data/` → grid scenes, oracle, terrain, capability, probes
  - `maze/` → `world.py` (scenes, routes, abstract controller), `robots.py` (bodies, structure)
  - `util.py` → projection, schedule, ranking, CEM
- `experiments/` → one folder per experiment
  - `exp1/` → grid
  - `exp2/` → manipulation
  - `exp3/` → maze
  - `exp4/` → replanning
- `ckpts/` → pretrained checkpoints
  - `grid/`
  - `maze/`
  - `locomotion/`
  - `paths.json` → where each checkpoint is linked for the code
- `models/` → ordering baselines
- `assets/` → robot models and README figures
- `utils/` → helpers
  - `tools/` → fetch and render
  - `tests/` → unit tests (`uv run pytest utils/tests`)
  - `training/` → training configs and teacher data

## Experiments

| (a) 2D Grid | (b) Ordered Manipulation | (c) Maze Navigation | (d) Long Horizon Planning |
|---|---|---|---|
| ![](https://anonymous-hf.com/api/a/p5icltdspejh/resolve/assets/readme/a_grid.png) | ![](https://anonymous-hf.com/api/a/p5icltdspejh/resolve/assets/readme/b_ordered_manipulation.png) | ![](https://anonymous-hf.com/api/a/p5icltdspejh/resolve/assets/readme/c_maze_navigation.png) | ![](https://anonymous-hf.com/api/a/p5icltdspejh/resolve/assets/readme/d_long_horizon_planning.png) |
| Relocate obstacles to open a path. | Order interactions to keep access. | Plan per body around terrain and objects. | Replan when placement or access changes. |
'''

