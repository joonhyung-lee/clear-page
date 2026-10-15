"""Plan one maze scene, then show the plan in a window (default) or write it to an mp4 (--video)."""
import argparse
import sys
from pathlib import Path

from _run import run

parser = argparse.ArgumentParser(description=__doc__, epilog='Other arguments go to the planner (--checkpoint, --input, --device, ...).')
parser.add_argument('--video', metavar='FILE.mp4', help='write the animation headless instead of opening a window')
parser.add_argument('--no-show', action='store_true', help='plan only')
args, planner = parser.parse_known_args()
if '--out' not in planner:
    planner += ['--out', 'outputs/reproduction/plan.json']
if '--checkpoint' not in planner:
    planner += ['--checkpoint', 'ckpts/maze/reference/seed0/clear.pt']
out = planner[planner.index('--out') + 1]
Path(out).unlink(missing_ok=True)   # the planner refuses to overwrite; the demo always re-plans
try:
    run('experiments.exp3.trajectory_v3.shared_cli', 'plan', argv=planner)
except SystemExit as exit:
    if exit.code:
        raise
if not args.no_show:
    sys.path.insert(0, 'tools')
    from render_plan import show
    png = str(Path(out).with_suffix('.png'))
    show(planner[planner.index('--input') + 1], out, video=args.video, png=png)
    print('wrote', png)
    if not args.video:
        show(planner[planner.index('--input') + 1], out)   # interactive window; headless hosts get a hint to use --video
