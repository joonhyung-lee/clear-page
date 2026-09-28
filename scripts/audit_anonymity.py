"""Audit publishable files, decompressed payloads, and media metadata.

Private identifiers are supplied at runtime and never written to a report.
Pixel content still requires visual review and OCR. This is not a certificate
of anonymity and cannot inspect a hosting service's configuration or logs.
"""
import argparse
import base64
import binascii
import getpass
import gzip
import io
import json
import re
import struct
import subprocess
from pathlib import Path
import zstandard
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--term', action='append', default=[])
a = p.parse_args()
needles = [s.lower().encode() for s in [getpass.getuser(), *a.term] if len(s) > 3]
paths = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).split(b'\0')
files = sorted({ROOT / s.decode() for s in paths if s and (ROOT / s.decode()).is_file()})
failed = set()
decoded = 0
patterns = [rb'/' + rb'home/[a-z0-9_-]+', rb'/' + rb'mnt/[^\s"<>]+', rb'[a-z0-9_.+-]+@[a-z0-9.-]+\.[a-z]{2,}']

def fail(label, reason):
    failed.add((label, reason))

def scan(data, label, text=False, vendor=False, depth=0):
    global decoded
    if depth >= 4:
        if any(n in data.lower() or n in label.lower().encode() for n in needles):
            fail(label, 'private identifier')
        return
    encoded_ranges = []
    # The standalone Viser client embeds compressed CSS, JS, and WASM.
    for i, match in enumerate(re.finditer(rb'["\']([A-Za-z0-9+/=]{100,})["\']', data)):
        try:
            payload = base64.b64decode(match[1], validate=True)
        except binascii.Error:
            continue
        if payload.startswith(b'\x28\xb5\x2f\xfd'):
            payload = zstandard.ZstdDecompressor().decompress(payload)
        elif payload.startswith(b'\x1f\x8b'):
            payload = gzip.decompress(payload)
        elif payload[8:12] == b'\x28\xb5\x2f\xfd':
            payload = zstandard.ZstdDecompressor().decompress(payload[8:])
        else:
            continue
        decoded += 1
        encoded_ranges.append(match.span(1))
        scan(payload, f'{label}:embedded-{i}', text=True, vendor=vendor, depth=depth+1)
    for i, match in enumerate(re.finditer(rb'data:[^;,"\s]+;base64,([A-Za-z0-9+/=]+)', data)):
        try:
            payload = base64.b64decode(match[1], validate=True)
        except binascii.Error:
            continue
        encoded_ranges.append(match.span(1))
        scan(payload, f'{label}:data-{i}', vendor=vendor, depth=depth+1)

    # Check the actual decoded payload above, not coincidental name fragments
    # in its base64 spelling. All surrounding plaintext still gets scanned.
    visible = bytearray(data)
    for start, end in encoded_ranges:
        visible[start:end] = b' ' * (end-start)
    plain = bytes(visible)
    if any(n in plain.lower() or n in label.lower().encode() for n in needles):
        fail(label, 'private identifier')
    if text and not vendor and any(re.search(p, plain, re.I) for p in patterns if b'@' not in p or b'@' in plain):
        fail(label, 'private path or email')


def mp4_atoms(data, start, end, label):
    """Walk real ISO BMFF boxes without interpreting compressed frame bytes."""
    while start < end:
        if start + 8 > end:
            fail(label, 'truncated MP4 atom'); return
        size, kind = struct.unpack_from('>I4s', data, start)
        header = 8
        if size == 1:
            size = struct.unpack_from('>Q', data, start+8)[0]; header = 16
        elif size == 0:
            size = end-start
        if size < header or start+size > end:
            fail(label, 'invalid MP4 atom'); return
        body = start+header
        if kind in {b'uuid', b'XMP_', b'loci', b'\xa9ART', b'aART', b'\xa9cmt', b'\xa9nam', b'\xa9day', b'\xa9xyz'}:
            fail(label, 'personal metadata atom')
        if kind == b'hdlr' and data[body+8:body+12] not in (b'vide', b'mdir'):
            fail(label, 'non-video track')
        if kind in (b'mvhd', b'tkhd', b'mdhd'):
            width = 8 if data[body] == 1 else 4
            if any(data[body+4:body+4+width*2]):
                fail(label, 'embedded creation/modification time')
        if kind in (b'moov', b'trak', b'mdia', b'minf', b'stbl', b'udta', b'ilst', b'meta'):
            mp4_atoms(data, body+(4 if kind == b'meta' else 0), start+size, label)
        start += size

for path in files:
    label = str(path.relative_to(ROOT))
    if path.is_symlink(): fail(label, 'symlink')
    data = path.read_bytes()
    if path.suffix == '.viser':
        data = zstandard.ZstdDecompressor().decompress(data[8:]); decoded += 1
    vendor = label.startswith('assets/viser/')
    if label == 'assets/viser/runtime-hex.js' or path.name.endswith('.hex.js'):
        packed = json.loads(data.decode().rsplit(' = ', 1)[1].rstrip(';\n'))
        payload = bytes.fromhex(packed)
        if path.name.endswith('.hex.js'):
            payload = zstandard.ZstdDecompressor().decompress(payload[8:]); decoded += 1
        scan(payload, label+':decoded', text=True, vendor=vendor)
    scan(data, label, text=path.suffix in ('.html', '.css', '.js', '.md', '.svg', '.viser', '.json', '.py', '.txt', '.yml', '.yaml', '.toml', '.xml', '.csv'), vendor=vendor)
    if path.suffix == '.png':
        im = Image.open(io.BytesIO(data))
        if set(im.info) - {'srgb', 'gamma', 'chromaticity', 'transparency', 'aspect'}:
            fail(label, 'PNG ancillary metadata')
    if path.suffix == '.mp4':
        mp4_atoms(data, 0, len(data), label)
if failed:
    for label, reason in sorted(failed): print(f'FAIL {label}: {reason}')
    raise SystemExit(1)
print(f'PASS: {len(files)} publishable files, {decoded} decompressed payloads; identifiers, metadata, and video-only tracks checked.')
