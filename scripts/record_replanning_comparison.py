"""Run one pinned CLEAR method with passive plan, flow and attention telemetry.

Naive means CLEAR without replanning, not the low-level MPC baseline.
The deprecated crouched posture is replaced by the same upright-palm physical
variant for all methods. Planning algorithms and candidate budgets are unchanged.
"""
import argparse
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--project', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--method', choices=['naive', 'replan', 'inpainting'], required=True)
p.add_argument('--device', default='cuda:0')
p.add_argument('--family', type=int, default=506)
p.add_argument('--seed', type=int, default=0)
p.add_argument('--cell', choices=['D6', 'P6', 'N6'], default='D6')
p.add_argument('--wall-multiplier', type=float, default=1.)
p.add_argument('--plan-only', action='store_true', help='Validate instrumentation on initial inference without physics')
p.add_argument('--checkpoint', type=Path, help='Explicit development checkpoint, shared by all comparison methods')
p.add_argument('--probe-replay', type=Path, help='With plan-only, also validate repair on an archived observed state')
a = p.parse_args()
root = a.project.resolve()
a.out = a.out.resolve()
a.out.mkdir(parents=True, exist_ok=True)
if (a.out / 'episode.json').exists():
    raise SystemExit('An episode already exists here. Use another output directory.')
os.environ.setdefault('MUJOCO_GL', 'egl')
os.environ.setdefault('PYOPENGL_PLATFORM', 'egl')
os.environ.setdefault('MJLAB_PUSH_LOWLEVEL_ONNX', str(root / 'assets/pretrained/g1/locomotion/g1_sumo_flat.onnx'))
os.environ.setdefault('XDG_CACHE_HOME', '/tmp/clear-replanning-cache')
os.environ.setdefault('MPLCONFIGDIR', '/tmp/clear-replanning-cache/matplotlib')
sys.path.insert(0, str(root))
os.chdir(root)
import torch
from experiments.exp4.sprint6h import runner_lh as runner
from experiments.exp3.trajectory_v3.data import scene_features
from replanning_upright_profile import PROFILE, PROFILE_SHA256
from experiments.exp4.sprint6h import physics_client
physics_client.SERVER = Path(__file__).with_name('replanning_upright_server.py').resolve()

torch.set_num_threads(2)
manifest = root / ('experiments/exp4/data/scene_manifest_d6.jsonl' if a.cell == 'D6'
                   else 'experiments/exp4/data/scene_manifest.jsonl')
row = runner.load_row(manifest, a.family, a.cell)
row = copy.deepcopy(row)
for obj in row['scene']['objects']:
    obj['size'][2] = PROFILE['box_height_m']
controller = json.loads((root / 'controllers/v4/paper_g1_v4.json').read_text())
runner.verify_controller(controller)
budgets = json.loads((root / 'experiments/exp4/data/budgets_h6.json').read_text())
assert a.wall_multiplier >= 1
for key in budgets:
    if 'wall' in key or key == 'planner_call_timeout_s':
        if isinstance(budgets[key], (float, int)):
            budgets[key] *= a.wall_multiplier
checkpoint = a.checkpoint.resolve() if a.checkpoint else root / 'assets/checkpoints/exp4/paper_axis.pt'
checkpoint_record = torch.load(checkpoint, map_location='cpu', weights_only=True)
assert checkpoint_record.get('exp4_decoder') == 'axis_chord', 'The parent checkpoint axis-chord decoding contract must be preserved'
del checkpoint_record
native_method = 'clear_frozen' if a.method == 'naive' else 'clear'

