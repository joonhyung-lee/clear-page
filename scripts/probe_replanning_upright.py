"""Run one actual upright interaction before recording the full comparison."""
import argparse
import json
import hashlib
import os
from pathlib import Path
import sys

p = argparse.ArgumentParser()
p.add_argument('--project', type=Path, required=True)
p.add_argument('--plan', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--seed', type=int, required=True)
p.add_argument('--worlds', type=int, default=16)
p.add_argument('--guide-only', action='store_true', help='Diagnostic isolation of base/palm guide; not the full MPC comparison')
a = p.parse_args()
root = a.project.resolve()
a.out = a.out.resolve()
a.out.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(root))
os.chdir(root)
os.environ.setdefault('XDG_CACHE_HOME', '/tmp/clear-replanning-cache')
os.environ.setdefault('MJLAB_PUSH_LOWLEVEL_ONNX', str(root/'assets/pretrained/g1/locomotion/g1_sumo_flat.onnx'))
from experiments.exp4.sprint6h import physics_client
from experiments.exp4.sprint6h.runner_lh import seeds_for
from replanning_upright_profile import PROFILE, PROFILE_SHA256
physics_client.SERVER = Path(__file__).with_name('replanning_upright_server.py').resolve()
plan = json.loads(a.plan.read_text())
assert plan['plan']['paths'], 'Cannot physically validate an empty plan'
controller = json.loads((root/'controllers/v4/paper_g1_v4.json').read_text())
world = physics_client.PhysicsWorld(controller, 'cpu', a.out/'server.log', wall_timeout_s=4800)
try:
    _, seed = seeds_for(plan['row']['scene'], a.seed)
    initial = world.init(dict(scene=plan['row']['scene'], body_id='g1', split='development',
                             diagnostic_guide_only=a.guide_only), seed, a.worlds, a.out/'physics')
    (a.out/'runtime.json').write_text(json.dumps(initial['config'], indent=2)+'\n')
    assert initial['config']['low_contact_profile'] is None
    profile = initial['config']['runtime_profile']
    assert initial['config']['runtime_profile_sha256'] == hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()
    if not a.guide_only:
        assert initial['config']['runtime_profile_sha256'] == PROFILE_SHA256
    assert initial['config']['guide_only'] == a.guide_only
    print('PASS upright motor and forward-facing palm reference initialized', flush=True)
    result = world.request('macro', path=plan['plan']['paths'][0], deadline_s=120.)
    world.request('save', result=dict(status='upright_first_interaction_probe', interaction=result),
                  config=dict(runtime_profile=profile, scope='Single-interaction physical validation only',
                              diagnostic_guide_only=a.guide_only, diagnostic_worlds=a.worlds))
    (a.out/'probe-result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:result.get(k) for k in ['success','stage','failure_type','end_time_s','object_pose_after']}), flush=True)
finally:
    world.close()

if not result['success']:
    raise SystemExit(1)
