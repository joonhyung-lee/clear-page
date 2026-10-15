"""Download this repository from the anonymous mirror: source tree, then the checkpoints."""
import argparse
import hashlib
import json
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MIRROR = 'https://anonymous-hf.com/api/a/p5icltdspejh/'
HEADERS = {'User-Agent': 'clear-fetch/1.0'}


class Progress:
    """One-line progress bar on stderr (files done, MB, MB/s); a plain summary line when not a terminal."""

    def __init__(self, label, total):
        self.label, self.total, self.done, self.bytes = label, total, 0, 0
        self.lock, self.start, self.drawn = threading.Lock(), time.time(), 0.
        self.tty = sys.stderr.isatty()

    def add(self, nbytes=0, done=False):
        with self.lock:
            self.bytes += nbytes
            self.done += done
            if self.tty and time.time() - self.drawn > .1:
                self.draw()

    def draw(self, end=''):
        self.drawn = time.time()
        filled = round(30 * self.done / self.total) if self.total else 30
        rate = self.bytes / 1e6 / max(self.drawn - self.start, 1e-9)
        sys.stderr.write(f'\r{self.label} [{"#" * filled}{"." * (30 - filled)}] {self.done}/{self.total} files'
                         f'  {self.bytes / 1e6:.1f} MB  {rate:.1f} MB/s{end}')
        sys.stderr.flush()

    def close(self):
        self.draw('\n')


def stream(response, out, progress):
    while chunk := response.read(1 << 20):
        out.write(chunk)
        progress.add(len(chunk))


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120)


def walk(skip=('ckpts/',), workers=8):
    """List the repository tree level by level in parallel, reporting progress on stderr."""
    files, folders, pending = [], 0, ['']
    with ThreadPoolExecutor(workers) as pool:
        while pending:
            folders += len(pending)
            listings = list(pool.map(lambda path: json.load(get(MIRROR + 'tree/' + path)), pending))
            pending = [entry['path'] for listing in listings for entry in listing
                       if entry['type'] == 'directory' and not entry['path'].startswith(skip)]
            files += [entry for listing in listings for entry in listing if entry['type'] != 'directory']
            sys.stderr.write(f'\rlisting     {folders} folders  {len(files)} files'); sys.stderr.flush()
    sys.stderr.write('\n')
    return files


def blob_sha1(data):
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def matches(path, oid):
    """The tree lists the git blob id of the file, or of its LFS pointer for large files."""
    data = path.read_bytes()
    pointer = b'version https://git-lfs.github.com/spec/v1\noid sha256:%s\nsize %d\n' % (
        hashlib.sha256(data).hexdigest().encode(), len(data))
    return oid in (blob_sha1(data), blob_sha1(pointer))


def fetch(root, entry, progress):
    target = root / entry['path']
    if target.is_file() and matches(target, entry['oid']):
        progress.add(done=True)
        return 'kept'
    target.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        with get(MIRROR + 'resolve/' + entry['path']) as response, target.open('wb') as out:
            stream(response, out, progress)
        if matches(target, entry['oid']):
            progress.add(done=True)
            return 'downloaded'
    raise RuntimeError('content mismatch: ' + entry['path'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', nargs='?', default='clear')
    parser.add_argument('--no-checkpoints', action='store_true', help='source tree only')
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    root = Path(args.destination).resolve()
    entries = [e for e in walk(workers=args.workers)
               if not (e['path'].startswith('ckpts/') and e['path'].endswith('.pt')) and e['path'] != '.gitattributes']
    progress = Progress('source     ', len(entries))
    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(lambda e: fetch(root, e, progress), entries))
    progress.close()
    print(f'source: {results.count("downloaded")} downloaded, {results.count("kept")} already present, {len(entries)} files -> {root}')
    if not args.no_checkpoints:
        subprocess.check_call([sys.executable, str(root / 'utils/tools/fetch_checkpoints.py')], cwd=root)


if __name__ == '__main__':
    sys.exit(main())
