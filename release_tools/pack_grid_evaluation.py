"""Build a compact evaluation contract without changing Grid inference or data.

The standalone code snapshot receives its own complete source pins. Historical
pins remain recorded separately; this is not labelled the original code freeze.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    args = parser.parse_args()
    source, destination = args.source.resolve(), args.destination.resolve()
    runtime = destination / 'runtime'
    original = source / 'experiments/exp1/configs/paper.json'
    release = json.loads(original.read_text())
    registry = json.loads((destination / 'docs/checkpoints.json').read_text())
    packaged = {r['sha256']: r['path'] for r in registry['references'] if r['status'] == 'packaged'}
    arms = {}
    for name, arm in release['arms'].items():
        checkpoints = {}
        for seed, checkpoint in arm['checkpoints'].items():
            digest = checkpoint['sha256']
            if digest not in packaged:
                raise ValueError(f'Packaged checkpoint required: {name} seed {seed}')
            path = destination / packaged[digest]
            if sha(path) != digest:
                raise ValueError('Packaged checkpoint changed')
            checkpoints[seed] = dict(path=str(path.relative_to(runtime)), sha256=digest)
        arms[name] = dict(method=arm['method'], inference=arm['inference'], checkpoints=checkpoints)
    artifact_path = destination / 'docs/artifact_manifest.json'
    artifacts = json.loads(artifact_path.read_text())
    for split in release['splits'].values():
        original_data = source / split['path']
        if sha(original_data) != split['sha256']:
            raise ValueError('Source evaluation data changed')
        target = runtime / split['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and sha(target) != split['sha256']:
            raise ValueError('Refusing to overwrite different evaluation data')
        shutil.copyfile(original_data, target)
        artifacts['files']['runtime/' + split['path']] = dict(
            source_path=split['path'], source_sha256=split['sha256'], sha256=sha(target),
            bytes=target.stat().st_size, changes=[])
    source_manifest = json.loads((destination / 'docs/source_manifest.json').read_text())
    pins = {str(Path(path).relative_to('runtime')): value['sha256']
            for path, value in source_manifest['files'].items() if path.endswith('.py')}
    for path, expected in pins.items():
        if sha(runtime / path) != expected:
            raise ValueError('Standalone source changed before contract creation')
    contract = dict(schema='clear-standalone-grid-evaluation-v1',
        source_release_sha256=sha(original), source_release_path='experiments/exp1/configs/paper.json',
        evaluation_seed=release['evaluation_seed'], training_seeds=release['training_seeds'],
        arms=arms, splits=release['splits'], code_sha256=pins,
        historical_code_sha256=release['code_sha256'],
        packaging_note='Standalone source freeze; original weights, splits and inference settings. '
                       'Historical pins are provenance, not a claim that this source equals the historical freeze.')
    target = runtime / 'experiments/exp1/configs/paper.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(contract, indent=2) + '\n'
    if target.exists() and target.read_text() != content:
        previous = artifacts['files'].get('runtime/experiments/exp1/configs/paper.json', {})
        if previous.get('sha256') != sha(target):
            raise ValueError('Refusing to overwrite a locally edited evaluation contract')
    target.write_text(content)
    artifacts['files']['runtime/experiments/exp1/configs/paper.json'] = dict(
        source_path='experiments/exp1/configs/paper.json', source_sha256=sha(original),
        sha256=sha(target), bytes=target.stat().st_size,
        changes=['Compact standalone contract: relocate checkpoints by hash, pin packaged source, '
                 'retain original inference, split hashes, seed settings and historical source hashes'])
    artifact_path.write_text(json.dumps(artifacts, indent=2) + '\n')
    print(json.dumps(dict(checkpoints=sum(len(a['checkpoints']) for a in arms.values()),
                          splits=len(contract['splits']), source_pins=len(pins))))


if __name__ == '__main__':
    main()
