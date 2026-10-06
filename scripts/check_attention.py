"""Verify public attention data against recorded states and causal constraints."""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT/'attention/attention.json').read_text())
text = (ROOT/'assets/learning-samples.js').read_text()
samples = json.loads(text[text.index('=')+1:].strip().rstrip(';'))['ordering']
count = 0
for case, sample_id in zip(data['cases'], [53, 54, 52], strict=True):
    source = samples[sample_id]
    assert case['body'] == source['body']
    for frame, index in zip(case['frames'][1:], np.linspace(0, len(source['rollout'])-1, 5).astype(int), strict=True):
        recorded = source['rollout'][index]
        assert frame['time'] == recorded[0]
        assert frame['scene']['start'] == recorded[1:4]
        assert [obj['pose'] for obj in frame['scene']['objects']] == recorded[4]
    for frame in case['frames']:
        weights = np.asarray(frame['encoder'])
        assert weights.shape[:3] == (4, 4, len(frame['scene']['objects']))
        assert weights.shape[-1] == len(frame['keys'])
        assert np.isfinite(weights).all() and (weights >= 0).all()
        assert np.allclose(weights.sum(-1), 1, atol=2e-6, rtol=0)
        for step in frame['flow']:
            weights = np.asarray(step['weights'])
            assert weights.shape[-1] == len(frame['flowKeys'])
            assert np.allclose(weights.sum(-1), 1, atol=2e-6, rtol=0)
            for query, selected in enumerate(frame['selected']):
                if not selected:
                    continue
                for key, movable in enumerate(frame['selected']):
                    if movable and frame['rank'][key] > frame['rank'][query]:
                        assert np.max(weights[:, :, query, 1+key]) == 0
        assert bool(frame['flow']) == any(frame['selected'])
        count += 1
assert count == 18
for artifact in ['index.html', 'attention-overview.png', 'attention-overview.pdf', 'attention-flow.png', 'attention-flow.pdf']:
    assert (ROOT/'attention'/artifact).stat().st_size > 1000
print('PASS 18 exact recorded observations, body identities, normalized attention, causal masks and five visual artifacts')
