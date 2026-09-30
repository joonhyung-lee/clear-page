"""Advance the controlled armed trial only after measured flat-ground walking.

Runs privately. A failed gate requests review instead of treating an exhausted
training budget as a learned skill. Existing checkpoint directories are retained.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from watch_progressive_evaluation import alive, read, write

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--python', type=Path, required=True)
    p.add_argument('--mjlab', type=Path, required=True)
    a = p.parse_args()
    original = read(a.run/'process.json')['pid']
    assert alive(original), 'The initial training process must still be running'
    assert 'initialTrainingPid' not in read(a.run/'process.json'), 'A supervisor already owns this trial'
    write(a.run/'process.json', {'pid': os.getpid(), 'initialTrainingPid': original})
    env = {**os.environ, 'PYTHONPATH': str(a.mjlab), 'OMP_NUM_THREADS': '4',
           'OPENBLAS_NUM_THREADS': '4', 'MJLAB_SPOT_TORSO_W': '0'}
    stages = [('locomotion', 3000), ('terrain', 6000), ('arm', 4000)]
    offset = 0
    for stage, budget in stages:
        target = offset+budget
        while True:
            status = read(a.run/stage/'status.json', {})
            if status.get('state') == 'complete' and status.get('completed_updates') == budget:
                break
            current_pid = original if stage == 'locomotion' else process.pid
            if not alive(current_pid):
                write(a.run/'review-needed.json', {'stage': stage, 'reason': 'Training stopped before its budget completed'})
                return
            time.sleep(15)
        latest = read(a.run/stage/'latest.json')
        checkpoint = Path(latest['checkpoint'])
        assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == latest['sha256']
        while True:
            evaluation = read(a.run/'fixed-evaluations.json', {'rows': []})
            final = next((r for r in evaluation['rows'] if r['update'] == target), None)
            if final:
                break
            watcher = read(a.run/'evaluation-process.json', {}).get('pid')
            if not alive(watcher):
                write(a.run/'review-needed.json', {'stage': stage, 'reason': 'Evaluation watcher stopped'})
                return
            time.sleep(15)
        flat = [e for e in final['episodes'] if e['terrain'] == 'flat']
        successes = sum(e['success'] for e in flat)
        write(a.run/(stage+'-gate.json'), {'update': target, 'flatSuccesses': successes,
              'flatEpisodes': len(flat), 'requiredSuccesses': 8,
              'protocol': '3 m forward traverse within 20 s, without a fall',
              'passed': len(flat) == 12 and successes >= 8})
        if len(flat) != 12 or successes < 8:
            write(a.run/'review-needed.json', {'stage': stage, 'reason': 'Flat-ground walking gate not reached',
                                             'successes': successes, 'episodes': len(flat)})
            return
        if stage == 'arm':
            write(a.run/'complete.json', {'updates': target, 'checkpoint': str(checkpoint), 'completed_at': time.time()})
            return
        next_stage, next_budget = stages[stages.index((stage, budget))+1]
        assert not (a.run/next_stage).exists(), 'Do not overwrite an existing stage'
        plan = read(a.run/'plan.json')
        plan['stages'].append({'name': next_stage, 'updates': next_budget})
        write(a.run/'plan.json', plan)
        # The previous watcher finished its final batch before the gate exists.
        watcher = read(a.run/'evaluation-process.json')['pid']
        if alive(watcher):
            os.kill(watcher, signal.SIGTERM)
        log = (a.run/(next_stage+'.log')).open('w')
        process = subprocess.Popen([str(a.python), str(ROOT/'scripts/train_spot_curriculum.py'),
                      '--output', str(a.run), '--body', 'spot_arm',
                      '--stage', next_stage, '--updates', str(next_budget), '--offset', str(target),
                      '--parent', str(checkpoint), '--num-envs', '512', '--seed', '42'],
                      cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        watch_log = (a.run/'evaluation-watch.log').open('a')
        worker = subprocess.Popen([sys.executable, str(ROOT/'scripts/watch_progressive_evaluation.py'),
                      '--run', str(a.run), '--body', 'spot_arm', '--python', str(a.python),
                      '--mjlab', str(a.mjlab)], cwd=ROOT, stdout=watch_log, stderr=subprocess.STDOUT)
        write(a.run/'evaluation-process.json', {'pid': worker.pid})
        offset = target


if __name__ == '__main__':
    main()
