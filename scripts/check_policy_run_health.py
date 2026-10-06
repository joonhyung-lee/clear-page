"""Check raw training evidence for numerical excursions and stalled terrain.

This diagnostic never filters or rewrites logged measurements. Its failure is
evidence of an unhealthy run, not a conclusion about the underlying cause.
"""
import argparse
import json
import math
import statistics
from pathlib import Path
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator


def inspect(run):
    plan = json.loads((run / 'plan.json').read_text())
    result = {'body': plan.get('body', 'spot_arm'), 'stages': [], 'failures': []}
    for stage in plan['stages']:
        folder = run / stage['name']
        if not folder.is_dir():
            continue
        events = EventAccumulator(str(folder), size_guidance={'scalars': 0})
        events.Reload()
        report = {'stage': stage['name'], 'metrics': {}}
        for tag in events.Tags()['scalars']:
            if not (tag.startswith('Loss/') or tag in ['Train/mean_reward',
                    'Episode_Metrics/diag_critic_obs_absmax', 'Episode_Metrics/diag_reward_absmax',
                    'Curriculum/terrain_levels/mean', 'Curriculum/arm_stow/mean']):
                continue
            rows = events.Scalars(tag)
            finite = [r for r in rows if math.isfinite(r.value)]
            if len(finite) != len(rows):
                result['failures'].append(f"{stage['name']}: nonfinite {tag}")
            if not finite:
                continue
            reference = max(1e-12, statistics.median(abs(r.value) for r in finite[:min(1000, len(finite))]))
            peak = max(finite, key=lambda r: abs(r.value))
            report['metrics'][tag] = {'count': len(rows), 'first': rows[0].value,
                'last': rows[-1].value, 'min': min(r.value for r in finite),
                'max': max(r.value for r in finite), 'peakUpdate': peak.step + 1,
                'firstUpdate': min(r.step for r in finite) + 1,
                'lastUpdate': max(r.step for r in finite) + 1,
                'peakToEarlyMedian': abs(peak.value) / reference}
            if tag in ['Loss/value', 'Train/mean_reward', 'Episode_Metrics/diag_critic_obs_absmax',
                       'Episode_Metrics/diag_reward_absmax'] and abs(peak.value) / reference > 1e6:
                result['failures'].append(f"{stage['name']}: millionfold excursion in {tag} at update {peak.step+1}")
            # Curriculum metrics are emitted at resets, not every PPO update.
            # Sparse measurements must not defer the same stagnation check.
            span = max(r.step for r in finite) - min(r.step for r in finite) + 1
            if tag == 'Curriculum/terrain_levels/mean' and span >= 1000 and all(r.value == 0 for r in finite):
                result['failures'].append(f"{stage['name']}: all {len(finite)} terrain measurements were zero across {span} PPO updates")
        result['stages'].append(report)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = inspect(args.run)
    if args.report:
        args.report.write_text(json.dumps(result, indent=2) + '\n')
    for failure in result['failures']:
        print('FAIL', failure)
    if not result['failures']:
        print('PASS no detected numerical excursions or persistently zero terrain in available logs')
    raise SystemExit(bool(result['failures']))
