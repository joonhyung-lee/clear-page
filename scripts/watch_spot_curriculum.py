"""Export anonymous progress and fixed-bank replays from a private curriculum run.

This local watcher never starts or restarts training. It publishes only a small
allowlist of training counters and newly evaluated geometry, without run paths,
machine names, checkpoint metadata or TensorBoard event files.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
LABELS = {'initialization': 'Initialization', 'locomotion': 'Locomotion',
          'terrain': 'Terrain adaptation', 'arm': 'Arm adaptation'}


def read(path, fallback=None):
    return json.loads(path.read_text()) if path.exists() else fallback


def alive(pid):
    try:
        os.kill(pid, 0)
        stat = Path(f'/proc/{pid}/stat').read_text().split()
        return stat[2] != 'Z'
    except (ProcessLookupError, FileNotFoundError, TypeError):
        return False


def training_state(args):
    """Use the owning supervisor across PID namespaces, never a guessed PID."""
    if getattr(args, 'supervisor', None):
        if (args.run / 'supervisor-stop.json').exists():
            return 'stopped'
        report = read(args.supervisor, {})
        job = next((job for job in report.get('jobs', []) if job['body'] == args.body), {})
        state = job.get('state', 'unknown')
        if state == 'running' and time.time() - report.get('updatedAt', 0) > 90:
            return 'unknown'
        return state
    process = read(args.run / 'process.json', {})
    return 'running' if alive(process.get('pid')) else 'stopped'


def publish(args, plan, cache):
    # A new history must not be paired with the previous run's initial replay.
    if not cache.get('initialization'):
        return
    run_state = training_state(args)
    offset = 0
    initial = cache.get('initialization')
    stages = [{'id': 'initialization', 'label': LABELS['initialization'],
               'state': 'complete' if initial else 'preparing', 'updates': 0,
               'cumulativeUpdates': 0, 'targetUpdates': 0, 'replay': initial}]
    for stage in plan['stages']:
        name, target = stage['name'], stage['updates']
        status = read(args.run / name / 'status.json', {})
        state = status.get('state', 'pending')
        if state == 'training' and run_state != 'running':
            state = run_state if run_state in ['failed', 'stopped'] else 'unknown'
        stages.append({'id': name, 'label': LABELS[name], 'state': state,
                       'updates': status.get('completed_updates', 0),
                       'cumulativeUpdates': offset + status.get('completed_updates', 0),
                       'targetUpdates': target, 'replay': cache.get(name)})
        offset += target
    curves = read_curves(args.run, plan)
    payload = {'schema': 2, 'body': args.body, 'numEnvironments': plan['num_envs'],
               'curves': curves,
               'stages': stages, 'updatedAt': int(time.time()),
               'complete': (args.run / 'complete.json').exists()}
    out = ROOT / f'assets/{args.body}-curriculum-data.js'
    temp = out.with_suffix('.tmp')
    temp.write_text('window.CLEAR_BODY_CURRICULA = window.CLEAR_BODY_CURRICULA || {};\n'
                   'window.CLEAR_BODY_CURRICULA[' + json.dumps(args.body) + '] = ' + json.dumps(payload) + ';\n')
    temp.replace(out)


def read_curves(run, plan):
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    curves, curve_offset = [], 0
    for stage in plan['stages']:
        folder = run / stage['name']
        if folder.exists():
            events = EventAccumulator(str(folder), size_guidance={'scalars': 0})
            events.Reload()
            tags = events.Tags()['scalars']
            rows = {}
            for key, tag in [('return', 'Train/mean_reward'), ('value', 'Loss/value'),
                             ('tracking', 'Metrics/twist/error_vel_xy'),
                             ('policy', 'Loss/surrogate'), ('entropy', 'Loss/entropy'),
                             ('terrain', 'Curriculum/terrain_levels/mean'),
                             ('arm', 'Curriculum/arm_stow/mean')]:
                if tag in tags:
                    for item in events.Scalars(tag):
                        rows.setdefault(item.step, {'update': curve_offset + item.step + 1,
                                                    'stage': stage['name']})[key] = item.value
            values = sorted(rows.values(), key=lambda row: row['update'])
            # Retain every logged update: stride sampling can hide short loss
            # spikes, sign reversals and the onset of numerical instability.
            curves.extend(values)
        curve_offset += stage['updates']
    return curves


def evaluate(args, name, checkpoint, cumulative):
    number = int(checkpoint.stem.split('_')[1])
    scene = f'learning-{args.body}-{args.scene_prefix}-{name}-{number:06d}'
    work = args.run / 'web-replays' / scene
    work.mkdir(parents=True, exist_ok=True)
    manifest = work / 'manifest.json'
    body = args.body
    manifest.write_text(json.dumps({body: [{'iteration': cumulative,
                                             'checkpoint': str(checkpoint)}]}))
    env = os.environ.copy()
    env.update(PYTHONPATH=str(args.mjlab), OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4')
    commands = [
        [str(args.python), str(ROOT / 'scripts/record_learning_checkpoints.py'),
         '--manifest', str(manifest), '--body', body, '--output', str(work),
         '--initial-frame', '--deterministic', '--device', args.device]
         + (['--consistent-commands'] if args.consistent_commands else [])
         + (['--bare-spot'] if body == 'spot' else []),
        [sys.executable, str(ROOT / 'scripts/export_learning_checkpoints.py'),
         str(work), '--body', body, '--scene', scene, '--output-dir', str(work / 'recordings')],
        [sys.executable, str(ROOT / 'scripts/check_learning_asset.py'),
         '--source', str(work), '--body', body, '--asset', str(work / 'recordings' / f'{scene}.hex.js')],
        [sys.executable, str(ROOT / 'scripts/render_learning_posters.py'),
         '--body', body, '--scene', scene, '--recordings-dir', str(work / 'recordings'),
         '--output-dir', str(work / 'media')],
    ]
    with (work / 'export.log').open('a') as log:
        for command in commands:
            subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
    for folder, suffix in [('recordings', '.hex.js'), ('media', '.png')]:
        out = ROOT / 'assets' / folder / (scene + suffix)
        temp = out.with_suffix(out.suffix + '.tmp')
        shutil.copyfile(work / folder / (scene + suffix), temp)
        temp.replace(out)
    return {'scene': scene, 'completedUpdates': number, 'cumulativeUpdates': cumulative,
            'duration': 8, 'startsBeforeAction': True,
            'body': body,
            'evaluation': ('G1 policy from random initialization on the fixed terrain bank' if body == 'g1' else 'Arm-free Spot policy on the fixed terrain bank' if body == 'spot' else 'Spot + arm policy with nominal arm pose on the fixed terrain bank')}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True, type=Path)
    p.add_argument('--python', required=True, type=Path)
    p.add_argument('--mjlab', required=True, type=Path)
    p.add_argument('--once', action='store_true')
    p.add_argument('--body', choices=['g1', 'spot', 'spot_arm'], required=True)
    p.add_argument('--device', default='cuda:0')
    p.add_argument('--consistent-commands', action='store_true')
    p.add_argument('--scene-prefix', default='scratch')
    p.add_argument('--supervisor', type=Path)
    args = p.parse_args()
    if not args.scene_prefix.replace('-', '').isalnum():
        p.error('Scene prefix must contain only letters, digits and hyphens')
    lock = (args.run / 'web-export.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    plan = read(args.run / 'plan.json')
    if plan.get('body', 'spot_arm') != args.body:
        p.error('Run physics does not match the requested body')
    cache_path = args.run / f'web-replays-{args.body}.json'
    cache = read(cache_path, {})
    while True:
        publish(args, plan, cache)
        choices = [('initialization', args.run / 'locomotion/update_000000.pt', 0)]
        offset = 0
        for stage in plan['stages']:
            name, target = stage['name'], stage['updates']
            latest = read(args.run / name / 'latest.json')
            if latest:
                # Keep early learning visible without evaluating every save.
                milestones = [n for n in [50, 500, 1000, target] if n <= latest['completed_updates']]
                checkpoints = sorted((args.run / name).glob('update_*.pt'))
                if milestones:
                    eligible = [c for c in checkpoints if int(c.stem.split('_')[1]) >= max(milestones)]
                    if eligible:
                        chosen = eligible[0]
                        choices.append((name, chosen, offset + int(chosen.stem.split('_')[1])))
            offset += target
        for name, checkpoint, cumulative in choices:
            if not checkpoint.exists() or cache.get(name, {}).get('cumulativeUpdates', -1) >= cumulative:
                continue
            try:
                cache[name] = evaluate(args, name, checkpoint, cumulative)
                cache_path.write_text(json.dumps(cache, indent=2) + '\n')
                publish(args, plan, cache)
            except subprocess.CalledProcessError as error:
                print(f'Export failed for {name}: {error}. See private export.log.', flush=True)
        if args.once:
            break
        if training_state(args) in ['complete', 'failed', 'stopped']:
            publish(args, plan, cache)
            break
        time.sleep(30)


if __name__ == '__main__':
    main()
