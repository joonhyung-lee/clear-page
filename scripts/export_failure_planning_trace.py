"""Publish only numeric geometry, archived proposals and rejection events."""
import argparse
import json
from pathlib import Path
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    scene = json.loads((args.source / 'scene.json').read_text())
    plan = json.loads((args.source / 'planner.json').read_text())
    assert plan['status'] == 'no_valid_plan_found' and not plan['native_execution']
    decisions = [d for d in plan['decision_trace'] if 'candidate' in d]
    candidates = []
    for decision in decisions:
        raw = plan['raw_proposals'][decision['candidate']]
        paths = []
        for path in raw.get('paths', []):
            points = np.asarray(path['poses'], dtype=float)
            assert np.isfinite(points).all()
            assert np.allclose(points[0], scene['objects'][path['object_id']]['pose'])
            paths.append({'object': path['object_id'], 'poses': points.tolist()})
        candidates.append({'id': decision['candidate'], 'order': decision.get('order', []),
                           'rejection': decision['rejection'], 'paths': paths,
                           'invalidDecode': 'decoder_error' in raw})
    assert len(candidates) == len(plan['raw_proposals']) == 8
    data = {'walls': scene['walls'], 'objects': [{k: o[k] for k in ('pose', 'size')} for o in scene['objects']],
            'start': scene['start'], 'goal': scene['goal'], 'candidates': candidates,
            'status': plan['status'], 'searchTraceRecorded': True, 'physicalExecution': False,
            'scope': 'Archived proposal and rejection sequence. Presentation time is not planner runtime.'}
    path = Path(__file__).resolve().parents[1] / 'assets/failure-planning-data.js'
    path.write_text('window.CLEAR_FAILURE_PLANNING = ' + json.dumps(data, separators=(',', ':'), allow_nan=False) + ';\n')
    print('PASS exported eight archived decisions, finite proposals and matching initial object poses')


if __name__ == '__main__':
    main()
