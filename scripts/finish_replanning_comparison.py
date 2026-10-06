"""Package each completed native run into a Viser recording and multiview MP4."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--runs', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--native-python', type=Path, required=True)
p.add_argument('--viser-python', type=Path, required=True)
p.add_argument('--wait-seconds', type=float, default=0)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
titles = {'naive': 'CLEAR · Naive', 'replan': 'CLEAR · Replanning', 'inpainting': 'CLEAR · Causal inpainting'}
todo = set(titles)
deadline = time.monotonic()+a.wait_seconds
result = {}
a.output.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, MUJOCO_GL='egl', PYTHONDONTWRITEBYTECODE='1')

def run(python, name, *args):
    subprocess.run([str(python), str(root/'scripts'/name), *map(str, args)], cwd=root, env=env, check=True)

while todo:
    for method in titles:
        if method not in todo:
            continue
        folder = a.runs/method
        source = folder/'episode.json'
        try:
            episode = json.loads(source.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        if not (folder/'capture-complete.json').exists():
            continue
        if episode['status'] == 'infrastructure_error':
            result[method] = dict(status='infrastructure_error', video=None)
            todo.remove(method)
            print('FAILED native runtime', method, flush=True)
            continue
        assert episode.get('runtime_profile', {}).get('name') == 'upright-bilateral-palms-v1', 'Deprecated crouched recording'
        prepared = folder/'prepared'
        output = a.output/method
        run(a.native_python, 'check_replanning_upright.py', '--physics', folder/'physics', '--output', folder/'upright-validation')
        run(a.native_python, 'prepare_replanning_native.py', '--run', folder, '--output', prepared, '--title', titles[method])
        run(a.viser_python, 'export_replanning_viser.py', '--source', prepared, '--output', output/f'{method}.viser')
        run(a.native_python, 'render_replanning_multiview.py', '--source', prepared, '--telemetry', folder, '--output', output)
        path = output/'replanning-multiview.mp4'
        result[method] = dict(status=episode['status'], strictSuccess=episode['strict_success'],
            video=f'{method}/{path.name}', viser=f'{method}/{method}.viser',
            videoSHA256=hashlib.sha256(path.read_bytes()).hexdigest(), episodeSHA256=hashlib.sha256(source.read_bytes()).hexdigest(),
            nativeMethod=episode['method'], repair=episode.get('repair', 0),
            repairMode=episode.get('repair_mode'), initialPlanHash=episode['initial_plan_hash'],
            sceneHash=episode['initial_scene_hash'], checkpointSHA256=episode['checkpoint_sha256'],
            planningCalls=episode['planning_calls'], recordedSeconds=episode['elapsed_sim_s'],
            candidateCount=episode['candidates'], fallback=episode['fallback_residual'])
        result[method].update(runtimeProfile=episode['runtime_profile'],
                              runtimeProfileSHA256=episode['runtime_profile_sha256'])
        todo.remove(method)
        print('PACKAGED', method, path, flush=True)
        (a.output/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    if todo:
        if time.monotonic() >= deadline:
            raise SystemExit('Still waiting for native results: '+', '.join(sorted(todo)))
        time.sleep(5)
(a.output/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
if any(row['video'] is None for row in result.values()):
    raise SystemExit('One or more native runs failed. No replacement motion was rendered.')
assert len({row['initialPlanHash'] for row in result.values()}) == 1
assert len({row['sceneHash'] for row in result.values()}) == 1
print('PASS three native methods packaged from the same initial scene and plan', flush=True)
