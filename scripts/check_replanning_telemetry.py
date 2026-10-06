"""Check observed attention and the actual executed-prefix interpolant."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--run', type=Path, required=True)
p.add_argument('--project', type=Path, required=True)
a = p.parse_args()
sys.path.insert(0, str(a.project))
from experiments.exp4.sprint6h.repair import path_code
calls = [json.loads(f.read_text()) for f in sorted(a.run.glob('planning-*.json'))]
assert calls
initial = {o['object_id']: o for o in calls[0]['scene']['objects']}
conditioned = 0
for call in calls:
    ids = [o['object_id'] for o in call['scene']['objects']]
    n = len(ids)
    for snapshot in call['snapshots']:
        attention = np.asarray(snapshot['attention'])
        encoder = np.asarray(snapshot['encoder_attention'])
        for tensor in [attention, encoder]:
            assert np.isfinite(tensor).all() and (tensor >= 0).all()
            assert np.allclose(tensor.sum(-1), 1, atol=2e-6, rtol=0)
        ranks = np.asarray(snapshot['rank'])
        selected = np.asarray(snapshot['selected'])
        later = ranks[:, None, :] > ranks[:, :, None]
        blocked = selected[:, :, None] & selected[:, None, :] & later
        assert (attention[:, :, 1:1+n][blocked] == 0).all(), 'Later dynamic tokens leaked through the causal mask'
    if call['prefix'] and len(call['snapshots']) == 60:
        group = call['snapshots'][30:]
        eps = np.asarray(group[0]['code'])
        world = np.asarray(call['scene']['world_size'])
        for oid in call['prefix']:
            slot = ids.index(oid)
            origin = np.asarray(initial[oid]['pose'])
            end = np.asarray(call['scene']['objects'][slot]['pose'])
            count = eps.shape[-1]//4
            # Native densify repeatedly bisects the longest segment, rather
            # than placing waypoints at evenly spaced fractions.
            target = path_code(origin, end, count+1, *world)
            for snapshot in group:
                t = snapshot['flow_t']
                expected = (1-t)*eps[:, slot]+t*target
                assert np.allclose(np.asarray(snapshot['code'])[:, slot], expected, atol=3e-7, rtol=0)
        conditioned += 1
assert conditioned, 'No conditioned replanning call was checked'
print('PASS normalized measured attention, causal masking, and fixed executed-prefix interpolation')
