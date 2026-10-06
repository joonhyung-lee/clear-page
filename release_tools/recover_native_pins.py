"""Recover exact frozen source bytes into a new local review directory.

No source checkout, controller identity, or pin is modified. This is a source
recovery receipt, not a runnable controller distribution or qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--destination', required=True, type=Path)
    p.add_argument('--revision', action='append', default=[])
    p.add_argument('--report', required=True, type=Path)
    args = p.parse_args()
    root, dest = args.source.resolve(), args.destination.resolve()
    if dest.exists() or dest.is_relative_to(root) or root.is_relative_to(dest):
        raise ValueError('Use a new, separate directory')
    pin_bytes = (root / 'controllers/release_source_hashes.json').read_bytes()
    pins = json.loads(pin_bytes)
    records, contents = {}, {}
    for relative, expected in pins.items():
        if Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('Invalid pinned path')
        current = root / relative
        data = current.read_bytes() if current.is_file() else b''
        origin = 'working-tree'
        if hashlib.sha256(data).hexdigest() != expected:
            for revision in args.revision:
                proc = subprocess.run(['git', '-C', str(root), 'show', revision + ':' + relative], capture_output=True)
                if proc.returncode == 0 and hashlib.sha256(proc.stdout).hexdigest() == expected:
                    data, origin = proc.stdout, revision
                    break
        valid = hashlib.sha256(data).hexdigest() == expected
        records[relative] = dict(sha256=expected, status='matched' if valid else 'missing', origin=origin if valid else None)
        if valid:
            contents[relative] = data
    dest.mkdir(parents=True)
    for relative, data in contents.items():
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if hashlib.sha256(target.read_bytes()).hexdigest() != pins[relative]:
            raise ValueError('Recovered file differs from frozen bytes')
    (dest / 'controllers').mkdir(exist_ok=True)
    (dest / 'controllers/release_source_hashes.json').write_bytes(pin_bytes)
    result = dict(schema='clear-native-frozen-source-recovery-v1', files=records,
        matched_files=len(contents), required_files=len(pins),
        restored_from_history=sum(r['origin'] not in (None, 'working-tree') for r in records.values()),
        source_pin_sha256=hashlib.sha256(pin_bytes).hexdigest(),
        original_sources_modified=False, original_pins_modified=False,
        executable_dependency_closure_verified=False, controller_qualification_performed=False,
        anonymous_publication_audit_performed=False)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}))
    return int(len(contents) != len(pins))


if __name__ == '__main__':
    raise SystemExit(main())