class RecordedEpisode(runner.Episode):
    def log(self, event, **fields):
        super().log(event, **fields)
        with (self.out / 'progress.jsonl').open('a') as stream:
            stream.write(json.dumps(self.events[-1]) + '\n')
        print(event, json.dumps(fields, default=str)[:250], flush=True)

    def plan(self, obs, purpose, residual=None):
        # The native builder closes over its SharedObjectProposer.
        proposer = inspect.getclosurevars(self.planner.proposer).nonlocals['proposer']
        model = proposer.model
        layers = [layer[0] for layer in model.flow.trunk.layers]
        encoder_layers = [layer[0] for layer in model.encoder.trunk.layers]
        old_flags = [(layer, getattr(layer, 'store_attn', False)) for layer in layers + encoder_layers]
        for layer, _ in old_flags:
            layer.store_attn = True
        snapshots = []
        calls = [0]
        def capture(module, inputs, output):
            # Keep every integration time and every candidate. Mean over heads
            # and layers only, preserving query/key and batch axes.
            _, _, _, g, t, rank, selected = inputs[:7]
            attn = torch.stack([layer.attn for layer in layers]).mean((0, 2))
            n = rank.shape[1]
            attn = attn[:, 1:1+n]
            torch.testing.assert_close(attn.sum(-1), torch.ones_like(attn.sum(-1)), atol=2e-6, rtol=0)
            assert torch.isfinite(attn).all()
            enc = torch.stack([layer.attn for layer in encoder_layers]).mean((0, 2))[:, 1:1+n]
            torch.testing.assert_close(enc.sum(-1), torch.ones_like(enc.sum(-1)), atol=2e-6, rtol=0)
            snapshots.append(dict(index=calls[0], flow_t=float(t[0]),
                code=g.detach().cpu().tolist(), velocity=output.detach().cpu().tolist(),
                rank=rank.detach().cpu().tolist(), selected=selected.detach().cpu().tolist(),
                attention=attn.detach().cpu().tolist(), encoder_attention=enc.detach().cpu().tolist()))
            calls[0] += 1
        hook = model.flow.register_forward_hook(capture)
        try:
            result = super().plan(obs, purpose, residual)
        finally:
            hook.remove()
            for layer, flag in old_flags:
                layer.store_attn = flag
        _, scene_keys = scene_features(obs['scene'], model.config.get('scene_dim', 9), with_metadata=True)
        prefix = []
        for attempt in self.attempts:
            if attempt['success'] and attempt['object_id'] not in prefix:
                prefix.append(attempt['object_id'])
        payload = dict(call=self.calls, time_s=obs['time_s'], purpose=purpose,
            scene=obs['scene'], prefix=prefix, residual=[] if not residual else [x.object_id for x in residual],
            spatial_keys=[dict(kind='embodiment', source_id='body')] +
                [dict(kind='object', source_id=f"object:{o['object_id']}") for o in obs['scene']['objects']] + scene_keys,
            snapshots=snapshots)
        (self.out / f'planning-{self.calls:03d}.json').write_text(json.dumps(payload, separators=(',', ':')) + '\n')
        return result

source_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in [
    'experiments/exp4/sprint6h/runner_lh.py', 'experiments/exp4/sprint6h/repair.py',
    'experiments/exp4/sprint6h/physics_server.py', 'assets/checkpoints/exp4/paper_axis.pt',
    'third_party/mjlab/src/mjlab/sim/sim_data.py']}
(a.out / 'capture.json').write_text(json.dumps(dict(method=a.method, family=a.family, seed=a.seed,
    cell=a.cell, device=a.device, source_hashes=source_hashes, plan_only=a.plan_only,
    runtime_profile=PROFILE, runtime_profile_sha256=PROFILE_SHA256,
    checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
    controller_identity_scope='Checkpoint conditioning identity; upright physical runtime is a separate variant.',
    attention='Actual attention, averaged over layers and heads. Attention is not success probability.'), indent=2) + '\n')
(a.out / 'scene.json').write_text(json.dumps(row['scene'], indent=2) + '\n')
episode = RecordedEpisode(row, native_method, str(checkpoint), controller, a.seed, 0,
    budgets, a.device, a.out, 16, repair=4 if a.method == 'inpainting' else 0, repair_mode='causal')
