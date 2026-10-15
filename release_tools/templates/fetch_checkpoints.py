"""Download the 153 pretrained checkpoints into ckpts/ from the anonymous mirror and link them."""
import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from link_checkpoints import link_checkpoints

ROOT = Path(__file__).resolve().parents[1]
MIRROR = 'https://anonymous-hf.com/api/a/p5icltdspejh/resolve/'


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fetch(base, item, attempts=3):
    target = ROOT / item['path']
    if target.is_file() and sha256(target) == item['sha256']:
        return 'kept'
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + '.part')
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(base + item['path'], headers={'User-Agent': 'clear-fetch/1.0'})
            with urllib.request.urlopen(request, timeout=120) as response, partial.open('wb') as out:
                shutil.copyfileobj(response, out, 1 << 20)
            if sha256(partial) == item['sha256']:
                partial.replace(target)
                return 'downloaded'
            error = ValueError('checksum mismatch')
        except OSError as exc:
            error = exc
        partial.unlink(missing_ok=True)
    raise RuntimeError(f'{item["path"]}: {error}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default=MIRROR, help='directory URL that serves checkpoints/<path>')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    records = json.loads((ROOT / 'docs/checkpoint_paths.json').read_text())['models']
    items = list({item['path']: item for item in records.values()}.values())
    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(lambda item: fetch(args.base_url, item), items))
    print(f'{results.count("downloaded")} downloaded, {results.count("kept")} already present, {len(items)} total')
    print(f'Checkpoint paths ready ({link_checkpoints(ROOT)} new links).')


if __name__ == '__main__':
    sys.exit(main())
