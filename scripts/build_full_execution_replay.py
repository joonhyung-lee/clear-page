"""Extend the opaque Ours replay using the measured 40 s context body poses.

The first interaction's forecasts expire at 14 s. Continuation contains measured
body/object poses and palm history, never extrapolated commands or predictions.
"""
import copy
import re
from pathlib import Path
import numpy as np
from recording_io import read_recording, write_recording, compact_buffers

ROOT = Path(__file__).resolve().parents[1]


def build():
    source, buffers = read_recording(ROOT / 'assets/recordings/mpc-optimized.viser')
    context, extra = read_recording(ROOT / 'assets/recordings/mpc-context-optimized.viser')
    context = copy.deepcopy(context)
    offset = len(buffers)

    def remap(value):
        if isinstance(value, dict):
            if '__binary_index' in value:
                value['__binary_index'] += offset
            else:
                for child in value.values():
                    remap(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                remap(child)

    remap(context)
    buffers.extend(extra)
    kinds = ('SetPositionMessage', 'SetOrientationMessage')

    def body_pose(message):
        return message['type'] in kinds and re.fullmatch(r'/tracking/body-\d+', message.get('name', ''))

    original = {(round(t, 6), m['type'], m['name']): m for t, m in source['messages'] if body_pose(m)}
    shared = 0
    messages = []
    for t, m in source['messages']:
        if body_pose(m) or (m.get('name') == '/tracking' and m['type'] in kinds):
            continue
        if m['type'] == 'SetCameraPositionMessage':
            # From this side the first box does not hide the robot passing it.
            m['position'] = [-2.6, -1.8, 1.8]
        elif m['type'] == 'SetCameraLookAtMessage':
            m['look_at'] = [0., .5, .7]
        messages.append([t, m])
    messages.append([0., dict(type=kinds[1], name='/tracking', wxyz=[1., 0., 0., 0.])])
    for t, m in context['messages']:
        name = m.get('name', '')
        if body_pose(m):
            key = (round(t, 6), m['type'], name)
            if key in original:
                field = 'position' if m['type'] == kinds[0] else 'wxyz'
                assert np.array_equal(original[key][field], m[field]), key
                shared += 1
            messages.append([t, m])
            if name == '/tracking/body-1' and m['type'] == kinds[0]:
                x, y, _ = m['position']
                messages.append([t, dict(type=kinds[0], name='/tracking', position=[-x, -y, 0.])])
        elif name.startswith('/tracking/palm-history-'):
            messages.append([t, m])
        elif name == '/tracking/current-palms' and m['type'] == 'SceneNodeUpdateMessage' and t > 14:
            for target in ('/tracking/palm-centers', '/tracking/palm-centers-outline'):
                messages.append([t, dict(type='SceneNodeUpdateMessage', name=target,
                                        updates={'points': copy.deepcopy(m['updates']['points'])})])
    assert shared > 8000, 'Full replay must match the original interaction exactly'
    names = {m.get('name', '') for _, m in source['messages']}
    expired = [name for name in names if re.search(r'candidate|waypoint|reference-', name)]
    # Contact heatmaps are tied to the first interaction's objects, too.
    expired += [m['name'] for _, m in source['messages'] if m['type'] == 'ImageMessage']
    initialized = {m['name'] for t, m in messages if t == 0 and m['type'] == 'SetSceneNodeVisibilityMessage'}
    for name in set(expired):
        if name not in initialized:
            # Native backward seeks retain scene nodes, so restore their initial
            # visibility explicitly after hiding the expired first-push overlays.
            messages.append([0., dict(type='SetSceneNodeVisibilityMessage', name=name, visible=True)])
        messages.append([14.000001, dict(type='SetSceneNodeVisibilityMessage', name=name, visible=False)])
    source['messages'] = sorted(messages, key=lambda pair: pair[0])
    source['durationSeconds'] = 40.1  # A padding frame keeps a seek to 40 from wrapping.
    source, buffers = compact_buffers(source, buffers)
    write_recording(ROOT / 'assets/recordings/mpc-optimized-full.viser', source, buffers)
    # Rebuild the measured object lane through the continuation and retain the
    # shared G1 annotation styling when this scene is regenerated.
    from style_g1_overlays import style
    style('mpc-optimized-full')
    print(f'PASS {shared} unchanged source transforms; full measured replay through 40 s')


if __name__ == '__main__':
    build()
