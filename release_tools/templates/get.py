"""Download this repository from the anonymous mirror: source tree, then the checkpoints."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MIRROR = 'https://anonymous-hf.com/api/a/p5icltdspejh/'
HEADERS = {'User-Agent': 'clear-fetch/1.0'}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120)


def walk(path=''):
    for entry in json.load(get(MIRROR + 'tree/' + path)):
        if entry['type'] == 'directory':
            yield from walk(entry['path'])
        else:
            yield entry


def blob_sha1(data):
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def matches(path, oid):
    """The tree lists the git blob id of the file, or of its LFS pointer for large files."""
    data = path.read_bytes()
    pointer = b'version https://git-lfs.github.com/spec/v1\noid sha256:%s\nsize %d\n' % (
        hashlib.sha256(data).hexdigest().encode(), len(data))
    return oid in (blob_sha1(data), blob_sha1(pointer))


def fetch(root, entry):
    target = root / entry['path']
    if target.is_file() and matches(target, entry['oid']):
        return 'kept'
    target.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        with get(MIRROR + 'resolve/' + entry['path']) as response, target.open('wb') as out:
            shutil.copyfileobj(response, out, 1 << 20)
        if matches(target, entry['oid']):
            return 'downloaded'
    raise RuntimeError('content mismatch: ' + entry['path'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', nargs='?', default='clear')
    parser.add_argument('--no-checkpoints', action='store_true', help='source tree only')
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    root = Path(args.destination).resolve()
    entries = [e for e in walk() if not e['path'].startswith('ckpts/') and e['path'] != '.gitattributes']
    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(lambda e: fetch(root, e), entries))
    print(f'source: {results.count("downloaded")} downloaded, {results.count("kept")} already present, {len(entries)} files -> {root}')
    if not args.no_checkpoints:
        subprocess.check_call([sys.executable, str(root / 'tools/fetch_checkpoints.py')], cwd=root)


if __name__ == '__main__':
    sys.exit(main())
