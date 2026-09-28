"""Package lazy Viser embeds for static hosts with opaque sandbox origins.

Classic scripts and srcdoc avoid cross-origin fetch and iframe restrictions.
The viewer itself uses Viser's native embedded-recording support.
"""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
viewer = root / 'assets/viser/index.html'
(root / 'assets/viser/runtime-hex.js').write_text(
    'window.CLEAR_VIEWER_HEX = ' + json.dumps(viewer.read_bytes().hex()) + ';\n'
)
for recording in (root / 'assets/recordings').glob('*.viser'):
    encoded = recording.read_bytes().hex()
    recording.with_suffix('.hex.js').write_text(
        'window.CLEAR_RECORDINGS = window.CLEAR_RECORDINGS || {};\n'
        'window.CLEAR_RECORDINGS[' + json.dumps(recording.stem) + '] = '
        + json.dumps(encoded) + ';\n'
    )
print('Packaged viewer runtime and recordings for sandboxed hosting.')
