"""Run private G1 and Spot+arm training jobs until a shared wall-clock deadline.

No job is silently restarted and no result is automatically published. The
supervisor owns its child process groups and records terminal states explicitly.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from train_progressive_policy import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--deadline', type=float, required=True)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--num-envs', type=int, default=32)
    parser.add_argument('--bodies', nargs='+', choices=['g1', 'spot_arm'], default=['g1', 'spot_arm'])
    parser.add_argument('--critic-observations', choices=['actor', 'native'], default='native')
    parser.add_argument('--action-limit', type=float)
    parser.add_argument('--action-rate-warmup', action='store_true')
    parser.add_argument('--failure-cost', type=float)
    parser.add_argument('--initial-state', type=Path,
                        help='Verified random update-zero state for a single-body comparison')
    parser.add_argument('--actor-normalization', action='store_true')
    parser.add_argument('--forward-locomotion', action='store_true')
    args = parser.parse_args()
    if args.initial_state and len(args.bodies) != 1:
        parser.error('A shared initial state requires exactly one body')
    root = Path(__file__).resolve().parents[1]
    args.output = args.output.resolve()
    if args.output.is_relative_to(root):
        parser.error('Training artifacts must remain outside the published website')
    if args.deadline <= time.time():
        parser.error('Deadline has already passed')
    args.output.mkdir(parents=True, exist_ok=False)
    jobs = []
    environment = os.environ.copy()
    environment.update(PYTHONDONTWRITEBYTECODE='1', MPLCONFIGDIR=str(args.output / 'matplotlib'),
                       OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4', WANDB_MODE='disabled')
    try:
        for body, budgets in [('g1', [6000, 12000, 0]), ('spot_arm', [3000, 6000, 4000])]:
            if body not in args.bodies:
                continue
            folder = args.output / body
            folder.mkdir()
            stream = (args.output / f'{body}.log').open('w')
            command = [sys.executable, str(root / 'scripts/train_progressive_policy.py'),
                       '--output', str(folder), '--body', body, '--device', args.device,
                       '--num-envs', str(args.num_envs), '--budgets', *map(str, budgets),
                       '--critic-observations', args.critic_observations]
            if args.action_limit is not None:
                command += ['--action-limit', str(args.action_limit)]
            if args.action_rate_warmup:
                command += ['--action-rate-warmup']
            if args.failure_cost is not None:
                command += ['--failure-cost', str(args.failure_cost)]
            if args.initial_state:
                command += ['--initial-state', str(args.initial_state.resolve())]
            if args.actor_normalization:
                command += ['--actor-normalization']
            if args.forward_locomotion:
                command += ['--forward-locomotion']
            process = subprocess.Popen(command, env=environment, cwd=root, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            write_json(folder / 'process.json', {'pid': process.pid, 'deadline': args.deadline})
            jobs.append({'body': body, 'folder': folder, 'process': process, 'stream': stream})
        last_print = 0
        while True:
            now = time.time()
            reports = []
            for job in jobs:
                process, folder = job['process'], job['folder']
                # Explicit private control requests affect only this owned job.
                request = folder / 'stop-request.json'
                if request.exists() and process.poll() is None:
                    reason = json.loads(request.read_text()).get('reason', 'requested stop')
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    write_json(folder / 'supervisor-stop.json', {'stoppedAt': time.time(),
                        'reason': reason, 'exitCode': process.returncode})
                exit_code = process.poll()
                state = 'running' if exit_code is None else 'stopped' if (folder/'supervisor-stop.json').exists() else 'complete' if exit_code == 0 and (folder/'complete.json').exists() else 'failed'
                stages = {}
                for phase in ['locomotion', 'terrain', 'arm']:
                    path = folder / phase / 'status.json'
                    if path.exists():
                        stages[phase] = json.loads(path.read_text())
                reports.append({'body': job['body'], 'pid': process.pid, 'state': state,
                                'exitCode': exit_code, 'stages': stages})
            write_json(args.output / 'supervisor.json', {'updatedAt': now,
                'deadline': args.deadline, 'device': args.device, 'numEnvironments': args.num_envs,
                'jobs': reports})
            if now - last_print >= 60 or all(r['state'] != 'running' for r in reports):
                print(json.dumps({'remainingHours': round(max(0, args.deadline-now)/3600, 2),
                    'jobs': [{'body': r['body'], 'state': r['state'], 'updates':
                              {k: v.get('completed_updates', 0) for k, v in r['stages'].items()}}
                             for r in reports]}), flush=True)
                last_print = now
            if all(r['state'] != 'running' for r in reports):
                return
            if now >= args.deadline:
                print('Authorized wall-clock deadline reached; stopping owned training jobs.', flush=True)
                return
            time.sleep(min(10, args.deadline-now))
    finally:
        for job in jobs:
            process = job['process']
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                write_json(job['folder'] / 'supervisor-stop.json',
                           {'stoppedAt': time.time(), 'reason': 'deadline' if time.time() >= args.deadline else 'supervisor interrupted',
                            'exitCode': process.returncode})
            job['stream'].close()


if __name__ == '__main__':
    main()
