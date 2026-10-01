"""Add recorded gripper anchors and a trajectory lane to Spot replay exports.

The source controller tracks arm_link_fngr (body 20 in these baked models).
These are measured replay positions, not predicted or commanded waypoints.
Video and native Viser geometry use the same positions and camera zoom.
"""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw

from recording_io import read_recording, write_recording, compact_buffers

ROOT = Path(__file__).resolve().parents[1]
COLOR = (207, 154, 151)
ZOOM = 1.22


def paths(folder):
    states = np.load(folder / 'states.npz')
    times = states['time']
    positions = states['positions'][:, 20].copy()
    distance = np.r_[0, np.cumsum(np.linalg.norm(np.diff(positions, axis=0), axis=1))]
    keep = np.r_[True, np.diff(distance) > 1e-10]
    anchors = np.column_stack([np.interp(np.linspace(0, distance[-1], 5),
        distance[keep], positions[keep, j]) for j in range(3)])
    # Use one lateral axis for the lane. A per-frame tangent would flip at
    # tiny measured reversals and create spurious loops in its boundaries.
    tangent = positions[-1, :2] - positions[0, :2]
    tangent /= max(float(np.linalg.norm(tangent)), 1e-8)
    side = np.array([-tangent[1], tangent[0], 0.]) * .045
    return times, positions, anchors, (positions - side, positions + side)


