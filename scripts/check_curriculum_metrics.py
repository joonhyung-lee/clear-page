"""Compare every public PPO update with its private TensorBoard source."""
import argparse
import json
from pathlib import Path
from watch_spot_curriculum import read_curves


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--body', choices=['g1', 'spot', 'spot_arm'], default='g1')
    parser.add_argument('--live', action='store_true', help='Allow new source updates after the published snapshot')
    args = parser.parse_args()
    plan = json.loads((args.run / 'plan.json').read_text())
    assert plan['body'] == args.body
    expected = read_curves(args.run, plan)
    source = Path(__file__).resolve().parents[1] / f'assets/{args.body}-curriculum-data.js'
    actual = json.loads(source.read_text().split(' = ', 2)[2].rstrip(';\n'))['curves']
    if args.live and actual:
        expected = [row for row in expected if row['update'] <= actual[-1]['update']]
    assert len(actual) == len(expected), f'Published {len(actual)} of {len(expected)} logged updates'
    assert actual == expected, 'Published metrics must match every source value and stage offset'
    assert len({row['update'] for row in actual}) == len(actual), 'Duplicate updates'
    for key in ['value', 'policy', 'entropy', 'return', 'terrain', 'tracking']:
        values = [(r['update'], r[key]) for r in actual if key in r]
        if not values:
            print(f'PASS {key}: absent in source and public data')
        else:
            print(f'PASS {key}: {len(values)} exact values; min {min(values,key=lambda v:v[1])}; max {max(values,key=lambda v:v[1])}')


if __name__ == '__main__':
    main()
