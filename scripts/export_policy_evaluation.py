"""Validate private evaluation episodes and publish anonymous numeric summaries."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]


def proportion(values):
    n, k = len(values), sum(values)
    p = k / n
    z = 1.959963984540054
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    width = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return {'mean': 100 * p, 'low': 0 if k == 0 else 100 * max(0, center - width),
            'high': 100 if k == n else 100 * min(1, center + width), 'count': k}


def summarize(episodes):
    values = [e['rmse'] for e in episodes]
    mean, sd = statistics.mean(values), statistics.stdev(values)
    return {'tracking': {'mean': mean, 'low': max(0, mean - sd), 'high': mean + sd, 'sd': sd},
            'success': proportion([e['success'] for e in episodes]),
            'falls': proportion([e['fall'] for e in episodes]),
            'episodes': len(episodes),
            'meanDuration': statistics.mean(e['duration'] for e in episodes),
            'meanProgress': statistics.mean(e['progress'] for e in episodes)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    bodies = {}
    origin_hash = None
    shared_protocol = None
    for body in ['g1', 'spot', 'spot_arm']:
        source = args.input / (body + '.json')
        if not source.exists() and args.allow_partial:
            continue
        private = json.loads(source.read_text())
        p = private['identity']['protocol']
        assert p['durationSeconds'] == 20 and p['episodeSeeds'] == [101, 202, 303]
        assert private['identity']['body'] == body
        assert private['identity']['evaluator'] == hashlib.sha256((ROOT/'scripts/evaluate_policy_progress.py').read_bytes()).hexdigest()
        assert private['identity']['manifest'] == hashlib.sha256(args.manifest.read_bytes()).hexdigest()
        if shared_protocol is None:
            shared_protocol = p
        assert p == shared_protocol, 'Evaluation settings differ across bodies'
        if body == 'spot':
            assert private['physics']['physics'] == 'arm-free'
            assert private['physics']['armJoints'] == 0 and private['physics']['actuators'] == 12
        elif body == 'spot_arm':
            assert private['physics']['actuators'] == 19 and private['physics']['nq'] == 26
        if origin_hash is None:
            origin_hash = p['terrainOriginHash']
        assert origin_hash == p['terrainOriginHash'], 'Bodies must use the same terrain bank'
        rows = private['checkpoints']
        expected = {r['update']: r for r in manifest[body]}
        assert len({r['update'] for r in rows}) == len(rows)
        if not args.allow_partial:
            assert set(expected) == {r['update'] for r in rows}, 'Missing checkpoint evaluations'
        baseline_states = None
        exported = []
        for row in sorted(rows, key=lambda row: row['update']):
            assert row['phase'] == expected[row['update']]['phase']
            checkpoint = Path(expected[row['update']]['path'])
            assert row['checkpointHash'] == hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            episodes = row['episodes']
            assert len(episodes) == 60
            assert {(e['seed'], e['environment']) for e in episodes} == {(seed, i) for seed in p['episodeSeeds'] for i in range(20)}
            states = {(e['seed'], e['environment']): e['initialStateHash'] for e in episodes}
            if baseline_states is None:
                baseline_states = states
            assert states == baseline_states, 'Initial states changed between checkpoints'
            for e in episodes:
                assert not (e['success'] and e['fall'])
                assert 0 < e['duration'] <= 20.00001 and math.isfinite(e['rmse']) and e['rmse'] >= 0
                assert e['terrain'] == p['terrains'][e['environment'] % 5]
                if e['success']:
                    assert e['progress'] >= 3.
            exported.append({'update': row['update'], 'phase': row['phase'], **summarize(episodes),
                             'byTerrain': {terrain: summarize([e for e in episodes if e['terrain'] == terrain])
                                           for terrain in p['terrains']}})
        assert exported[0]['update'] == 0
        bodies[body] = {'rows': exported, 'initialization': 'warm start' if body == 'g1' else 'random',
                        'plannedCheckpoints': len(expected),
                        'complete': set(expected) == {r['update'] for r in rows}}
    payload = {'schema': 1, 'status': 'measured',
               'protocol': {'terrains': ['flat', 'stairs_up', 'stairs_down', 'slope_up', 'slope_down'],
                            'difficultyLevels': [0, .2, .4, .6], 'episodesPerCheckpoint': 60,
                            'initialConditionSeeds': 3, 'trainingSeedsPerBody': 1,
                            'durationSeconds': 20, 'speedMps': .5, 'goalDistanceM': 3,
                            'lateralToleranceM': .75, 'fallAngleDegrees': 70,
                            'armPose': 'nominal', 'trackingBand': 'One episode standard deviation',
                            'rateBand': '95% Wilson interval'}, 'bodies': bodies}
    target = ROOT/'assets/policy-evaluation-data.js'
    target.write_text('window.CLEAR_POLICY_EVALUATION = '+json.dumps(payload, separators=(',', ':'), allow_nan=False)+';\n')
    print('Published measured checkpoints:', {body: len(d['rows']) for body, d in bodies.items()})


if __name__ == '__main__':
    main()