def annotate(folder, scene, cache):
    result = json.loads((folder / 'result.json').read_text())
    times, eef, anchors, lanes = paths(folder)
    recording = ROOT / 'assets/recordings' / (scene + '.viser')
    record, buffers = read_recording(recording)
    original_messages = [(t, m) for t, m in record['messages']
        if not m.get('name', '').startswith('/eef-overlay')]
    messages = []

    def emit(t, kind, **kwargs):
        messages.append((float(t), dict(type=kind, **kwargs)))

    def binary(values, dtype):
        buffers.append(np.asarray(values, dtype=dtype).tobytes())
        return dict(__binary_index=len(buffers)-1, dtype=np.dtype(dtype).str)

    def points(name, values, color, size):
        emit(0, 'PointCloudMessage', name=name, props=dict(points=binary(values, '<f4'),
            colors=binary(np.tile(color, (len(values), 1)), '|u1'), point_size=size,
            point_shape='circle', precision='float32', scale=1., point_shading='flat'))

    emit(0, 'FrameMessage', name='/eef-overlay', props=dict(show_axes=False,
        axes_length=.5, axes_radius=.025, origin_radius=.05, origin_color=[236, 236, 0], scale=1.))
    for name, values, width, color in [('trace', eef, 3, COLOR),
            ('lane-left', lanes[0], 1.5, (222, 193, 188)),
            ('lane-right', lanes[1], 1.5, (222, 193, 188))]:
        segments = np.stack([values[:-1], values[1:]], axis=1)
        emit(0, 'LineSegmentsMessage', name='/eef-overlay/'+name,
            props=dict(points=binary(segments, '<f4'), colors=binary(np.broadcast_to(color, segments.shape), '|u1'),
                       line_width=width, scale=1.))
    points('/eef-overlay/anchors-outline', anchors, (71, 61, 59), .069)
    points('/eef-overlay/anchors', anchors, COLOR, .054)
    points('/eef-overlay/current-outline', [[0, 0, 0]], (71, 61, 59), .089)
    points('/eef-overlay/current', [[0, 0, 0]], (249, 216, 204), .070)
    for now, position in zip(times, eef):
        for name in ['current', 'current-outline']:
            emit(now, 'SetPositionMessage', name='/eef-overlay/'+name, position=position.tolist())
    for _, message in original_messages:
        if message['type'] == 'SetCameraFovMessage':
            message['fov'] = float(2*np.arctan(np.tan(result['camera']['fov']/2)/ZOOM))
    record['messages'] = sorted(original_messages + messages, key=lambda pair: pair[0])
    record, buffers = compact_buffers(record, buffers)
    write_recording(recording, record, buffers)

    video = ROOT / 'assets/media' / (scene+'.mp4')
    cache.mkdir(parents=True, exist_ok=True)
    source = cache / (scene+'.mp4')
    if not source.exists():
        shutil.copyfile(video, source)
    reader = imageio_ffmpeg.read_frames(str(source), pix_fmt='rgb24')
    metadata = next(reader)
    width, height = metadata['size']
    fps = metadata['fps']
    camera = result['camera']
    eye, target = np.asarray(camera['position']), np.asarray(camera['target'])
    forward = target - eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0., 0., 1.]);right /= np.linalg.norm(right)
    basis = np.stack([right, np.cross(right, forward), forward], axis=1)
    focal = height/(2*np.tan(camera['fov']/2))

    def project(values):
        q = (values - eye) @ basis
        assert np.all(q[:, 2] > 0)
        return np.column_stack([width/2+q[:, 0]/q[:, 2]*focal, height/2-q[:, 1]/q[:, 2]*focal])

    projected = [project(values) for values in [eef, *lanes]]
    anchor_pixels = project(anchors)
    crop = (width*(1-1/ZOOM)/2, height*(1-1/ZOOM)/2,
            width*(1+1/ZOOM)/2, height*(1+1/ZOOM)/2)
    with tempfile.TemporaryDirectory(prefix='clear-spot-overlay-') as temporary:
        output = Path(temporary) / 'video.mp4'
        proc = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-v', 'error',
            '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', f'{width}x{height}',
            '-framerate', str(fps), '-i', '-', '-an', '-map_metadata', '-1', '-c:v', 'libx264',
            '-crf', '19', '-pix_fmt', 'yuv420p', '-fflags', '+bitexact', '-flags:v', '+bitexact',
            '-movflags', '+faststart', str(output)], stdin=subprocess.PIPE)
        try:
            for frame, raw in enumerate(reader):
                image = Image.frombytes('RGB', (width, height), raw)
                draw = ImageDraw.Draw(image, 'RGBA')
                for line, color, weight in [(projected[1], (*COLOR, 150), 1),
                        (projected[2], (*COLOR, 150), 1), (projected[0], (*COLOR, 225), 2)]:
                    draw.line([tuple(p) for p in line], fill=color, width=weight)
                for x, y in anchor_pixels:
                    draw.ellipse((x-3, y-3, x+3, y+3), fill=(*COLOR, 255), outline=(71, 61, 59, 255))
                i = min(int(np.searchsorted(times, frame/fps)), len(times)-1)
                if i and abs(times[i-1]-frame/fps) < abs(times[i]-frame/fps):i -= 1
                x, y = projected[0][i]
                draw.ellipse((x-4, y-4, x+4, y+4), fill=(249, 216, 204, 255), outline=(71, 61, 59, 255), width=1)
                image = image.crop(crop).resize((width, height), Image.Resampling.LANCZOS)
                if frame == 0:image.save(video.with_suffix('.png'))
                if frame in [0, 250, 500]:image.save(cache / f'{scene}-{frame}.png')
                proc.stdin.write(image.tobytes())
                if frame % 250 == 0:print(scene, 'overlay frame', frame, flush=True)
        finally:
            reader.close();proc.stdin.close();code = proc.wait()
        assert code == 0
        shutil.copyfile(output, video)
    print('PASS', scene, 'recorded gripper path, five anchors, two lane boundaries and 1.22x view', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baked', type=Path)
    parser.add_argument('scene', choices=['mpc-spot-optimized', 'mpc-spot-held-arm'])
    parser.add_argument('--source-cache', type=Path, required=True,
                        help='Retains the original unannotated video for repeatable exports')
    args = parser.parse_args()
    annotate(args.baked, args.scene, args.source_cache)
