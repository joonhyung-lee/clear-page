"""Record, audit and publish all three upright variants from one fixed checkpoint."""
import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--project', type=Path, required=True)
p.add_argument('--checkpoint', type=Path, required=True)
p.add_argument('--runs', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--native-python', type=Path, required=True)
p.add_argument('--wait-seconds', type=float, default=0)
p.add_argument('--private-term', action='append', required=True,
               help='Private identifier to reject; repeat for each author or institution. Never stored in reports.')
p.add_argument('--motor-validation', type=Path, required=True,
               help='Passing empty-floor upright motor response report, before expensive task recordings')
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
a.runs.mkdir(parents=True, exist_ok=False)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', MUJOCO_GL='egl', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2')
status_file = a.runs/'rebuild-status.json'
def status(stage, **fields):
    value = dict(stage=stage, **fields)
    status_file.write_text(json.dumps(value, indent=2)+'\n')
    print(json.dumps(value), flush=True)
def command(script, *args, native=True):
    return [str(a.native_python) if native else sys.executable, str(root/'scripts'/script), *map(str,args)]
def run(script, *args, native=True):
    subprocess.run(command(script,*args,native=native), cwd=root, env=env, check=True)

jobs = []
def terminate(signum, frame):
    raise KeyboardInterrupt('Rebuild interrupted')
signal.signal(signal.SIGTERM, terminate)
try:
    motor = json.loads(a.motor_validation.read_text())
    if not motor.get('qualified') or not motor.get('arm_reference_sha256') or motor.get('crouch_offsets') is not False:
        raise RuntimeError('The upright motor has not passed measured forward/stop/reverse validation without crouch offsets')
    if motor.get('arm_observation') != 'relative' or motor.get('gravity_support'):
        raise RuntimeError('Motor validation does not match the current upright runtime settings')
    import hashlib
    import ast
    arm_tree = ast.parse((a.project/'clear/maze/fixed_palm.py').read_text())
    arm_pose = ast.literal_eval(next(node.value for node in arm_tree.body
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PALM_JOINTS' for t in node.targets)))
    if hashlib.sha256(json.dumps(arm_pose, sort_keys=True).encode()).hexdigest() != motor['arm_reference_sha256']:
        raise RuntimeError('Motor validation used a different arm posture')
    motor_file = a.project/'assets/pretrained/g1/locomotion/g1_sumo_flat.onnx'
    if hashlib.sha256(motor_file.read_bytes()).hexdigest() not in motor.get('checkpoints', {}).values():
        raise RuntimeError('Motor validation used a different walker checkpoint')
    status('waiting_for_fixed_checkpoint')
    deadline = time.monotonic()+a.wait_seconds
    def checkpoint_ready():
        try:
            report = json.loads((a.checkpoint.parent/'training.json').read_text())
            return a.checkpoint.exists() and report.get('status', '').startswith('complete;')
        except (FileNotFoundError, json.JSONDecodeError):
            return False
    while not checkpoint_ready():
        if time.monotonic() >= deadline:
            raise RuntimeError('Fixed final checkpoint is not available')
        time.sleep(5)
    # A checkpoint is written to a temporary path and atomically renamed by
    # the trainer. No partial checkpoint is ever admitted here.
    status('checking_initial_plan')
    shared = ['--project', a.project, '--checkpoint', a.checkpoint, '--device', 'cpu', '--wall-multiplier', '20']
    probe = a.runs/'plan-validation'
    run('record_replanning_comparison.py', *shared, '--method', 'naive', '--out', probe, '--plan-only')
    plan = json.loads((probe/'probe-plan.json').read_text())['plan']
    if not plan['paths']:
        raise RuntimeError('The adapted checkpoint did not produce an admitted plan for the fixed comparison scene')
    status('recording_native_physics', methods=['naive','replan','inpainting'])
    for method in ['naive','replan','inpainting']:
        log = (a.runs/f'{method}.log').open('w')
        proc = subprocess.Popen(command('record_replanning_comparison.py', *shared, '--method', method,
                                        '--out', a.runs/method), cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        jobs.append((method,proc,log))
    for method,proc,log in jobs:
        code = proc.wait()
        log.close()
        if code:
            raise RuntimeError(f'{method} recording exited with code {code}; inspect its log')
    outcomes = {method: json.loads((a.runs/method/'episode.json').read_text())
                for method, _, _ in jobs}
    measured = {method: {key: episode[key] for key in
                         ('status', 'task_success', 'strict_success', 'successful_macros', 'elapsed_sim_s')}
                for method, episode in outcomes.items()}
    (a.runs/'performance-gate.json').write_text(json.dumps(measured, indent=2)+'\n')
    if not any(episode['strict_success'] for episode in outcomes.values()):
        raise RuntimeError('No method completed the physical task under the strict audit. Keep diagnostics; do not publish this batch as the rebuilt demonstration.')
    status('auditing_and_rendering')
    run('finish_replanning_comparison.py', '--runs', a.runs, '--output', a.output,
        '--native-python', a.native_python, '--viser-python', sys.executable, native=False)
    import imageio_ffmpeg
    run('check_replanning_delivery.py', '--runs', a.runs, '--output', a.output,
        '--ffmpeg', imageio_ffmpeg.get_ffmpeg_exe(), native=False)
    manifest = json.loads((a.output/'manifest.json').read_text())
    private_roots = [str(Path('/') / name) + '/' for name in ('home', 'mnt')]
    forbidden = tuple(term.lower() for term in [getpass.getuser(), *a.private_term, *private_roots])
    # Inspect Viser's decompressed message strings as well as readable sidecars.
    sys.path.insert(0, str(root/'scripts'))
    from recording_io import read_recording
    for entry in manifest.values():
        record, _ = read_recording(a.output/entry['viser'])
        content = json.dumps(record, default=str).lower()
        assert not any(term in content for term in forbidden), 'Identity/path text in Viser recording'
    for file in a.output.rglob('*.json'):
        assert not any(term in file.read_text().lower() for term in forbidden), f'Identity/path text in {file.name}'
    page = root/'replanning/index.html'
    text = page.read_text()
    import re
    text = re.sub(r'  <p id="pending" role="status">[^<]*</p>\n', '', text)
    text = text.replace('<button disabled ', '<button ').replace('<footer hidden>', '<footer>')
    text = text.replace('<video hidden controls playsinline preload="none"', '<video controls playsinline preload="metadata" poster="videos-upright/naive/frame-0000.png" src="videos-upright/naive/replanning-multiview.mp4"')
    page.write_text(text)
    readme = root/'replanning/README.md'
    text = readme.read_text().replace('All three methods are being recorded again', 'All three methods were recorded again').replace('The planner is being adapted', 'The planner was adapted')
    text = text.replace('Recording is paused\nuntil the motor passes physical qualification. Existing upright outputs are\nincomplete diagnostic artifacts, not a completed comparison.',
                        'The current batch passed the motor qualification and task publication gates. Individual outcomes are listed below.')
    text += '\n## Recorded outcomes\n\n'
    for method, entry in manifest.items():
        text += f"- {method}: {entry['status']}, {entry['recordedSeconds']:.1f} simulation seconds, {entry['planningCalls']} planning calls.\n"
    readme.write_text(text)
    status('complete', methods=manifest)
except BaseException as exc:
    status('failed', error=str(exc), published=False)
    for _,proc,log in jobs:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
        if not log.closed:
            log.close()
    raise
