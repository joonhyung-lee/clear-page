"""Package available r2 planning inputs; report missing raw probe supervision."""
import argparse
import hashlib
import json
from pathlib import Path

from pack_revision_recipes import normalize


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True)
    p.add_argument('--private-term', action='append', required=True)
    a = p.parse_args()
    source, root = a.source.resolve(), a.destination.resolve()
    run_base = source / 'outputs/leap2026/V4/maze_v4_r2/train'
    runs = sorted(run_base.glob('*/run.json'))
    if not runs:
        raise ValueError('No recorded r2 training recipes')
    inputs, expected = set(), {}
    for run_path in runs:
        run = json.loads(run_path.read_text())
        inputs.add(str(run_path.relative_to(source)))
        for ref, checksum in ((normalize(run['config'], []), run['config_sha256']),
                              (run['provenance']['plans'], run['provenance']['plans_sha256']),
                              (run['provenance']['roster'], run['provenance']['roster_sha256'])):
            ref = str(Path(ref))
            digest = checksum.removeprefix('sha256:')
            if ref in expected and expected[ref] != digest:
                raise ValueError('Training runs recorded different inputs: ' + ref)
            expected[ref] = digest
            inputs.add(ref)
    plan_base = 'data/plans/maze_v4_r2'
    plans = json.loads((source / plan_base / 'manifest.json').read_text())
    inputs.add(plan_base + '/manifest.json')
    for name, checksum in plans['files'].items():
        ref = plan_base + '/' + name
        if ref in expected and expected[ref] != checksum.removeprefix('sha256:'):
            raise ValueError('Plan generation and training hashes disagree')
        expected[ref] = checksum.removeprefix('sha256:')
        inputs.add(ref)
    inputs.add(plans['args']['test_templates'])
    roster_base = 'data/rosters/maze_v4_r2'
    roster = json.loads((source / roster_base / 'roster.json').read_text())
    for entry in roster['entries']:
        inputs.add(roster_base + '/' + entry['rows_file'])
    probe_base = 'data/probes/maze_v4_r2'
    inputs.add(probe_base + '/manifest.json')
    missing = []
    for entry in roster['entries']:
        if entry['split'] == 'test-body':
            continue
        body = entry['body_id']
        summary = f'{probe_base}/{body}/summary.json'
        trials = f'{probe_base}/{body}/trials.jsonl'
        if (source / summary).is_file():
            inputs.add(summary)
        if (source / trials).is_file():
            inputs.add(trials)
        else:
            missing.append(trials)
    mp = root / 'docs/artifact_manifest.json'
    manifest = json.loads(mp.read_text())
    for relative in sorted(inputs):
        original = source / relative
        if not original.resolve().is_relative_to(source):
            raise ValueError('Input escapes the source root')
        raw = original.read_bytes()
        if relative in expected and sha(raw) != expected[relative]:
            raise ValueError('Recorded training input hash mismatch: ' + relative)
        changed = []
        data = raw
        if original.suffix == '.json':
            value = normalize(json.loads(raw), changed)
            if changed:
                data = (json.dumps(value, indent=2) + '\n').encode()
        if original.suffix != '.npy':
            lower = data.lower()
            if any(term.lower().encode() in lower for term in a.private_term) or b'/home/' in lower or b'/mnt/' in lower:
                raise ValueError('Identity or private path requires review: ' + relative)
        target = root / 'runtime' / relative
        if target.exists() and target.read_bytes() != data:
            raise ValueError('Refusing to overwrite different input: ' + relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest['files']['runtime/' + relative] = dict(source_path=relative,
            source_sha256=sha(raw), sha256=sha(data), bytes=len(data),
            changes=['normalize private repository prefix'] if changed else [],
            changed_fields=changed, historical_input_hash_verified=relative in expected)
    mp.write_text(json.dumps(manifest, indent=2) + '\n')
    report = dict(schema='clear-standalone-v4-inputs-v1', campaign='maze_v4_r2',
        recorded_runs=len(runs), copied_inputs=len(inputs),
        recorded_hashes_verified=expected, roster_bodies=len(roster['entries']),
        missing_training_probe_files=missing, training_probe_supervision_complete=not missing,
        summary_files_are_not_training_substitutes=True, native_variant_assets_packaged=False,
        raw_probe_timing_cannot_be_reconstructed_from_summaries=True,
        full_training_reproduced=False)
    (root / 'docs/v4_inputs.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(recorded_runs=len(runs), copied_inputs=len(inputs), missing_probe_files=len(missing))))


if __name__ == '__main__':
    main()
