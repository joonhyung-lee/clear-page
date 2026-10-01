"""Show measured gripper motion and intended versus executed object motion.

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
from PIL import Image, ImageDraw, ImageFont

from recording_io import read_recording, write_recording, compact_buffers

ROOT = Path(__file__).resolve().parents[1]
COLOR = (184, 92, 91)
ZOOM = 1.22
OBJECT_COLOR = (26, 115, 105)
REFERENCE_COLOR = (57, 100, 163)
TRAIL_SECONDS = .8


def object_paths(folder, source=None):
    """Use the archived plan, never fit a reference to the executed trajectory."""
    result = json.loads((folder / 'result.json').read_text())
    states = np.load(folder / 'states.npz')
    if 'objectReference' in result:
        reference, size = result['objectReference'], result['objectSize']
    else:
        if source is None:
            raise ValueError('Older bakes require --reference-source with the recorded plan')
        original = json.loads((source / 'result.json').read_text())
        reference = original['reference_plan']['paths'][0]['poses']
        size = original['input_scene']['objects'][0]['size']
    # These baked single-box models have body 21 as the box. New bakes save IDs.
    body = result.get('objectBodyId', 21)
    observed = states['positions'][:, body].copy()
    reference = np.asarray(reference, dtype=float)[:, :2]
    assert np.allclose(reference[-1], result['taskConfig']['goal_position'][:2])
    assert np.linalg.norm(reference[0]-observed[0, :2]) < .05
    reference = np.column_stack([reference, np.full(len(reference), .012)])
    footprint = observed.copy(); footprint[:, 2] = .018
    direction = reference[-1]-reference[0]
    direction /= np.linalg.norm(direction)
    side = np.array([-direction[1], direction[0], 0.])*size[1]/2
    rails = (reference-side, reference+side)
    return observed, footprint, reference, rails, np.asarray(size)


def segments(values):
    if len(values) == 1:
        values = np.repeat(values, 2, axis=0)
    return np.stack([values[:-1], values[1:]], axis=1)


def spaced_anchors(values, count=5):
    distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(values,axis=0),axis=1))]
    keep=np.r_[True,np.diff(distance)>1e-10]
    return np.column_stack([np.interp(np.linspace(0,distance[-1],count),
                            distance[keep],values[keep,j]) for j in range(3)])


def dashed(values, length=.10, gap=.065):
    result = []
    for start, end in zip(values[:-1], values[1:]):
        distance = np.linalg.norm(end-start)
        if distance < 1e-9: continue
        for t in np.arange(0, distance, length+gap):
            result.append([start+(end-start)*t/distance,
                           start+(end-start)*min(t+length, distance)/distance])
    return np.asarray(result)


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


def annotate(folder, scene, cache, source=None):
    result = json.loads((folder / 'result.json').read_text())
    variable_delay=bool(result.get('commandSettings',{}).get('commandHoldIntervals'))
    diagnostic_label='Cost ablation' if result.get('costAblation') else 'Variable-delay actuation stress test' if variable_delay else None
    if result.get('gainDiagnostic'):diagnostic_label=f"P gain ×{result['gainDiagnostic']['scale']:g}"
    times, eef, anchors, lanes = paths(folder)
    objects, footprint, reference, object_lanes, size = object_paths(folder, source)
    recording = ROOT / 'assets/recordings' / (scene + '.viser')
    record, buffers = read_recording(recording)
    original_messages = [(t, m) for t, m in record['messages']
        if not m.get('name', '').startswith(('/eef-overlay', '/object-overlay'))]
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

    def lines(name, values, color, width, time=0., update=False):
        props = dict(points=binary(values, '<f4'),
                     colors=binary(np.broadcast_to(color, values.shape), '|u1'))
        if update:
            emit(time, 'SceneNodeUpdateMessage', name=name, updates=props)
        else:
            emit(time, 'LineSegmentsMessage', name=name,
                 props=dict(**props, line_width=width, scale=1.))

    emit(0, 'FrameMessage', name='/eef-overlay', props=dict(show_axes=False,
        axes_length=.5, axes_radius=.025, origin_radius=.05, origin_color=[236, 236, 0], scale=1.))
    # Preserve the complete measured archive, but show only the recent motion
    # by default. Identical time window and styles are used for both controllers.
    for name, values in [('trace', eef), ('lane-left', lanes[0]), ('lane-right', lanes[1])]:
        lines('/eef-overlay/'+name, segments(values), COLOR, 1.)
        emit(0, 'SetSceneNodeVisibilityMessage', name='/eef-overlay/'+name, visible=False)
    lines('/eef-overlay/recent', segments(eef[:1]), COLOR, 5.)
    points('/eef-overlay/time-dots', eef[:1], COLOR, .045)
    points('/eef-overlay/anchors-outline', anchors, (255, 255, 255), .125)
    points('/eef-overlay/anchors', anchors, COLOR, .09)
    points('/eef-overlay/current-outline', [[0, 0, 0]], (255, 255, 255), .15)
    points('/eef-overlay/current', [[0, 0, 0]], COLOR, .11)
    emit(0, 'FrameMessage', name='/object-overlay', props=dict(show_axes=False,
        axes_length=.5, axes_radius=.025, origin_radius=.05, origin_color=[236, 236, 0], scale=1.))
    if diagnostic_label:
        emit(0,'LabelMessage',name='/object-overlay/diagnostic',props=dict(
            text=diagnostic_label,font_size_mode='screen',
            font_screen_scale=.75,font_scene_height=.075,depth_test=False,anchor='bottom-center'))
        emit(0,'SetPositionMessage',name='/object-overlay/diagnostic',position=[7.,6.,1.55])
    lines('/object-overlay/reference', dashed(reference), REFERENCE_COLOR, 5.)
    object_anchors=spaced_anchors(reference)
    points('/object-overlay/anchors-outline',object_anchors,(255,255,255),.15)
    points('/object-overlay/anchors',object_anchors,REFERENCE_COLOR,.105)
    for index, rail in enumerate(object_lanes):
        lines('/object-overlay/lane-'+str(index), dashed(rail), REFERENCE_COLOR, 3.5)
    lines('/object-overlay/observed', segments(footprint[:1]), OBJECT_COLOR, 6.)
    points('/object-overlay/current-outline',[[0,0,0]],(255,255,255),.19)
    points('/object-overlay/current', [[0, 0, 0]], OBJECT_COLOR, .14)
    goal = reference[-1].copy()
    corners = np.array([[-1,-1],[1,-1],[1,1],[-1,1],[-1,-1]])*size[:2]/2
    goal_box = np.column_stack([corners+goal[:2], np.full(5,.012)])
    lines('/object-overlay/goal', dashed(goal_box), REFERENCE_COLOR, 3.5)
    for index, (now, position) in enumerate(zip(times, eef)):
        for name in ['current', 'current-outline']:
            emit(now, 'SetPositionMessage', name='/eef-overlay/'+name, position=position.tolist())
        begin = np.searchsorted(times, now-TRAIL_SECONDS)
        lines('/eef-overlay/recent', segments(eef[begin:index+1]), COLOR, 5., now, True)
        dots=eef[begin:index+1:5]
        emit(now,'SceneNodeUpdateMessage',name='/eef-overlay/time-dots',updates=dict(
            points=binary(dots,'<f4'),colors=binary(np.tile(COLOR,(len(dots),1)),'|u1')))
        lines('/object-overlay/observed', segments(footprint[:index+1]), OBJECT_COLOR, 6., now, True)
        emit(now, 'SetPositionMessage', name='/object-overlay/current', position=footprint[index].tolist())
        emit(now, 'SetPositionMessage', name='/object-overlay/current-outline', position=footprint[index].tolist())
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
    object_anchor_pixels=project(object_anchors)
    object_pixels = project(footprint)
    reference_segments = [project(line) for values in [reference, *object_lanes, goal_box]
                          for line in dashed(values)]
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
                i = min(int(np.searchsorted(times, frame/fps)), len(times)-1)
                if i and abs(times[i-1]-frame/fps) < abs(times[i]-frame/fps):i -= 1
                for line in reference_segments:
                    draw.line([tuple(p) for p in line], fill=(*REFERENCE_COLOR, 255), width=3)
                for x,y in object_anchor_pixels:
                    draw.ellipse((x-6,y-6,x+6,y+6),fill='white',outline=(*REFERENCE_COLOR,255),width=2)
                if i:
                    draw.line([tuple(p) for p in object_pixels[:i+1]], fill=(*OBJECT_COLOR, 255), width=5)
                ox, oy = object_pixels[i]
                draw.ellipse((ox-7,oy-7,ox+7,oy+7),fill=(*OBJECT_COLOR,255),outline='white',width=2)
                begin = np.searchsorted(times, times[i]-TRAIL_SECONDS)
                if i > begin:
                    draw.line([tuple(p) for p in projected[0][begin:i+1]], fill=(*COLOR,255), width=4)
                # Equal-time markers make the recorded pauses/speed changes visible.
                for j in range(begin, i+1, 5):
                    x,y=projected[0][j]
                    draw.ellipse((x-3,y-3,x+3,y+3),fill=(*COLOR,255),outline='white')
                for x, y in anchor_pixels:
                    draw.ellipse((x-5,y-5,x+5,y+5),fill=(*COLOR,255),outline='white',width=2)
                x, y = projected[0][i]
                draw.ellipse((x-6, y-6, x+6, y+6), fill=(*COLOR,255), outline='white', width=2)
                image = image.crop(crop).resize((width, height), Image.Resampling.LANCZOS)
                draw=ImageDraw.Draw(image,'RGBA')
                font=ImageFont.truetype('DejaVuSans.ttf',12)
                draw.rounded_rectangle((10,height-62,415,height-10),radius=4,fill=(255,255,255,232))
                for x,color,label in [(20,REFERENCE_COLOR,'Object target'),(145,OBJECT_COLOR,'Object motion'),(280,COLOR,'EEF 0.8 s')]:
                    if color==REFERENCE_COLOR:
                        for dx in (0,8):draw.line((x+dx,height-46,x+dx+5,height-46),fill=color,width=2)
                    else:draw.line((x,height-46,x+14,height-46),fill=color,width=2)
                    draw.text((x+19,height-53),label,font=font,fill=(50,63,61))
                error=np.linalg.norm(objects[i,:2]-reference[-1,:2])
                draw.text((20,height-31),f'Goal error {error:.2f} m',font=font,fill=OBJECT_COLOR)
                scope='Cost ablation' if result.get('costAblation') else 'Variable-delay stress test' if variable_delay else 'Recorded motion · extended arm'
                if result.get('gainDiagnostic'):scope=diagnostic_label
                if result.get('gainDiagnostic') and result.get('failedAttempt'):scope='P ×3 · Contact timeout'
                draw.text((170,height-31),scope,font=font,fill=(75,82,79))
                if frame == 0:image.save(video.with_suffix('.png'))
                if frame in [0, 250, 500]:image.save(cache / f'{scene}-{frame}.png')
                proc.stdin.write(image.tobytes())
                if frame % 250 == 0:print(scene, 'overlay frame', frame, flush=True)
        finally:
            reader.close();proc.stdin.close();code = proc.wait()
        assert code == 0
        shutil.copyfile(output, video)
    print('PASS', scene, 'measured EEF trail, object reference lane and executed object path', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baked', type=Path)
    parser.add_argument('scene', choices=['mpc-spot-optimized','mpc-spot-baseline', 'mpc-spot-held-arm','mpc-spot-variable-delay','mpc-spot-cost-ablation','mpc-spot-high-kp'])
    parser.add_argument('--source-cache', type=Path, required=True,
                        help='Retains the original unannotated video for repeatable exports')
    parser.add_argument('--reference-source',type=Path,
                        help='Original physical record for references absent from older bakes')
    args = parser.parse_args()
    annotate(args.baked, args.scene, args.source_cache, args.reference_source)
