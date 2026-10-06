"""Export recorded revision commands and verify their referenced inputs.

Commands are historical records, including failed launches and event notes.
They are never executed or silently rewritten into claimed runnable recipes.
Private repository and temporary scratch prefixes are normalized in the exports.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import tarfile

from inventory_standalone import HASH, references_in, relative_reference

PREFIX = re.compile(r'/(?:home|mnt)/[^\s\'"<>]*?/clear(?=/|\s|$)')
SCRATCH = re.compile(r'/tmp/[^\s\'"<>]*?/scratchpad(?=/|\s|$)')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def normalize(value, changed, field='$'):
    if isinstance(value, str):
        result = PREFIX.sub('.', value)
        result = SCRATCH.sub(lambda m: '<ARCHIVE>/scratch-' + hashlib.sha256(
            m[0].encode()).hexdigest()[:16], result)
        if result != value:
            changed.append(field)
        if '/home/' in result or '/mnt/' in result:
            raise ValueError('Unrecognized private path at ' + field)
        return result
    if isinstance(value, list):
        return [normalize(v, changed, f'{field}[{i}]') for i, v in enumerate(value)]
    if isinstance(value, dict):
        out = {}
        for key, child in value.items():
            replacement = normalize(key, changed, field + '.<key>')
            if replacement in out:
                raise ValueError('Normalization caused a duplicate key')
            out[replacement] = normalize(child, changed, field + '.' + replacement)
        return out
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True)
    p.add_argument('--private-term', action='append', required=True)
    a = p.parse_args()
    source, root = a.source.resolve(), a.destination.resolve()
    inventory = json.loads((root / 'docs/checkpoint_inventory.json').read_text())
    registry = json.loads((root / 'docs/checkpoints.json').read_text())
    am_path = root / 'docs/artifact_manifest.json'
    artifacts = json.loads(am_path.read_text())
    manifests = {r['manifest'] for r in inventory['checkpoints']}
    manifests.update(r for r in references_in((source / 'outputs/leap2026/PAPER_MAP.md').read_text())
                     if r.endswith('manifest.json'))
    cache, records = {}, []

    def digest(path):
        if path not in cache:
            cache[path] = sha(path)
        return cache[path]

    for relative in sorted(manifests):
        origin = source / relative
        original = json.loads(origin.read_text())
        changed = []
        exported = normalize(original, changed)
        content = json.dumps(exported, indent=2) + '\n'
        if any(t.lower() in content.lower() for t in a.private_term):
            raise ValueError('Private identifier requires review: ' + relative)
        destination = 'runtime/' + relative
        target = root / destination
        if target.exists() and target.read_text() != content:
            raise ValueError('Existing manifest differs: ' + relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        artifacts['files'][destination] = dict(source_path=relative,
            source_sha256=digest(origin), sha256=sha(target), bytes=target.stat().st_size,
            changes=['normalize private repository and temporary scratch prefixes'] if changed else [],
            changed_fields=changed)
        inputs = []
        for category in ('configs', 'datasets'):
            for label, recorded in original.get(category, {}).items():
                ref = relative_reference(label)
                expected = HASH.fullmatch(str(recorded))
                expected = expected[1] if expected else None
                entry = dict(category=category, reference=ref or 'external-input',
                             expected_sha256=expected, source_status='missing',
                             packaged_status='not-packaged')
                path = source / ref if ref else None
                if ref and '.tar.gz:' in ref:
                    archive_name, member = ref.split(':', 1)
                    candidates = [relative_reference(k) for k in original.get('datasets', {})
                                  if Path(k).name == archive_name]
                    if len(candidates) == 1 and candidates[0]:
                        archive = source / candidates[0]
                        if archive.is_file() and archive.resolve().is_relative_to(source):
                            with tarfile.open(archive, 'r:gz') as tf:
                                info = tf.getmember(member)
                                if not info.isfile():
                                    raise ValueError('Expected a regular archive member')
                                with tf.extractfile(info) as stream:
                                    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
                            entry.update(actual_source_sha256=actual, bytes=info.size,
                                source_status='verified' if actual == expected else 'hash-mismatch',
                                source_archive=candidates[0], archive_member=member)
                if path and path.resolve().is_relative_to(source) and path.is_file():
                    entry['actual_source_sha256'] = digest(path)
                    entry['source_status'] = ('verified' if digest(path) == expected
                                              else 'hash-mismatch' if expected else 'unrecorded-hash')
                    entry['bytes'] = path.stat().st_size
                packaged = root / 'runtime' / ref if ref else None
                if packaged and packaged.resolve().is_relative_to(root) and packaged.is_file():
                    entry['packaged_path'] = 'runtime/' + ref
                    entry['packaged_sha256'] = digest(packaged)
                    provenance = artifacts['files'].get('runtime/' + ref, {})
                    if digest(packaged) == expected:
                        entry['packaged_status'] = 'exact'
                    elif provenance.get('source_sha256') == expected and provenance.get('sha256') == digest(packaged):
                        entry['packaged_status'] = 'documented-transformation'
                    else:
                        entry['packaged_status'] = 'different-source-version'
                inputs.append(entry)
        models = [r for r in registry['references'] if r['manifest'] == relative]
        records.append(dict(manifest=relative, exported_manifest=destination,
            original_manifest_sha256=digest(origin), exported_manifest_sha256=sha(target),
            command_records=len(exported.get('commands', [])),
            git_sha=exported.get('git_sha'), seeds=exported.get('seeds', []),
            selection_rule=exported.get('selection_rule'), inputs=inputs,
            checkpoint_references=[{k: r.get(k) for k in ('label','sha256','status','path')} for r in models]))
    # Resolve cross-manifest inputs after every export has been recorded.
    for record in records:
        for entry in record['inputs']:
            key = 'runtime/' + entry['reference']
            provenance = artifacts['files'].get(key)
            if provenance and (root / key).is_file():
                actual = sha(root / key)
                entry.update(packaged_path=key, packaged_sha256=actual)
                if actual == entry['expected_sha256']:
                    entry['packaged_status'] = 'exact'
                elif provenance.get('source_sha256') == entry['expected_sha256'] and provenance['sha256'] == actual:
                    entry['packaged_status'] = 'documented-transformation'
    counts = Counter(i['source_status'] for r in records for i in r['inputs'])
    statuses = Counter(i['packaged_status'] for r in records for i in r['inputs'])
    report = dict(schema='clear-standalone-revision-recipes-v1',
        source_revision=inventory['source_revision'], records=records,
        source_input_status=dict(counts), packaged_input_status=dict(statuses),
        commands_executed=False, full_reproduction_verified=False,
        note='Historical command arrays include timestamps, event notes and failed launches. '
             'Private repository and temporary scratch prefixes are normalized. Controller identities remain unchanged.')
    (root / 'docs/revision_recipes.json').write_text(json.dumps(report, indent=2) + '\n')
    am_path.write_text(json.dumps(artifacts, indent=2) + '\n')
    lines = ['# Revision training and evaluation records', '',
        'These are the recorded commands for the available source revision, not a newly',
        'validated end-to-end recipe. Each linked manifest preserves its command array,',
        'seeds, selection rule and input hashes. Private checkout prefixes become `.`.',
        'Temporary scratch roots become opaque `<ARCHIVE>/scratch-...` references.',
        'Run locations therefore refer to `runtime/`. Some entries are timestamped',
        'event notes or failed attempts, and some commands omit the Python executable.',
        'Do not run these arrays as a shell script.', '',
        'Exact input availability and checkpoint release paths are in',
        '[revision_recipes.json](revision_recipes.json). Original hashes remain unchanged.',
        'A source hash mismatch is an unresolved discrepancy, not a new accepted hash.', '']
    for record in records:
        title = record['manifest'].removeprefix('outputs/leap2026/').removesuffix('/manifest.json')
        lines += ['## ' + title, '',
            f"[Recorded commands and metadata](../{record['exported_manifest']})", '',
            f"Command/event records: {record['command_records']}. Seeds: `{record['seeds']}`.", '',
            'Selection rule: ' + str(record['selection_rule']), '',
            '| Input status | Count |', '| --- | ---: |']
        for status, count in sorted(Counter(i['packaged_status'] for i in record['inputs']).items()):
            lines.append(f'| {status} | {count} |')
        lines.append('')
    (root / 'docs/REVISION_RECIPES.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(dict(manifests=len(records), command_records=sum(r['command_records'] for r in records),
                         source_inputs=dict(counts), packaged_inputs=dict(statuses))))


if __name__ == '__main__':
    main()
