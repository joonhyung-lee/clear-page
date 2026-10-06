"""Reject missing explicitly requested Maze v4 probe supervision in the export."""
import argparse
import hashlib
import json
from pathlib import Path

OLD = '''    if probes_dir is None or not probes_dir.exists():
        return None
'''
NEW = '''    if probes_dir is None:
        return None
    if not probes_dir.is_dir():
        raise FileNotFoundError("Requested probe directory is unavailable: " + str(probes_dir))
'''
OLD_BODY = '''        if p.exists():
            out[body] = list(aggregate(list(read_trials(p))).values())
'''
NEW_BODY = '''        if not p.is_file():
            raise FileNotFoundError("Requested probe supervision is incomplete: " + str(p))
        out[body] = list(aggregate(list(read_trials(p))).values())
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destination', required=True, type=Path)
    a = p.parse_args()
    root = a.destination.resolve()
    key = 'runtime/experiments/exp5_maze_v4/train.py'
    path = root / key
    mp = root / 'docs/source_manifest.json'
    manifest = json.loads(mp.read_text())
    original = path.read_bytes()
    if hashlib.sha256(original).hexdigest() != manifest['files'][key]['sha256']:
        raise ValueError('Exported training source was edited outside the manifest')
    text = original.decode()
    if NEW not in text or NEW_BODY not in text:
        if text.count(OLD) != 1 or text.count(OLD_BODY) != 1:
            raise ValueError('Original probe loader changed; review the patch')
        text = text.replace(OLD, NEW).replace(OLD_BODY, NEW_BODY)
        path.write_text(text)
        row = manifest['files'][key]
        row['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        row['bytes'] = path.stat().st_size
        row['changes'].append('Reject absent directory/body trial files when probe supervision was explicitly requested; aggregation and optional no-probe mode unchanged')
        mp.write_text(json.dumps(manifest, indent=2) + '\n')
    print('Maze v4 explicit probe input guard installed')


if __name__ == '__main__':
    main()