if a.plan_only:
    episode.embodiment = runner.g1_embodiment()
    seed, _ = runner.seeds_for(row['scene'], a.seed)
    episode.planner, episode.raw_log, episode.record, episode.geometry, episode.assessor = runner.build_planner(
        checkpoint, controller, seed, a.device, repair=episode.repair, repair_mode='causal')
    scene = runner.planner_scene(row['scene'])
    episode.observations = [dict(object_poses={str(o['object_id']): o['pose'] for o in scene['objects']})]
    decision, error = episode.plan(dict(scene=scene, time_s=0), 'initial')
    (a.out/'planning-diagnostics.json').write_text(json.dumps(episode.plans, indent=2, default=str)+'\n')
    # Replay identical inference without hooks and compare the full raw bank.
    plain, raw, _, _, _ = runner.build_planner(checkpoint, controller, seed, a.device,
        repair=episode.repair, repair_mode='causal')
    reference, _, timed_out = runner.timed_decide(plain, scene, episode.embodiment, 120)
    assert not timed_out and error is None
    assert decision.plan.to_dict() == reference.plan.to_dict()
    assert episode.raw_log == raw
    (a.out/'probe-plan.json').write_text(json.dumps(dict(plan=decision.plan.to_dict(),
        row=row, proposal_seed=seed), indent=2)+'\n')
    print('PASS passive telemetry preserves selected plan and all raw proposals', flush=True)
    if a.probe_replay:
        archived = json.loads((a.probe_replay/'episode.json').read_text())
        archived_scene = json.loads((a.probe_replay/'scene.json').read_text())
        assert archived_scene['walls'] == row['scene']['walls']
        observations = [json.loads(line) for line in (a.probe_replay/'observations.jsonl').read_text().splitlines()]
        event_end = archived['external_events'][0]['end_time_s']
        measured = next(obs for obs in observations if abs(obs['time_s']-event_end) < 1e-5)
        now = copy.deepcopy(scene)
        now['start'] = measured['robot_pose']
        for obj in now['objects']:
            obj['pose'] = measured['object_poses'][str(obj['object_id'])]
        episode.attempts = [x for x in archived['attempt_log'] if x['end_time_s'] <= event_end]
        done = [x['object_id'] for x in episode.attempts if x['success']]
        residual = [x for x in decision.plan.paths if x.object_id not in done]
        anchor = plain.repair_anchor
        anchor.update(order=[x.object_id for x in residual],
            prefix=[(oid, episode.observations[0]['object_poses'][str(oid)]) for oid in done], start=row['scene']['start'])
        decision, error = episode.plan(dict(scene=now, time_s=event_end), 'archived_probe', residual)
        reference, _, timed_out = runner.timed_decide(plain, now, episode.embodiment, 120)
        assert not timed_out and error is None
        assert decision.plan.to_dict() == reference.plan.to_dict() and episode.raw_log == raw
        print('PASS inpainting telemetry preserves inference with a measured executed prefix and displaced object', flush=True)
else:
    result = episode.run()
    result.update(runtime_profile=PROFILE, runtime_profile_sha256=PROFILE_SHA256,
                  controller_identity_scope='Checkpoint conditioning identity; upright physical runtime is a separate variant.')
    pending = a.out/'episode.pending.json'
    pending.write_text(json.dumps(result, indent=2, default=str)+'\n')
    pending.replace(a.out/'episode.json')
    (a.out/'capture-complete.json').write_text(json.dumps(dict(status=result['status'], runtime_profile_sha256=PROFILE_SHA256))+'\n')
    print(json.dumps({k: result.get(k) for k in ['status', 'task_success', 'strict_success', 'planning_calls', 'elapsed_sim_s']}), flush=True)
    if result['status'] == 'infrastructure_error':
        raise SystemExit(1)
