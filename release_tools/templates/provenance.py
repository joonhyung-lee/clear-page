"""Identify the actual standalone source bytes without consulting a parent Git repo."""
import hashlib
import json
from pathlib import Path


def package_revision():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / 'docs/source_manifest.json').read_text())
    actual = {}
    changed = []
    for relative, record in sorted(manifest['files'].items()):
        if not relative.endswith('.py'):
            continue
        path = root / relative
        if not path.resolve().is_relative_to(root):
            raise ValueError('Source path escapes standalone package')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        actual[relative] = digest
        if digest != record['sha256']:
            changed.append(relative)
    identity = hashlib.sha256(json.dumps(actual, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return dict(commit='standalone:' + identity, tracked_changes=bool(changed),
                changed_files=changed, source_identity='packaged Python file hashes')
