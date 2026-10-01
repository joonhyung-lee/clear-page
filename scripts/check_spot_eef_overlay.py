"""Check Spot overlays against the gripper poses in the published recordings."""
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image

from recording_io import read_recording, validate_binary_arrays

ROOT = Path(__file__).resolve().parents[1]
for scene in ['mpc-spot-optimized', 'mpc-spot-held-arm']:
    record, buffers = read_recording(ROOT / f'assets/recordings/{scene}.viser')
    validate_binary_arrays(record, buffers)
    messages = record['messages']
    body = {t: m['position'] for t, m in messages
            if m['type'] == 'SetPositionMessage' and m['name'] == '/body-20'}
    current = {t: m['position'] for t, m in messages
            if m['type'] == 'SetPositionMessage' and m['name'] == '/eef-overlay/current'}
    assert body.keys() == current.keys()
    assert np.allclose(list(body.values()), list(current.values()), atol=1e-8)

    def array(name, field, shape):
        props = next(m['props'] for _, m in messages if m.get('name') == name and 'props' in m)
        ref = props[field]
        return np.frombuffer(buffers[ref['__binary_index']], dtype=ref['dtype']).reshape(shape)

    trajectory = np.asarray(list(body.values()))
    segments = array('/eef-overlay/trace', 'points', (-1, 2, 3))
    assert np.allclose(segments, np.stack([trajectory[:-1], trajectory[1:]], axis=1), atol=1e-6)
    anchors = array('/eef-overlay/anchors', 'points', (-1, 3))
    assert len(anchors) == 5
    # Every fixed anchor must lie on an actual recorded segment.
    vectors = trajectory[1:] - trajectory[:-1]
    for anchor in anchors:
        u = np.sum((anchor-trajectory[:-1])*vectors, axis=1)/np.maximum(np.sum(vectors*vectors, axis=1), 1e-20)
        closest = trajectory[:-1]+np.clip(u, 0, 1)[:, None]*vectors
        assert np.linalg.norm(closest-anchor, axis=1).min() < 1e-6
    left = array('/eef-overlay/lane-left', 'points', (-1, 2, 3))
    right = array('/eef-overlay/lane-right', 'points', (-1, 2, 3))
    assert np.allclose((left+right)/2, segments, atol=1e-6)
    assert np.allclose(np.linalg.norm(left-right, axis=-1), .09, atol=1e-6)
    assert sum(m.get('name') == '/eef-overlay' and m['type'] == 'FrameMessage' for _, m in messages) == 1
    fov = next(m['fov'] for _, m in messages if m['type'] == 'SetCameraFovMessage')
    assert abs(np.tan(.75/2)/np.tan(fov/2)-1.22) < 1e-6
    reader = imageio_ffmpeg.read_frames(str(ROOT / f'assets/media/{scene}.mp4'))
    metadata = next(reader);reader.close()
    assert metadata['fps'] == 25
    assert abs(metadata['duration']-record['durationSeconds']) < .05
    with Image.open(ROOT / f'assets/media/{scene}.png') as image:
        assert not image.info
    print('PASS', scene, len(body), 'measured poses, aligned anchors and lane, matching camera and duration')
