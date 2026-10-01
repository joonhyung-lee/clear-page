"""Check Spot overlays against the gripper poses in the published recordings."""
from pathlib import Path
import json

import imageio_ffmpeg
import numpy as np
from PIL import Image

from recording_io import read_recording, validate_binary_arrays

ROOT = Path(__file__).resolve().parents[1]
scenes = {row['scene'] for row in json.loads((ROOT/'assets/controller-gallery.json').read_text())
          if row.get('body') == 'spot_arm'}
scenes.add('mpc-spot-held-arm')
for scene in sorted(scenes):
    if scene=='mpc-spot-native':
        from check_native_baseline_replays import check_scene
        check_scene(scene)
        continue
    record, buffers = read_recording(ROOT / f'assets/recordings/{scene}.viser')
    validate_binary_arrays(record, buffers)
    messages = record['messages']
    if scene=='mpc-spot-variable-delay':
        assert any(m.get('props',{}).get('text')=='Variable-delay actuation stress test'
                   for _,m in messages), 'The native diagnostic must retain its scope label'
    if scene=='mpc-spot-cost-ablation':
        assert any(m.get('props',{}).get('text')=='Cost ablation' for _,m in messages)
    if scene=='mpc-spot-high-kp':
        assert any(m.get('props',{}).get('text')=='P gain ×3' for _,m in messages)
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
    def props(name):
        return next(m['props'] for _,m in messages if m.get('name')==name and 'props' in m)
    assert props('/eef-overlay/anchors')['point_size'] >= .09
    assert props('/eef-overlay/recent')['line_width'] >= 5
    assert props('/object-overlay/observed')['line_width'] >= 6
    assert props('/object-overlay/lane-0')['line_width'] >= 3.5
    assert props('/object-overlay/anchors')['point_size'] >= .10
    target_anchors=array('/object-overlay/anchors','points',(-1,3))
    assert np.allclose(target_anchors[:,0],np.linspace(6,8,5))
    assert np.allclose(target_anchors[:,1:],[[6,.012]]*5)
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
    box = {t: m['position'] for t, m in messages
           if m['type'] == 'SetPositionMessage' and m['name'] == '/body-21'}
    object_current = {t: m['position'] for t, m in messages
                      if m['type'] == 'SetPositionMessage' and m['name'] == '/object-overlay/current'}
    assert box.keys() == object_current.keys(), 'Object overlay must follow the physical box'
    floor_path = np.asarray(list(box.values())); floor_path[:, 2] = .018
    assert np.allclose(floor_path, list(object_current.values()), atol=1e-8)
    reference = array('/object-overlay/reference', 'points', (-1, 2, 3))
    assert np.allclose(reference[:,:,1], 6.) and np.allclose(reference[:,:,2],.012)
    assert np.allclose(reference[0,0,:2],[6.,6.])
    assert np.linalg.norm(reference[-1,-1,:2]-[8.,6.]) < .065, 'Only a final dash gap may precede the goal'
    goal = array('/object-overlay/goal','points',(-1,3))
    assert np.allclose(goal[:,:2].min(0),[7.6,5.6])
    assert np.allclose(goal[:,:2].max(0),[8.4,6.4]), 'Goal footprint must retain the requested target pose'
    object_left = array('/object-overlay/lane-0','points',(-1,2,3))
    object_right = array('/object-overlay/lane-1','points',(-1,2,3))
    assert np.allclose(np.linalg.norm(object_right-object_left,axis=-1),.8,atol=1e-6)
    times = np.asarray(list(body))
    updates = [(t,m) for t,m in messages if m['type']=='SceneNodeUpdateMessage'
               and m['name']=='/eef-overlay/recent']
    assert np.array_equal([t for t,_ in updates],times)
    for index,(t,m) in enumerate(updates):
        begin=np.searchsorted(times,t-.8)
        expected=trajectory[begin:index+1]
        if len(expected)==1:expected=np.repeat(expected,2,axis=0)
        ref=m['updates']['points']
        actual=np.frombuffer(buffers[ref['__binary_index']],dtype=ref['dtype']).reshape(-1,2,3)
        assert np.allclose(actual,np.stack([expected[:-1],expected[1:]],axis=1),atol=1e-6)
    for t,m in messages:
        if m['type']!='SceneNodeUpdateMessage' or m['name']!='/object-overlay/observed':continue
        index=np.searchsorted(times,t)
        expected=floor_path[:index+1]
        if len(expected)==1:expected=np.repeat(expected,2,axis=0)
        ref=m['updates']['points']
        actual=np.frombuffer(buffers[ref['__binary_index']],dtype=ref['dtype']).reshape(-1,2,3)
        assert np.allclose(actual,np.stack([expected[:-1],expected[1:]],axis=1),atol=1e-6)
    fov = next(m['fov'] for _, m in messages if m['type'] == 'SetCameraFovMessage')
    assert abs(np.tan(.75/2)/np.tan(fov/2)-1.22) < 1e-6
    reader = imageio_ffmpeg.read_frames(str(ROOT / f'assets/media/{scene}.mp4'))
    metadata = next(reader);reader.close()
    assert metadata['fps'] == 25
    assert abs(metadata['duration']-record['durationSeconds']) < .05
    with Image.open(ROOT / f'assets/media/{scene}.png') as image:
        assert not image.info
    print('PASS', scene, len(body), 'measured poses, 0.8 s EEF trails, object target/actual lanes, matching camera and duration')
