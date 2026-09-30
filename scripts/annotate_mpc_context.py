"""Attach palm labels to measured coordinates without changing replay geometry."""
from pathlib import Path
import numpy as np
from recording_io import read_recording, write_recording


def annotate(record, buffers):
    prefix = '/tracking/annotation-'
    messages = [[t, m] for t, m in record['messages']
                if not m.get('name', '').startswith((prefix, '/overlay-axes'))]
    # This fixed frame indicates the reference-aligned coordinates of the
    # chase view. It is a viewing aid, not an extra physical scene object.
    annotations = [[0., dict(type='FrameMessage', name='/overlay-axes', props=dict(
        show_axes=True, axes_length=.32, axes_radius=.007,
        origin_radius=.012, origin_color=[90,100,90], scale=1.))],
        [0., dict(type='SetPositionMessage', name='/overlay-axes', position=[.9,-.8,.03])],
        [0., dict(type='SetSceneNodeVisibilityMessage', name='/overlay-axes', visible=True)]]
    for i, axis in enumerate('XYZ'):
        point = [0.,0.,0.]
        point[i] = .38
        name = '/overlay-axes/'+axis.lower()
        annotations.extend([
            [0., dict(type='LabelMessage', name=name, props=dict(text=axis,
                font_size_mode='screen', font_screen_scale=.75, font_scene_height=.06,
                depth_test=False, anchor='center-center'))],
            [0., dict(type='SetPositionMessage', name=name, position=point)],
            [0., dict(type='SetSceneNodeVisibilityMessage', name=name, visible=True)]])
    for side in ['left', 'right']:
        name = prefix + side
        annotations.append([0., dict(type='LabelMessage', name=name, props=dict(
            text=side.capitalize()+' palm', font_size_mode='screen',
            font_screen_scale=.85, font_scene_height=.075,
            depth_test=False, anchor='bottom-left' if side=='left' else 'top-right'))])
        annotations.append([0., dict(type='SetSceneNodeVisibilityMessage', name=name, visible=True)])
    frames = 0
    for t, message in messages:
        if message.get('name') != '/tracking/current-palms':
            continue
        props = message.get('props', message.get('updates', {}))
        if 'points' not in props:
            continue
        ref = props['points']
        palms = np.frombuffer(buffers[ref['__binary_index']], dtype=ref['dtype']).reshape(2, 3)
        for side, point in zip(['left', 'right'], palms):
            annotations.append([t, dict(type='SetPositionMessage', name=prefix+side,
                                       position=point.astype(float).tolist())])
        frames += 1
    assert frames > 1, 'Palm annotations require measured time-varying positions'
    # Stable sorting creates labels after their parent, then applies each pose.
    record['messages'] = sorted(messages + annotations, key=lambda item:item[0])
    return record


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    for kind in ['optimized', 'baseline']:
        path = root/f'assets/recordings/mpc-context-{kind}.viser'
        record, buffers = read_recording(path)
        original = list(buffers)
        annotate(record, buffers)
        assert buffers == original
        write_recording(path, record, buffers)
        print('Annotated', kind, 'palms at recorded positions')
