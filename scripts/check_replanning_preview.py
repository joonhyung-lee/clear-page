"""Check the archived rendering fixture against its source and encoded frames.

This validates the renderer, not the requested latest three-method comparison.
"""
import argparse
import hashlib
import json
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image
from replanning_timeline import at_time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--video', type=Path, required=True)
p.add_argument('--episode', type=Path, required=True)
a = p.parse_args()
d = json.loads((a.source / 'timeline.json').read_text())
episode = json.loads(a.episode.read_text())
assert d['episodeSHA256'] == hashlib.sha256(a.episode.read_bytes()).hexdigest()
assert len(d['plans']) == len(episode['plans'])
for prepared, original in zip(d['plans'], episode['plans'], strict=True):
    assert prepared['time'] == original['time_s']
    assert prepared['paths'] == original['plan']['paths']
    assert prepared['order'] == original['order']

# Boundary probes ensure a new plan never leaks into an earlier frame.
assert at_time(d, 0)['current'] is None
for i, plan in enumerate(d['plans']):
    before = at_time(d, plan['time'] - 1e-4)['current']
    assert before == (d['plans'][i - 1] if i else None)
    assert at_time(d, plan['time'])['current'] == plan

# Independent facts from the archived B_solid_v2 episode.
assert at_time(d, 69.69)['current']['order'] == [7, 6, 5, 2, 0]
after = at_time(d, 69.7)
assert after['current']['order'] == [6, 2, 0]
assert after['changes'] == {0: 'unchanged', 2: 'unchanged', 5: 'removed',
                            6: 'changed', 7: 'executed'}
assert at_time(d, 65.7)['event']['object_id'] == 5
assert at_time(d, 69.7)['event'] is None
geometry = np.load(a.source / 'geometry.npz')
body = d['object_bodies']['5']
def position(t):
    return np.array([np.interp(t, geometry['time'], geometry['positions'][:, body, k])
                     for k in range(3)])
assert np.linalg.norm(position(68.7)[:2] - position(65.7)[:2]) > 1

audit = json.loads((a.video / 'render-audit.json').read_text())
assert audit['recordingSHA256'] == d['recordingSHA256']
assert 'Not the requested latest' in audit['scope']
frames, seconds = imageio_ffmpeg.count_frames_and_secs(str(a.video / 'replanning-preview.mp4'))
assert frames == len(audit['frames']) == 376
assert abs(seconds - frames / 25) < .05
for frame in audit['frames']:
    state = at_time(d, frame['time'])
    assert frame['planCall'] == state['current']['call']
    assert frame['changes'] == {str(k): v for k, v in state['changes'].items()}

# Decode the deliverable rather than relying only on sidecar images.
stream = imageio_ffmpeg.read_frames(str(a.video / 'replanning-preview.mp4'))
metadata = next(stream)
assert metadata['size'] == (1280, 720)
probes = {0, frames // 2, frames - 1}
for index, raw in enumerate(stream):
    if index in probes:
        actual = np.frombuffer(raw, dtype=np.uint8).reshape(720, 1280, 3)
        expected = np.asarray(Image.open(a.video / f'frame-{index:04d}.png'))
        assert np.abs(actual.astype(float) - expected.astype(float)).mean() < 3
assert index + 1 == frames
print('PASS source snapshots, causal revisions, removal versus completion, external motion and encoded MP4')
