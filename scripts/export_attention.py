"""Extract real CLEAR attention on recorded observations, without changing inference."""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import torch

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--project', type=Path, required=True)
p.add_argument('--checkpoint', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--frames', type=int, default=5, help='Number of recorded observations per rollout')
p.add_argument('--encoder-only', action='store_true', help='Capture scene attention without running flow generation')
a = p.parse_args()
sys.path.insert(0, str(a.project))
from experiments.exp3.trajectory_v3.shared_morphology import load_shared_checkpoint, SharedTraversalPredictor
from experiments.exp3.trajectory_v3.navigation import EmbodimentSpec, TerrainNavigator
from experiments.exp3.trajectory_v3.calibration import digest
from experiments.exp3.trajectory_v3.data import collate, scene_features
from clear.model.causal_velocity_field import causal_mask

ROOT = Path(__file__).resolve().parents[1]
torch.set_num_threads(2)
model, record = load_shared_checkpoint(a.checkpoint)
model.eval()
structures = json.loads((a.project / 'assets/checkpoints/exp3/structures.json').read_text())
raw = (ROOT / 'assets/learning-samples.js').read_text()
samples = json.loads(raw[raw.index('=')+1:].strip().rstrip(';'))['ordering']
navigator = TerrainNavigator(SharedTraversalPredictor(model, record['controller_profiles']), **record['navigation'])
encoder = [layer[0] for layer in model.encoder.trunk.layers]
flow = [layer[0] for layer in model.flow.trunk.layers]

def enabled(modules, flag):
    for module in modules:
        module.store_attn = flag

def capture(modules, n, blocked=None):
    full = torch.stack([m.attn[0] for m in modules])
    assert torch.isfinite(full).all() and (full >= 0).all()
    torch.testing.assert_close(full.sum(-1), torch.ones_like(full.sum(-1)), atol=2e-6, rtol=0)
    if blocked is not None:
        assert full.masked_select(blocked[0][None, None].expand_as(full)).abs().max().item() == 0
    # Keep all layers and heads. Query axis contains actual object slots only.
    return full[:, :, 1:1+n].tolist()

def spatial_tokens(scene):
    _, metadata = scene_features(scene, model.config.get('scene_dim', 9), with_metadata=True)
    objects = [dict(kind='object', source_id=f'object:{o["object_id"]}',
                    pose=o['pose'], size=o['size']) for o in scene['objects']]
    return [dict(kind='embodiment', source_id='body')] + objects + metadata

def infer(scene, body):
    structure = structures[body]
    spec = EmbodimentSpec(structure, .35, record['controller_profiles'][digest(structure)])
    context = navigator.analyze(scene, spec).model_context()
    batch = collate([dict(scene=scene, structure_rows=structure, navigation_context=context)],
                    model.config['waypoints'], scene_dim=model.config.get('scene_dim', 9), include_targets=False)
    n = len(scene['objects'])
    enabled(encoder, False)
    baseline = model._encode(batch)
    enabled(encoder, True)
    h = model._encode(batch)
    for key in ('tokens', 'selection', 'mu', 'sigma'):
        assert torch.equal(h[key], baseline[key]), 'Attention recording changed encoder predictions'
    shared = capture(encoder, n)
    enabled(encoder, False)
    rank, selected = model.ordering.sample(h['selection'], h['mu'], h['sigma'], batch['object_mask'],
                                         generator=torch.Generator().manual_seed(0), sample_selection=False)
    keys = spatial_tokens(scene)
    result = dict(scene=scene, keys=keys, encoder=shared,
                  selection=h['selection'][0].sigmoid().tolist(), rank=rank[0].tolist(),
                  selected=selected[0].tolist(), flow=[])
    if selected.any() and not a.encoder_only:
        enabled(flow, False)
        args = (h['objects'], h['embodiment'], h['scene'], rank, selected)
        key_mask = model.flow_key_mask(h, batch['object_mask'])
        reference = model.flow.sample(*args, n_steps=30, generator=torch.Generator().manual_seed(0), key_mask=key_mask)
        enabled(flow, True)
        captured = []
        calls = [0]
        blocked = causal_mask(rank, selected, h['scene'].shape[1]+n, causal=model.flow.causal) | ~key_mask[:, None, :]
        def hook(module, inputs, output):
            k = calls[0]
            if k in (0, 15, 29):
                captured.append(dict(t=k/30, weights=capture(flow, n, blocked)))
            calls[0] += 1
        handle = model.flow.register_forward_hook(hook)
        try:
            actual = model.flow.sample(*args, n_steps=30, generator=torch.Generator().manual_seed(0), key_mask=key_mask)
        finally:
            handle.remove()
            enabled(flow, False)
        assert torch.equal(actual, reference), 'Attention recording changed generated paths'
        assert calls[0] == 30
        result['flow'] = captured
        # Generated decision tokens contain whole paths, not one spatial point.
        result['flowKeys'] = [keys[0]] + [dict(kind='decision', source_id=f'decision:{o["object_id"]}') for o in scene['objects']] + keys[1+n:] + keys[1:1+n]
    return result

cases = []
with torch.inference_mode():
    for sample_id in (53, 54, 52):
        sample = samples[sample_id]
        case = dict(id=f'sample-{sample_id+1}', body=sample['body'], split=sample['split'],
                    title={'53':'Two passages · G1', '54':'Two passages · Spot + arm', '52':'Mixed terrain · G1'}[str(sample_id)], frames=[])
        base = infer(copy.deepcopy(sample['scene']), sample['body'])
        assert np.allclose(base['selection'], sample['selection'], atol=1e-5, rtol=0), 'Checkpoint differs from published predictions'
        base.update(time=0, label='Planning input')
        case['frames'].append(base)
        rollout = sample['rollout']
        for index in np.unique(np.linspace(0, len(rollout)-1, a.frames).astype(int)):
            frame = rollout[index]
            scene = copy.deepcopy(sample['scene'])
            scene['start'] = frame[1:4]
            for obj, pose in zip(scene['objects'], frame[4], strict=True):
                obj['pose'] = pose
            result = infer(scene, sample['body'])
            result.update(time=frame[0], label=f'Recorded state · {frame[0]:.1f} s')
            case['frames'].append(result)
            print(case['title'], result['label'], 'selected', result['selected'], flush=True)
        cases.append(case)
value = dict(schema=1, cases=cases, checkpointSHA256=hashlib.sha256(a.checkpoint.read_bytes()).hexdigest(),
             layers=len(encoder), heads=encoder[0].heads,
             protocol=dict(observations='Actual recorded robot and object poses. Attention is recomputed offline on these states, not captured online during the original controller run.',
                           shared='Object queries to embodiment, observed objects and scene primitives.',
                           flow='Generated object-path queries to embodiment, rank-masked decisions, scene primitives and observed object copies. Flow time is not execution time.',
                           aggregation='Arithmetic mean of selected queries, layers and heads. No attention rollout, gradients, smoothing, or spatial renormalization.',
                           projection='Scene-token weights are shown on their exact top-down footprints. Embodiment and generated whole-path decisions remain non-spatial.',
                           scope='Attention weights describe model information mixing, not causal importance or task success. These are geometry-token maps, not RGB-pixel attention or depth/segmentation probes.'),
             verification=dict(encoderPredictionsBitIdentical=True, flowEndpointsBitIdentical=None if a.encoder_only else True,
                               softmaxRowsSumToOne=True, causalMaskedWeightsZero=None if a.encoder_only else True, publishedSelectionsMatch=True))
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False)+'\n')
print('PASS captured attention without changing predictions or flow endpoints:', a.output, flush=True)
