"""Package original Grid stage inputs and ancestry without changing training values."""
import argparse
import hashlib
import json
from pathlib import Path


STAGES = ('structural_training_20260913_a', 'structural_replay_20260913_c',
          'structural_gentle_20260913_d')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sanitize_metadata(value, fields):
    def opaque(text):
        return '<ARCHIVE>/' + sha(text.encode())[:24]
    if 'stress_source' in value and value['stress_source'].startswith('/'):
        value['stress_source'] = opaque(value['stress_source'])
        fields.append('stress_source')
    for i, stage in enumerate(value.get('stages', [])):
        settings = stage.get('original_settings', {})
        for key in ('root', 'source'):
            if isinstance(settings.get(key), str) and settings[key].startswith('/'):
                settings[key] = opaque(settings[key])
                fields.append(f'stages[{i}].original_settings.{key}')
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True)
    p.add_argument('--private-term', action='append', required=True)
    a = p.parse_args()
    source, root = a.source.resolve(), a.destination.resolve()
    inputs = {'training/exp1/ancestry.json'}
    for stage in STAGES:
        prefix = 'training/exp1/stages/' + stage + '/'
        inputs.update((prefix + 'design.json', prefix + 'train.jsonl'))
        design = json.loads((source / (prefix + 'design.json')).read_text())
        for key in ('stress_val', 'original_val'):
            relative = design[key]
            path = source / relative
            if not path.resolve().is_relative_to(source) or sha(path.read_bytes()) != design[key + '_sha256']:
                raise ValueError('Validation split differs from frozen design')
            inputs.add(relative)
        if sha((source / (prefix + 'train.jsonl')).read_bytes()) != design['train_sha256']:
            raise ValueError('Training data differs from frozen design')
    inputs.update('experiments/exp1/configs/' + n + '.yaml' for n in
                  ('leap2026_plancode', 'leap2026_rankmask_causal', 'leap2026_rankmask_nocausal'))
    upstream = json.loads((source / 'artifact_manifest.json').read_text())['files']
    apath = root / 'docs/artifact_manifest.json'
    artifacts = json.loads(apath.read_text())
    for relative in sorted(inputs):
        original = (source / relative).read_bytes()
        if relative in upstream and sha(original) != upstream[relative]['sha256']:
            raise ValueError('Source artifact hash mismatch: ' + relative)
        changed, data = [], original
        if relative.endswith('design.json') or relative.endswith('ancestry.json'):
            value = sanitize_metadata(json.loads(original), changed)
            if changed:
                data = (json.dumps(value, indent=2) + '\n').encode()
        text = data.decode()
        if '/home/' in text or '/mnt/' in text or any(t.lower() in text.lower() for t in a.private_term):
            raise ValueError('Unreviewed identity or path in ' + relative)
        target = root / 'runtime' / relative
        if target.exists() and target.read_bytes() != data:
            raise ValueError('Existing packaged file differs: ' + relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        artifacts['files']['runtime/' + relative] = dict(source_path=relative,
            source_sha256=sha(original), sha256=sha(data), bytes=len(data),
            changes=['anonymize origin-only metadata'] if changed else [], changed_fields=changed)
    apath.write_text(json.dumps(artifacts, indent=2) + '\n')
    script = 'scripts/leap2026/exp1_wp1_train.py'
    data = (source / script).read_bytes()
    if any(t.lower().encode() in data.lower() for t in a.private_term):
        raise ValueError('Private identifier in stage runner')
    target = root / 'runtime' / script
    if target.exists() and target.read_bytes() != data:
        raise ValueError('Existing stage runner differs')
    target.write_bytes(data)
    spath = root / 'docs/source_manifest.json'
    sm = json.loads(spath.read_text())
    sm['files']['runtime/' + script] = dict(source_path=script, source_sha256=sha(data),
        sha256=sha(data), bytes=len(data), changes=[])
    spath.write_text(json.dumps(sm, indent=2) + '\n')
    print(json.dumps(dict(grid_inputs=len(inputs), original_stage_runner=True)))


if __name__ == '__main__':
    main()
