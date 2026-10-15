"""Maze (exp3): plan one scene and show it, train the shared-morphology planner, or evaluate frozen plans."""
import argparse
import sys
from pathlib import Path

from _run import main, run


def plan(argv):
    parser = argparse.ArgumentParser(prog='run_03_maze.py plan', description='Plan one maze scene, then show the plan in a window (default) or write it to an mp4 (--video).',
                                     epilog='Other arguments go to the planner (--checkpoint, --input, --device, ...).')
    parser.add_argument('--video', metavar='FILE.mp4', help='write the animation headless instead of opening a window')
    parser.add_argument('--no-show', action='store_true', help='plan only')
    args, planner = parser.parse_known_args(argv)
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
    if args.no_show:
        return
    sys.path.insert(0, 'tools')
    from render_plan import show
    png = str(Path(out).with_suffix('.png'))
    scene = planner[planner.index('--input') + 1]
    show(scene, out, video=args.video, png=png)
    print('wrote', png)
    if not args.video:
        show(scene, out)   # interactive window; headless hosts get a hint to use --video


main({
    'plan': plan,
    'train': ('experiments.exp3.trajectory_v3.shared_cli', 'train'),
    'evaluate': ('experiments.exp3.trajectory_v3.evaluate_frozen',),
})
