"""Evaluate new curriculum milestones without borrowing archived performance."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from export_policy_evaluation import summarize
from watch_spot_curriculum import training_state

ROOT = Path(__file__).resolve().parents[1]


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(path)


def alive(pid):
    path = Path('/proc') / str(pid) / 'stat'
    return path.exists() and not path.read_text().split(') ', 1)[1].startswith('Z ')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--python', type=Path, required=True)
    p.add_argument('--mjlab', type=Path, required=True)
    p.add_argument('--body', choices=['g1', 'spot_arm'], required=True)
    p.add_argument('--public-key', choices=['g1_scratch', 'spot_arm_trial'])
    p.add_argument('--device', default='cuda:0')
    p.add_argument('--consistent-commands', action='store_true')
    p.add_argument('--supervisor', type=Path)
    p.add_argument('--once', action='store_true')
    p.add_argument('--evaluator', type=Path, default=ROOT/'scripts/evaluate_policy_progress.py',
                   help='Explicit evaluator source for private policy-contract comparisons')
    a = p.parse_args()
    lock = (a.run / 'fixed-evaluation.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    plan = read(a.run/'plan.json')
    assert plan['body'] == a.body
    cache_path = a.run/'fixed-evaluations.json'
    code_hash = digest(a.evaluator)
    cache = read(cache_path, {'evaluatorHash': code_hash, 'rows': []})
    assert cache['evaluatorHash'] == code_hash
    env = {**os.environ, 'PYTHONPATH': str(a.mjlab), 'OMP_NUM_THREADS': '4', 'OPENBLAS_NUM_THREADS': '4'}
    while True:
        targets, offset = [], 0
        planned = set()
        for stage in plan['stages']:
            folder = a.run/stage['name']
            files = sorted(folder.glob('update_*.pt'))
            marks = [n for n in [0, 50, 250, 500, 1000, 1500, 2000, 3000, 4000, 5000, stage['updates']] if n <= stage['updates']]
            for mark in sorted(set(marks)):
                planned.add(offset+mark)
                eligible = [f for f in files if int(f.stem.split('_')[1]) >= mark]
                if eligible:
                    checkpoint = eligible[0]
                    update = offset+int(checkpoint.stem.split('_')[1])
                    targets.append({'update': update, 'phase': stage['name'], 'path': str(checkpoint)})
            offset += stage['updates']
        unique = {r['update']: r for r in targets}
        done = {r['update'] for r in cache['rows']}
        pending = [r for update, r in sorted(unique.items()) if update not in done]
        if pending:
            work = a.run/'fixed-evaluation-batches'/f'from-{pending[0]["update"]:06d}'
            work.mkdir(parents=True, exist_ok=True)
            manifest = work/'manifest.json'
            write(manifest, {a.body: pending})
            with (work/'evaluation.log').open('w') as log:
                subprocess.run([str(a.python), str(a.evaluator),
                                '--manifest', str(manifest), '--body', a.body, '--output', str(work),
                                '--device', a.device] + (['--consistent-commands'] if a.consistent_commands else []),
                               cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            result = read(work/(a.body+'.json'))
            reference = cache.get('protocol')
            if reference:
                assert reference == result['identity']['protocol']
            cache['protocol'] = result['identity']['protocol']
            baseline = cache['rows'][0]['episodes'] if cache['rows'] else result['checkpoints'][0]['episodes']
            baseline_hashes = {(e['seed'], e['environment']): e['initialStateHash'] for e in baseline}
            for row in result['checkpoints']:
                assert row['checkpointHash'] == digest(Path(unique[row['update']]['path']))
                assert len(row['episodes']) == 60
                assert {(e['seed'], e['environment']): e['initialStateHash'] for e in row['episodes']} == baseline_hashes
                cache['rows'].append(row)
            cache['rows'].sort(key=lambda row: row['update'])
            write(cache_path, cache)
            print('Evaluated', a.body, [r['update'] for r in result['checkpoints']], flush=True)
        if a.public_key and cache['rows']:
            rows = [{'update': r['update'], 'phase': r['phase'], **summarize(r['episodes'])} for r in cache['rows']]
            payload = {'rows': rows, 'initialization': 'random', 'plannedCheckpoints': len(planned),
                       'trainingState': 'complete' if (a.run/'complete.json').exists() else
                           ('training' if training_state(a) == 'running' else training_state(a)),
                       'complete': (a.run/'complete.json').exists() and max(r['update'] for r in rows) == offset}
            asset = ROOT/'assets'/f'{a.public_key}-evaluation-data.js'
            text = 'window.CLEAR_POLICY_EVALUATION = window.CLEAR_POLICY_EVALUATION || {bodies:{}};\n'
            text += 'window.CLEAR_POLICY_EVALUATION.bodies['+json.dumps(a.public_key)+'] = '+json.dumps(payload, separators=(',', ':'), allow_nan=False)+';\n'
            temp = asset.with_suffix('.tmp');temp.write_text(text);temp.replace(asset)
        if a.once or training_state(a) in ['complete', 'failed', 'stopped']:
            break
        time.sleep(30)


if __name__ == '__main__':
    main()
