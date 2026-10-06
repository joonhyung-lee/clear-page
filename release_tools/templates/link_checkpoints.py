"""Connect task-organized checkpoints to the original experiment paths."""
import hashlib
import json
import os
from pathlib import Path


def link_checkpoints(root):
    root = root.resolve()
    records = json.loads((root / 'docs/checkpoint_paths.json').read_text())['models']
    planned = []
    # Validate the complete set before creating any links.
    for old, item in records.items():
        source, target = root / item['path'], root / old
        if not source.resolve().is_relative_to(root) or not target.resolve().is_relative_to(root):
            raise ValueError('Checkpoint path leaves the package')
        if not source.is_file():
            raise FileNotFoundError('Extract clear-pretrained.zip first: ' + item['path'])
        with source.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != item['sha256']:
                raise ValueError('Checkpoint checksum mismatch: ' + item['path'])
        if target.exists() or target.is_symlink():
            if target.resolve() == source.resolve():
                continue
            with target.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() == item['sha256']:
                    continue
            raise FileExistsError('Existing checkpoint differs: ' + old)
        planned.append((source, target))
    for source, target in planned:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(os.path.relpath(source, target.parent))
    return len(planned)


if __name__ == '__main__':
    count = link_checkpoints(Path(__file__).resolve().parents[1])
    print(f'Checkpoint paths ready ({count} new links).')
