"""Regression checks for metadata scanning without mistaking numeric bytes for text."""
import ast
import base64
import binascii
import gzip
import json
import re
from pathlib import Path
import msgpack
import zstandard

source = ast.parse(Path(__file__).with_name('audit_anonymity.py').read_text())
namespace = dict(globals(), failed=set(), decoded=0, needles=[b'private-fixture'],
    patterns=[rb'/' + rb'home/[a-z0-9_-]+', rb'[a-z0-9_.+-]+@[a-z0-9.-]+\.[a-z]{2,}'])
exec(compile(ast.Module(body=[node for node in source.body if isinstance(node, ast.FunctionDef)], type_ignores=[]), 'audit-functions', 'exec'), namespace)

def check(buffer, dtype, metadata='', trailing=b''):
    record = {'binaryBufferLengths': [len(buffer)], 'message': {
        'label': metadata, 'array': {'__binary_index': 0, 'dtype': dtype}}}
    packed = msgpack.packb(record, use_bin_type=True)
    raw = len(packed).to_bytes(8, 'little') + packed
    raw += b'\0' * (-len(raw) % 8) + buffer + trailing
    namespace['failed'].clear()
    namespace['scan_recording'](raw, 'fixture')
    return set(namespace['failed'])

coincidental = b'j' + b'@' + b'bA.Ls\0'
assert not check(coincidental, '<f4')
assert check(coincidental, '|u1')
assert check(b'\0'*8, '<f4', 'fixture' + '@' + 'example.org')
assert check(b'\0'*8, '<f4', '/' + 'home/' + 'private-fixture')
assert check(b'private-fixture\0', '<f4')
assert check(b'\0'*8, '<f4', trailing=b'additional data')
print('PASS typed numeric buffers, unknown payloads, metadata identities and unparsed bytes')
