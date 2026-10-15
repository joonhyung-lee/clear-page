"""Download the 153 pretrained checkpoints into ckpts/ from the anonymous mirror and link them."""
import argparse
import hashlib
import json
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from link_checkpoints import link_checkpoints

ROOT = Path(__file__).resolve().parents[1]
MIRROR = 'https://anonymous-hf.com/api/a/p5icltdspejh/resolve/'


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


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fetch(base, item, progress, attempts=3):
    target = ROOT / item['path']
    if target.is_file() and sha256(target) == item['sha256']:
        progress.add(done=True)
        return 'kept'
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + '.part')
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(base + item['path'], headers={'User-Agent': 'clear-fetch/1.0'})
            with urllib.request.urlopen(request, timeout=120) as response, partial.open('wb') as out:
                stream(response, out, progress)
            if sha256(partial) == item['sha256']:
                partial.replace(target)
                progress.add(done=True)
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
    progress = Progress('checkpoints', len(items))
    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(lambda item: fetch(args.base_url, item, progress), items))
    progress.close()
    print(f'{results.count("downloaded")} downloaded, {results.count("kept")} already present, {len(items)} total')
    print(f'Checkpoint paths ready ({link_checkpoints(ROOT)} new links).')


if __name__ == '__main__':
    sys.exit(main())
