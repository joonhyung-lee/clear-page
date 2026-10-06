"""Audit the three requested MP4s against native episodes and Viser pose data."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
from PIL import Image
from recording_io import read_recording, validate_binary_arrays
from replanning_timeline import at_time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--runs', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--ffmpeg', type=Path, required=True)
p.add_argument('--method', choices=['naive', 'replan', 'inpainting'], help='Check one finished artifact while other native runs continue')
a = p.parse_args()
manifest = json.loads((a.output/'manifest.json').read_text())
if a.method:
    manifest = {a.method: manifest[a.method]}
else:
    assert set(manifest) == {'naive', 'replan', 'inpainting'}
for field in ['initialPlanHash', 'sceneHash', 'checkpointSHA256', 'runtimeProfileSHA256']:
    assert len({v[field] for v in manifest.values()}) == 1, field
if 'naive' in manifest:
    assert manifest['naive']['nativeMethod'] == 'clear_frozen' and manifest['naive']['repair'] == 0
if 'replan' in manifest:
    assert manifest['replan']['nativeMethod'] == 'clear' and manifest['replan']['repair'] == 0
if 'inpainting' in manifest:
    assert manifest['inpainting']['nativeMethod'] == 'clear'
    assert manifest['inpainting']['repair'] == 4 and manifest['inpainting']['repairMode'] == 'causal'
for method, entry in manifest.items():
    assert not entry['fallback'] and entry['candidateCount'] == 8
    assert entry['runtimeProfile']['name'] == 'upright-bilateral-palms-v1'
    assert not entry['runtimeProfile']['low_contact_profile']
    assert not entry['runtimeProfile']['crouch_offsets']
    folder = a.runs/method
    episode_path = folder/'episode.json'
    episode = json.loads(episode_path.read_text())
    assert episode['status'] != 'infrastructure_error'
    assert hashlib.sha256(episode_path.read_bytes()).hexdigest() == entry['episodeSHA256']
    audit = json.loads((a.output/method/'render-audit.json').read_text())
    assert not audit['layoutPreview']
    assert audit['sourceEpisode'] == entry['episodeSHA256']
    timeline = json.loads((folder/'prepared/timeline.json').read_text())
    with np.load(folder/'prepared/geometry.npz') as archive:
        geometry = dict(archive)
    record, buffers = read_recording(a.output/entry['viser'])
    validate_binary_arrays(record, buffers)
    assert abs(record['durationSeconds']-timeline['duration']) < 1e-6
    recorded_positions = {(t, m['name']): m['position'] for t, m in record['messages'] if m['type'] == 'SetPositionMessage'}
    for i in [0, len(geometry['time'])//2, len(geometry['time'])-1]:
        for b in range(len(timeline['bodies'])):
            actual = recorded_positions[(geometry['time'][i], f'/body-{b}')]
            assert np.allclose(actual, geometry['positions'][i, b], atol=1e-8)
    # Validate the deliverable's actual binary geometry, including both box
    # ghosts at the corresponding planned poses, rather than only its poses.
    sizes = {obj['object_id']: obj['size'] for obj in timeline['scene']['objects']}
    ghost_updates = 0
    for stamp, message in record['messages']:
        if message['type'] != 'SceneNodeUpdateMessage' or not message.get('name', '').endswith('/ghosts'):
            continue
        oid = int(message['name'].split('/')[2].removeprefix('object-'))
        descriptor = message['updates']['points']
        points = np.frombuffer(buffers[descriptor['__binary_index']], dtype=descriptor['dtype']).reshape(-1, 2, 3)
        assert points.shape == (24, 2, 3), 'Expected two complete 12-edge box ghosts'
        path = next(path for path in at_time(timeline, stamp)['current']['paths'] if path['object_id'] == oid)
        poses = path['poses']
        for edges, pose in zip([points[:12], points[12:]], [poses[len(poses)//2], poses[-1]], strict=True):
            corners = np.unique(edges.reshape(-1, 3), axis=0)
            assert len(corners) == 8
            assert np.allclose(corners.mean(axis=0)[:2], pose[:2], atol=2e-6)
            assert np.isclose(corners[:, 2].max()-corners[:, 2].min(), sizes[oid][2], atol=2e-6)
        ghost_updates += 1
    assert ghost_updates > 0, 'Viser is missing planned box ghosts'
    frames = audit['frames']
    clock = np.array([frame['time'] for frame in frames])
    assert np.all(np.diff(clock) >= -1e-8)
    assert abs(clock[-1]-timeline['duration']) < 1e-6
    for frame in frames:
        if frame['attentionTotal'] is not None:
            assert abs(frame['attentionTotal']-1) < 2e-6
        visible = [p for p in episode['plans'] if p['time_s'] <= frame['time']+1e-8]
        assert frame['planCall'] == (visible[-1]['call'] if visible else None)
    assert any(frame['generationTime'] is not None for frame in frames)
    video = a.output/entry['video']
    assert hashlib.sha256(video.read_bytes()).hexdigest() == entry['videoSHA256']
    process = subprocess.Popen([str(a.ffmpeg), '-v', 'error', '-i', str(video), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    size = 1280*720*3
    count = 0
    probes = {0, len(frames)//2, len(frames)-1}
    while True:
        raw = process.stdout.read(size)
        if not raw:
            break
        assert len(raw) == size
        if count in probes:
            actual = np.frombuffer(raw, dtype=np.uint8).reshape(720, 1280, 3)
            saved = np.asarray(Image.open(a.output/method/f'frame-{count:04d}.png'))
            assert np.abs(actual.astype(float)-saved).mean() < 3
        count += 1
    assert process.wait() == 0 and count == len(frames)
    print('PASS', method, 'native identity, causal overlays, complete video clock, Viser poses and decoded MP4')
if not a.method:
    assert manifest['naive']['planningCalls'] == 1
    assert manifest['replan']['planningCalls'] >= 2
    assert manifest['inpainting']['planningCalls'] >= 2
    inpaint = json.loads((a.runs/'inpainting/episode.json').read_text())
    assert inpaint['event']['applied'], 'The comparison did not reach its planned disturbance'
    print('PASS all three requested methods and an observed disturbance')
