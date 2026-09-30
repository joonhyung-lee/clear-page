"""Preserve native scene refs when file playback reuses the same message.

Viser's addSceneNode clears its Three.js ref even when the incoming message is
the exact object already in the store. React's message selector then skips the
render, leaving the mounted mesh absent from nodeRefFromName. This affects
rewinds, loops, and seeks that resend the time-zero declarations. Only clear
the ref when the message changes, so real replacements still remount normally.
"""
import base64
import json
from pathlib import Path
import re

import zstandard

ROOT = Path(__file__).resolve().parents[1]
OLD = 'a&&delete A[i.name],e.set(o)'
NEW = 'a&&a.message!==i&&delete A[i.name],e.set(o)'


def main():
    path = ROOT / 'assets/viser/index.html'
    html = path.read_text()
    match = re.search(r'data-c="([^"]+)"', html)
    assert match, 'Expected standalone Viser compressed JavaScript'
    code = zstandard.ZstdDecompressor().decompress(base64.b64decode(match[1])).decode()
    if NEW not in code:
        assert code.count(OLD) == 1, 'Review upstream addSceneNode before applying patch'
        code = code.replace(OLD, NEW)
        encoded = base64.b64encode(zstandard.ZstdCompressor(level=19).compress(code.encode())).decode()
        html = html[:match.start(1)] + encoded + html[match.end(1):]
        html, count = re.subn(r'data-cs="\d+"', f'data-cs="{len(code.encode())}"', html)
        assert count == 1
        path.write_text(html)
    (ROOT / 'assets/viser/runtime-hex.js').write_text(
        'window.CLEAR_VIEWER_HEX = ' + json.dumps(path.read_bytes().hex()) + ';\n')
    print('Patched native replay ref preservation for identical scene messages')


if __name__ == '__main__':
    main()
