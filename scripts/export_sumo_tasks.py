"""Export recorded native task poses as offline Viser replays and CPU videos.

No simulation is performed here. Both formats use the same full visual meshes
and body poses. Source paths and source body names are never published.
"""
import argparse
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import imageio_ffmpeg
import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation

from recording_io import write_recording
from replay_geometry import mesh
from render_learning_posters import raster


def export(folder, scene, output, video=True):
    geometry = SimpleNamespace(**dict(np.load(folder / 'geometry.npz')))
    states = np.load(folder / 'states.npz')
    result = json.loads((folder / 'result.json').read_text())
    positions, quaternions = states['positions'], states['quaternions']
    times = states['time']
    assert np.all(np.diff(times) > 0)
    meshes = []
    for index, kind in enumerate(geometry.geom_type):
        if geometry.geom_group[index] == 3:
            continue
        color = geometry.geom_rgba[index].copy()
        material = geometry.geom_matid[index]
        if material >= 0:
            color = geometry.mat_rgba[material].copy()
        if color[3] <= 0:
            continue
        shape = mesh(geometry, index)
        local, triangles = shape.vertices, shape.faces
        if kind == 0:
            # Tessellation keeps near-plane clipping from removing the entire floor.
            axis = np.arange(-12., 12.01, .5)
            local = np.array([[x, y, 0.] for y in axis for x in axis])
            n = len(axis)
            triangles = np.array([[y*n+x, y*n+x+1, (y+1)*n+x+1]
                                  for y in range(n-1) for x in range(n-1)] +
                                 [[y*n+x, (y+1)*n+x+1, (y+1)*n+x]
                                  for y in range(n-1) for x in range(n-1)])
        vertices = Rotation.from_quat(geometry.geom_quat[index], scalar_first=True).apply(local)
        vertices += geometry.geom_pos[index]
        if kind == 0:
            color[:3] = [.93, .945, .92]
        meshes.append((int(geometry.geom_bodyid[index]), vertices, triangles, np.round(color[:3]*255)))

    # A goal ring is a visualization of the task's actual goal, not a contact target.
    goal = np.array(result['taskConfig']['goal_position'])
    angles = np.linspace(0, 2*np.pi, 97)
    ring = np.array([[goal[0]+r*np.cos(a), goal[1]+r*np.sin(a), .006]
                     for a in angles for r in [.28, .305]])
    faces = np.array([[2*i, 2*i+1, 2*i+3] for i in range(96)] +
                     [[2*i, 2*i+3, 2*i+2] for i in range(96)])
    meshes.append((0, ring, faces, np.array([108, 155, 110])))

    # Fit a single static camera to all body trajectories and the goal.
    centers = positions[:, 1:, :].reshape(-1, 3)
    low, high = centers.min(0), centers.max(0)
    low[:2] = np.minimum(low[:2], goal[:2]-.4)
    high[:2] = np.maximum(high[:2], goal[:2]+.4)
    target = (low+high)/2
    target[2] = .8 if result['task'] != 'g1_door' else 1.
    extent = max(float(np.max(high[:2]-low[:2])), 2.)
    eye = target + np.array([-1.05, -1.3, .95])*max(2.2, extent*.85)
    fov = .8
    if 'camera' in result:
        # Matched comparisons can share one fixed camera across both runs.
        target=np.asarray(result['camera']['target'],dtype=float)
        eye=np.asarray(result['camera']['position'],dtype=float)
        fov=float(result['camera']['fov'])
    messages, buffers = [], []

    def emit(time, kind, **kwargs):
        messages.append((float(time), dict(type=kind, **kwargs)))

    def binary(array, dtype):
        buffers.append(np.asarray(array, dtype=dtype).tobytes())
        return {'__binary_index': len(buffers)-1, 'dtype': np.dtype(dtype).str}

    emit(0, 'SetOrientationMessage', name='', wxyz=[.5, -.5, .5, .5])
    emit(0, 'ThemeConfigurationMessage', titlebar_content=None, control_layout='floating',
         control_width='medium', show_logo=False, show_share_button=False, dark_mode=False, colors=None)
    emit(0, 'SetCameraPositionMessage', position=eye.tolist(), initial=True)
    emit(0, 'SetCameraLookAtMessage', look_at=target.tolist(), initial=True)
    emit(0, 'SetCameraFovMessage', fov=fov, initial=True)
    used_bodies = sorted(set(item[0] for item in meshes))
    for body in used_bodies:
        emit(0, 'FrameMessage', name=f'/body-{body}', props=dict(show_axes=False,
             axes_length=.5, axes_radius=.025, origin_radius=.05, origin_color=[236, 236, 0], scale=1.))
        emit(0, 'SetSceneNodeVisibilityMessage', name=f'/body-{body}', visible=True)
    for index, (body, vertices, faces, color) in enumerate(meshes):
        name = f'/body-{body}/visual-{index}'
        emit(0, 'MeshMessage', name=name, props=dict(vertices=binary(vertices, '<f4'), faces=binary(faces, '<u4'),
             color=color.astype(int).tolist(), wireframe=False, opacity=None, flat_shading=False,
             side='double', material='standard', scale=1., cast_shadow=True, receive_shadow=True))
        emit(0, 'SetSceneNodeVisibilityMessage', name=name, visible=True)
    for frame, now in enumerate(times):
        for body in used_bodies:
            emit(now, 'SetPositionMessage', name=f'/body-{body}', position=positions[frame, body].tolist())
            emit(now, 'SetOrientationMessage', name=f'/body-{body}', wxyz=quaternions[frame, body].tolist())
    recording = output / 'recordings' / f'{scene}.viser'
    recording.parent.mkdir(parents=True, exist_ok=True)
    write_recording(recording, dict(durationSeconds=float(times[-1]), viserVersion='1.0.29', messages=messages), buffers)
    print(scene, 'Viser exported', len(times), 'physical frames', flush=True)

    if not video:
        return
    width, height, fps = 640, 480, 25
    forward = target-eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0., 0., 1.])
    right /= np.linalg.norm(right)
    basis = np.stack([right, np.cross(right, forward), forward], axis=1)
    focal = height/(2*np.tan(fov/2))
    light = np.array([-.3, -.5, 1.])
    light /= np.linalg.norm(light)
    media = output / 'media'
    media.mkdir(parents=True, exist_ok=True)
    command = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'rgb24',
               '-video_size', f'{width}x{height}', '-framerate', str(fps), '-i', '-', '-an', '-map_metadata', '-1',
               '-c:v', 'libx264', '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
               '-fflags', '+bitexact', '-flags:v', '+bitexact', str(media/f'{scene}.mp4')]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    frame_times = np.arange(0, float(times[-1])+1e-8, 1/fps)
    try:
        for frame, now in enumerate(frame_times):
            # Use the nearest saved state. Never extrapolate a controller's motion.
            index = min(int(np.searchsorted(times, now)), len(times)-1)
            if index and abs(times[index-1]-now) < abs(times[index]-now):
                index -= 1
            matrices = Rotation.from_quat(quaternions[index], scalar_first=True).as_matrix()
            pixels = np.full((height, width, 3), 248., dtype=float)
            depth = np.full((height, width), np.inf)
            for body, local, faces, color in meshes:
                vertices = local @ matrices[body].T + positions[index, body]
                camera = (vertices-eye) @ basis
                points = np.column_stack([width/2+camera[:, 0]/camera[:, 2]*focal,
                                          height/2-camera[:, 1]/camera[:, 2]*focal, camera[:, 2]])
                triangle = vertices[faces]
                normal = np.cross(triangle[:, 1]-triangle[:, 0], triangle[:, 2]-triangle[:, 0])
                normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
                shades = .5+.5*np.abs(normal @ light)
                raster(points, faces, shades, depth, pixels, color)
            image = pixels.astype(np.uint8)
            if frame == 0:
                Image.fromarray(image).save(media/f'{scene}.png')
            process.stdin.write(image.tobytes())
            if frame % 50 == 0:
                print(scene, 'video', frame, '/', len(frame_times), flush=True)
    finally:
        process.stdin.close()
        code = process.wait()
    if code:
        raise RuntimeError(f'Video encoder exited with {code}')
    print(scene, 'video complete', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--scene', required=True)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1]/'assets')
    parser.add_argument('--no-video', action='store_true')
    args = parser.parse_args()
    export(args.folder, args.scene, args.output, video=not args.no_video)
