"""Create a separate anonymous candidate from trusted, hash-verified models.

Only approved origin/config path strings are rewritten in protocol-2 data.pkl.
Tensor storage members are copied unchanged. Never torch.save, modify the input
package, or inherit historical native certification for the new file hashes.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import pickletools
import re
import shutil
import struct
import sys
import zipfile


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sensitive(value, terms):
    return (bool(re.search(r'/(?:home|mnt)/', value, re.I))
            or any(term.casefold() in value.casefold() for term in terms)
            or bool(re.search(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}', value, re.I)))


def replacement(value, trail):
    if trail in {('development_study', 'root'), ('development_study', 'source'), ('config',)}:
        return '<ARCHIVE>/' + hashlib.sha256(value.encode()).hexdigest()[:24]
    for prefix in [('config', 'model'), ('model_config',), ('training_state', 'identity', 'config', 'model')]:
        if trail == (*prefix, 'cdgs', 'repository'):
            return 'third_party/CDGS_toydomain'
        if trail in {(*prefix, 'get_encoder', 'repository'), (*prefix, 'get_encoder', 'dependencies')}:
            return 'third_party/get_zero'
    raise ValueError('Unapproved metadata field; manual classification required')


def collect_replacements(value, terms):
    mapping, fields = {}, []
    def walk(node, trail=()):
        if isinstance(node, str) and sensitive(node, terms):
            new = replacement(node, trail)
            if node in mapping and mapping[node] != new:
                raise ValueError('Conflicting metadata roles')
            mapping[node] = new
            fields.append('.'.join(trail))
        elif isinstance(node, dict):
            for key, child in node.items():
                if isinstance(key, str) and sensitive(key, terms):
                    raise ValueError('A dictionary key requires review')
                walk(child, (*trail, str(key)))
        elif isinstance(node, (list, tuple)):
            for i, child in enumerate(node):
                walk(child, (*trail, str(i)))
    walk(value)
    return mapping, fields


def rewrite_pickle(data, mapping):
    ops = list(pickletools.genops(data))
    if not ops or ops[0][0].name != 'PROTO' or ops[0][1] != 2:
        raise ValueError('Only inspected protocol-2 checkpoints are supported')
    if ops[-1][0].name != 'STOP' or ops[-1][2] + 1 != len(data):
        raise ValueError('Trailing or incomplete pickle data')
    result, seen = [], set()
    for i, (op, value, start) in enumerate(ops):
        end = ops[i+1][2] if i+1 < len(ops) else len(data)
        if isinstance(value, str) and value in mapping:
            if op.name != 'BINUNICODE':
                raise ValueError('Unsupported metadata opcode')
            encoded = mapping[value].encode('utf-8')
            result.append(b'X' + struct.pack('<I', len(encoded)) + encoded)
            seen.add(value)
        else:
            result.append(data[start:end])
    if seen != mapping.keys():
        raise ValueError('Not every approved string was rewritten')
    return b''.join(result)


def compare_values(before, after, mapping, trail=()):
    """Check every field, including optimizer tensors, dict keys and attributes."""
    import torch
    import numpy as np
    if type(before) is not type(after):
        raise ValueError('Value type changed')
    count = 0
    if isinstance(before, torch.Tensor):
        if (before.dtype != after.dtype or before.shape != after.shape
                or before.stride() != after.stride() or before.storage_offset() != after.storage_offset()
                or before.requires_grad != after.requires_grad
                or not torch.equal(before, after)):
            raise ValueError('Tensor changed')
        count = 1
    elif isinstance(before, np.ndarray):
        if before.dtype != after.dtype or not np.array_equal(before, after):
            raise ValueError('Array changed')
    elif isinstance(before, dict):
        if list(before) != list(after):
            raise ValueError('Dictionary keys changed')
        count = sum(compare_values(v, after[k], mapping, (*trail, str(k))) for k, v in before.items())
        if getattr(before, '__dict__', {}) or getattr(after, '__dict__', {}):
            count += compare_values(before.__dict__, after.__dict__, mapping, (*trail, '__attributes__'))
    elif isinstance(before, (list, tuple)):
        if len(before) != len(after):
            raise ValueError('Sequence length changed')
        count = sum(compare_values(v, w, mapping, (*trail, str(i))) for i, (v, w) in enumerate(zip(before, after)))
    elif isinstance(before, str) and before in mapping:
        if after != mapping[before] or after != replacement(before, trail):
            raise ValueError('Metadata replacement used outside approved field')
    elif before != after:
        raise ValueError('Non-metadata value changed')
    return count


def derive(original, destination, expected, terms):
    import torch
    if sha(original) != expected:
        raise ValueError('Source hash changed before loading')
    if original.resolve() == destination.resolve():
        raise ValueError('Original must never be overwritten')
    before = torch.load(original, map_location='cpu', weights_only=False)
    mapping, fields = collect_replacements(before, terms)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.partial')
    storage = {}
    try:
        if mapping:
            with zipfile.ZipFile(original) as src, zipfile.ZipFile(temporary, 'w') as dst:
                if len(src.namelist()) != len(set(src.namelist())):
                    raise ValueError('Duplicate archive member')
                pickles = [n for n in src.namelist() if n.endswith('/data.pkl')]
                if len(pickles) != 1:
                    raise ValueError('Ambiguous checkpoint metadata')
                dst.comment = src.comment
                for info in src.infolist():
                    data = src.read(info)
                    if info.filename == pickles[0]:
                        data = rewrite_pickle(data, mapping)
                    else:
                        storage[info.filename] = hashlib.sha256(data).hexdigest()
                    dst.writestr(copy.copy(info), data)
            with zipfile.ZipFile(temporary) as dst:
                for name, digest in storage.items():
                    if hashlib.sha256(dst.read(name)).hexdigest() != digest:
                        raise ValueError('Non-metadata archive member changed')
        else:
            shutil.copyfile(original, temporary)
        after = torch.load(temporary, map_location='cpu', weights_only=False)
        count = compare_values(before, after, mapping)
        if not count:
            raise ValueError('No model tensors')
        if collect_replacements(after, terms)[0]:
            raise ValueError('Sensitive metadata remains')
        if sha(original) != expected:
            raise ValueError('Original checkpoint changed')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(source_sha256=expected, sha256=sha(destination), changed_fields=fields,
                tensor_count=count, tensors_equal=True, originals_unchanged=True,
                non_metadata_members_unchanged=True, serialized_with_torch_save=False)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def document_candidate(dest, result):
    prior = dest / 'docs/original_assembly_status.md'
    if not prior.exists():
        shutil.copyfile(dest / 'docs/STATUS.md', prior)
    (dest / 'docs/STATUS.md').write_text('''# Anonymous candidate status

This is a separate derivative of the local standalone working distribution.
Original research files and the original assembly remain unchanged.

## Checkpoints

All 153 available models are included. Ninety-nine require metadata-only path
changes; 54 are byte-identical copies. Every decoded tensor and numerical field
was compared with its source. All ZIP members other than data.pkl are unchanged.
No checkpoint was re-saved with torch.save. Original and released hashes are
recorded separately in checkpoint_derivatives.json and checkpoints.json.
The 31 previously withheld available models are included after this verification.
There are still 41 missing references representing 31 unique unavailable models.

Grid evaluation and staged training contracts now reference the released hashes
and retain original hashes explicitly. Historical command records and controller
certificates have not been rewritten to claim validation of the derivatives.
GET/CDGS repository metadata uses the same relative locations as the packaged
configuration. Those optional third-party runtimes remain incomplete.

## Validation scope

checkpoint_derivatives.json records tensor/storage/metadata equivalence.
Run tools/verify.py --smoke, tools/checkpoints.py --verify and
tools/check_grid_training.py to check the candidate runtime and model loading.
The current tree_audit.json is valid only for the files/hashes it lists.
Passing its identifier/path scan does not certify imagery, licensing or hosting.

Reports inherited from the original assembly describe that earlier snapshot.
In particular checkpoint_metadata_audit.json and checkpoint_path_review.json
describe ORIGINAL checkpoint bytes. Their findings motivated the derivatives.
reassembly_check.json and validation.json likewise describe the original tree.
The earlier assembly status is retained in original_assembly_status.md.

## Outstanding work

- The latest handoff source is unavailable on this host.
- 31 unique selected model hashes and 28 raw Maze v4 probe inputs are missing.
- Native source recovery is separate from dependency assembly and qualification.
  native_source_recovery.json, when present, records the exact recovery scope.
- Native policies/dependencies, clean installation and full experiment
  reproduction still require verification.
- GET/Husky redistribution rights and anonymous hosting remain unresolved.

This candidate is not a complete release and has not been pushed or published.
''')
    (dest / 'README.md').write_text('''# CLEAR standalone anonymous candidate

Separate checkpoint derivatives with original weights and numerical state.
This working candidate is incomplete and has not been published.

See [status](docs/STATUS.md), [training commands](docs/TRAINING.md),
[checkpoint equivalence](docs/checkpoint_derivatives.json) and
[model availability](docs/checkpoints.json).

```bash
python run.py --help
python tools/verify.py --smoke
python tools/checkpoints.py --verify
python tools/check_grid_training.py
```
''')
    audit_path = dest / 'docs/completion_audit.json'
    audit = json.loads(audit_path.read_text())
    for gate in audit['gates']:
        if gate['requirement'] == 'selected_checkpoint_bytes':
            gate.update(status='partially-complete', evidence='153 available models verified; 99 metadata-only derivatives, 54 exact copies; 31 unique selected hashes missing')
        if gate['requirement'] == 'anonymous_payload':
            gate.update(status='pending-candidate-tree-audit', evidence='checkpoint_derivatives.json; tensor equivalence verified, full tree scan required after assembly')
    audit['anonymous_derivatives_authorized'] = True
    write_json(audit_path, audit)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package', required=True, type=Path)
    p.add_argument('--destination', required=True, type=Path)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--store', action='append', type=Path, default=[])
    p.add_argument('--private-term', action='append', required=True)
    args = p.parse_args()
    original, dest = args.package.resolve(), args.destination.resolve()
    if dest.exists() or dest.is_relative_to(original) or original.is_relative_to(dest):
        raise ValueError('Use a new, separate destination')
    if any(not s.strip() for s in args.private_term):
        raise ValueError('Private terms must not be empty')
    shutil.copytree(original, dest, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git', '.venv', '.pytest_cache'))
    sys.path.insert(0, str(dest / 'runtime'))
    import torch
    torch.set_num_threads(2)
    registry = json.loads((dest / 'docs/checkpoints.json').read_text())
    inventory = json.loads((dest / 'docs/checkpoint_inventory.json').read_text())
    manifest = json.loads((dest / 'docs/artifact_manifest.json').read_text())
    roots = {'source': args.source, **{f'store-{i}': s for i, s in enumerate(args.store)}}
    inputs = {}
    for row in registry['references']:
        if row['status'] == 'packaged':
            inputs[row['sha256']] = (original / row['path'], row['path'], None)
    for row in inventory['checkpoints']:
        if row['status'] == 'verified' and row['sha256'] not in inputs:
            loc = row['locations'][0]
            relative = f"runtime/assets/checkpoints/anonymous/{row['sha256']}.pt"
            inputs[row['sha256']] = (roots[loc['origin']] / loc['path'], relative, loc)
    reports = {}
    for i, (digest, (path, relative, loc)) in enumerate(inputs.items()):
        info = derive(path, dest / relative, digest, args.private_term)
        info['path'] = relative
        reports[digest] = info
        record = manifest['files'].setdefault(relative, dict(source_origin=loc['origin'],
            source_path=loc['path'], source_sha256=digest, changes=[])) if loc else manifest['files'][relative]
        record.update(sha256=info['sha256'], bytes=(dest / relative).stat().st_size)
        if info['changed_fields']:
            record['changes'].append(dict(operation='anonymous derivative; tensor members unchanged', fields=info['changed_fields']))
        print(f'Checked checkpoint {i+1}/{len(inputs)}', flush=True) if (i+1) % 25 == 0 else None
    for row in registry['references']:
        if row['sha256'] in reports:
            info = reports[row['sha256']]
            row.update(source_sha256=row['sha256'], sha256=info['sha256'], path=info['path'], status='packaged')
    registry.update(schema='clear-standalone-checkpoints-v2', unique_packaged_models=len(reports),
                    anonymous_derivatives=True, full_release_validated=False)
    # Active local contracts use released bytes; historical hashes remain explicit.
    contracts = [('runtime/training/exp1/ancestry.json', 'source', 'source_sha256'),
                 ('runtime/experiments/exp1/configs/paper.json', 'path', 'sha256')]
    for relative, path_key, hash_key in contracts:
        path = dest / relative
        value = json.loads(path.read_text())
        def update(node):
            if isinstance(node, dict):
                old = node.get(hash_key)
                if path_key in node and isinstance(old, str) and old in reports:
                    node['original_' + hash_key] = old
                    node[hash_key] = reports[old]['sha256']
                    node[path_key] = str(Path(reports[old]['path']).relative_to('runtime'))
                for child in list(node.values()):
                    update(child)
            elif isinstance(node, list):
                for child in node:
                    update(child)
        update(value)
        write_json(path, value)
        record = manifest['files'][relative]
        record.update(sha256=sha(path), bytes=path.stat().st_size)
        record['changes'].append('Local checkpoint identities point to anonymous derivatives; original hashes retained')
    write_json(dest / 'docs/checkpoints.json', registry)
    write_json(dest / 'docs/artifact_manifest.json', manifest)
    result = dict(schema='clear-anonymous-checkpoint-derivatives-v1', models=reports,
        checked_models=len(reports), derived_models=sum(bool(r['changed_fields']) for r in reports.values()),
        missing_references=sum(r['status'] != 'packaged' for r in registry['references']),
        scope='Every decoded tensor/numeric field and non-metadata ZIP member compared; no physical qualification',
        historical_native_certification_inherited=False, full_release_validated=False)
    write_json(dest / 'docs/checkpoint_derivatives.json', result)
    document_candidate(dest, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'models'}))


if __name__ == '__main__':
    main()
