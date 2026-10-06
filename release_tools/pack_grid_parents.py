"""Copy the exact training parents of the selected Grid paper checkpoints."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil

from audit_checkpoint_metadata import scan


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--private-term', action='append', required=True)
    args = parser.parse_args()
    source, root = args.source.resolve(), args.destination.resolve()
    ancestry = json.loads((source / 'training/exp1/ancestry.json').read_text())
    apath, rpath = root / 'docs/artifact_manifest.json', root / 'docs/checkpoints.json'
    artifacts, registry = json.loads(apath.read_text()), json.loads(rpath.read_text())
    parent_manifest = 'training/exp1/ancestry.json'
    registry['references'] = [r for r in registry['references'] if r['manifest'] != parent_manifest]
    checked = {}
    for stage in ancestry['stages']:
        relative, expected = stage['source'], stage['source_sha256']
        original = source / relative
        if not original.resolve().is_relative_to(source) or digest(original) != expected:
            raise ValueError('Training parent differs from original ancestry record')
        if expected not in checked:
            checked[expected] = dict(path=relative, sha256=expected, bytes=original.stat().st_size,
                                    metadata_findings=scan(original, args.private_term))
        findings = checked[expected]['metadata_findings']
        target = root / 'runtime' / relative
        if findings:
            if target.exists():
                raise ValueError('Metadata-flagged parent is already present; review required')
        else:
            if target.exists() and digest(target) != expected:
                raise ValueError('Existing parent differs: ' + relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copyfile(original, target)
            if digest(target) != expected:
                raise ValueError('Parent copy hash mismatch')
            artifacts['files']['runtime/' + relative] = dict(source_path=relative,
                source_sha256=expected, sha256=expected, bytes=target.stat().st_size, changes=[])
        registry['references'].append(dict(manifest=parent_manifest, label=relative,
            sha256=expected, status='metadata-review' if findings else 'packaged',
            path=None if findings else 'runtime/' + relative,
            used_by=stage['checkpoint'], method=stage['method'], seed=stage['seed']))
    registry['unique_packaged_models'] = len({r['sha256'] for r in registry['references'] if r['status'] == 'packaged'})
    rows = list(checked.values())
    report = dict(schema='clear-grid-training-parent-audit-v1', models=rows,
        counts=dict(Counter('metadata-review' if r['metadata_findings'] else 'metadata-passed' for r in rows)),
        all_source_hashes_verified=True, full_anonymity_certified=False)
    (root / 'docs/grid_parent_audit.json').write_text(json.dumps(report, indent=2) + '\n')
    apath.write_text(json.dumps(artifacts, indent=2) + '\n')
    rpath.write_text(json.dumps(registry, indent=2) + '\n')
    print(json.dumps(dict(parents=report['counts'], unique_packaged_models=registry['unique_packaged_models'])))


if __name__ == '__main__':
    main()
