"""Extract hash-matched probe scenes instead of requiring full native recordings."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--archive', required=True, action='append', type=Path)
    args = parser.parse_args()
    root = args.destination.resolve()
    runtime = root / 'runtime'
    sys.path.insert(0, str(runtime))
    sys.dont_write_bytecode = True
    from experiments.exp3.trajectory_v3.navigation import scene_hash
    from experiments.exp3.trajectory_v3.scenes import public_scene
    manifest_path = root / 'docs/artifact_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    inputs = {}
    names = set()
    for relative, record in manifest['files'].items():
        if relative.endswith('_probes.jsonl'):
            source = args.source / record['source_path']
            if sha(source) != record['source_sha256']:
                raise ValueError('Original probe data changed')
            rows = [json.loads(line) for line in source.read_text().splitlines() if line]
            inputs[relative] = rows
            names.update(Path(row['recording']).name for row in rows if row.get('recording'))
    candidates = set()
    for rows in inputs.values():
        candidates.update(Path(row['recording']) / 'input.jsonl' for row in rows if row.get('recording'))
    for archive in args.archive:
        for base, dirs, files in os.walk(archive):
            dirs[:] = [d for d in dirs if d not in {'.git', '.venv', '__pycache__', 'node_modules'}]
            if Path(base).name in names and 'input.jsonl' in files:
                candidates.add(Path(base) / 'input.jsonl')
    scenes = {}
    for path in sorted(candidates):
        if path.is_file():
            row = json.loads(path.read_text())
            if isinstance(row, dict) and 'scene' in row:
                geometry = public_scene(row['scene'])
                scenes.setdefault(scene_hash(geometry), (geometry, sha(path)))
    missing = {row['scene_hash'] for rows in inputs.values() for row in rows
               if row.get('recording') and row['scene_hash'] not in scenes}
    if missing:
        raise ValueError(f'{len(missing)} probe scene hashes have no matching archive input')
    extracted = {}
    count = 0
    for relative, original_rows in inputs.items():
        target = root / relative
        record = manifest['files'][relative]
        if sha(target) != record['sha256']:
            raise ValueError('Refusing to overwrite edited probe data')
        rows = [json.loads(line) for line in target.read_text().splitlines() if line]
        if len(rows) != len(original_rows):
            raise ValueError('Probe row count changed')
        for original, row in zip(original_rows, rows):
            if not original.get('recording'):
                continue
            # No measured labels, body data or split memberships may change.
            left = {k: v for k, v in original.items() if k != 'recording'}
            right = {k: v for k, v in row.items() if k != 'recording'}
            if left != right:
                raise ValueError('Probe values changed beyond the recording reference')
            digest = row['scene_hash']
            scene, input_hash = scenes[digest]
            directory = f'data/probe_scenes/{digest}'
            path = runtime / directory / 'input.jsonl'
            if digest not in extracted:
                path.parent.mkdir(parents=True, exist_ok=True)
                content = json.dumps(dict(scene=scene), sort_keys=True) + '\n'
                if path.exists() and path.read_text() != content:
                    raise ValueError('Conflicting extracted scene')
                path.write_text(content)
                extracted[digest] = dict(source_input_sha256=input_hash, scene_hash=digest,
                                         path='runtime/' + directory + '/input.jsonl')
                manifest['files']['runtime/' + directory + '/input.jsonl'] = dict(
                    source_path=None, source_sha256=input_hash, sha256=sha(path), bytes=path.stat().st_size,
                    changes=['Extracted public scene fields; exact probe scene hash verified'])
            row['recording'] = directory
            count += 1
        target.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
        record.update(sha256=sha(target), bytes=target.stat().st_size)
        record['changes'].append('Recording reference points to packaged hash-matched scene input; all other probe values unchanged')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    (root / 'docs/probe_scenes.json').write_text(json.dumps(dict(
        schema='clear-standalone-probe-scenes-v1', scenes=extracted,
        relocated_probe_rows=count, original_probe_values_preserved=True), indent=2) + '\n')
    print(json.dumps(dict(extracted_scenes=len(extracted), relocated_probe_rows=count)))


if __name__ == '__main__':
    main()
