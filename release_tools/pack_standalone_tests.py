"""Include relevant original planner regressions and their local import closure."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from select_standalone import select

TESTS = [
    'tests.test_shared_morphology_v3', 'tests.test_shared_balanced_sampling',
    'tests.test_ordering_ablation', 'tests.test_inference_recipe',
    'tests.test_actual_target_validation', 'tests.test_candidate_orders_guard',
    'tests.model.test_flow_trace',
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True)
    args = p.parse_args()
    source, root = args.source.resolve(), args.destination.resolve()
    expanded = select(source, TESTS)
    mpath = root / 'docs/source_manifest.json'
    manifest = json.loads(mpath.read_text())
    added = 0
    for relative in expanded['files']:
        key = 'runtime/' + relative
        target = root / key
        if key in manifest['files']:
            if sha(target) != manifest['files'][key]['sha256']:
                raise ValueError('Existing source differs: ' + relative)
            continue
        original = source / relative
        if target.exists() and sha(target) != sha(original):
            raise ValueError('Refusing to replace a modified file: ' + relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        manifest['files'][key] = dict(source_path=relative, source_sha256=sha(original),
            sha256=sha(target), bytes=target.stat().st_size, changes=[])
        added += 1
    mpath.write_text(json.dumps(manifest, indent=2) + '\n')
    apath = root / 'docs/artifact_manifest.json'
    artifacts = json.loads(apath.read_text())
    # Some initial working exports placed these tests in the input manifest.
    artifacts['files'] = {k: v for k, v in artifacts['files'].items() if k not in manifest['files']}
    apath.write_text(json.dumps(artifacts, indent=2) + '\n')
    expanded['regression_modules'] = TESTS
    (root / 'docs/source_selection.json').write_text(json.dumps(expanded, indent=2) + '\n')
    print(json.dumps(dict(added_source_files=added, regression_modules=len(TESTS))))


if __name__ == '__main__':
    main()
