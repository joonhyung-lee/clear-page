"""Synchronized third-person, ego, attention and map views of a native Viser replay."""
import argparse
import json
import subprocess
import time
from pathlib import Path
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.spatial.transform import Rotation
from attention_lanes import box_vertices, draw_query_marker
from replanning_mesh_renderer import MeshRenderer, camera_matrix
from replanning_timeline import at_time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--telemetry', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--start', type=float, default=0)
p.add_argument('--end', type=float)
p.add_argument('--speed', type=float, default=2)
p.add_argument('--preview', action='store_true')
p.add_argument('--layout-preview', action='store_true', help='Explicitly mark unpaired renderer validation data')
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
d = json.loads((a.source/'timeline.json').read_text())
with np.load(a.source/'geometry.npz') as archive:
    g = dict(archive)
logs = {int(f.stem.split('-')[-1]): json.loads(f.read_text()) for f in a.telemetry.glob('planning-*.json')}
capture = json.loads((a.telemetry/'capture.json').read_text())
W, H = 1280, 720
renderer = MeshRenderer(g, d['meshes'])
fonts = {n: ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', n) for n in [12, 13, 14, 16, 18, 22]}
sizes = {o['object_id']: o['size'] for o in d['scene']['objects']}
objects = {int(k): v for k, v in d['object_bodies'].items()}
body_to_object = {b: oid for oid, b in objects.items()}
ego_body, root_body = d.get('ego_body', 16), d.get('root_body', 1)
world = np.asarray(d['scene']['world_size'])
map_camera = camera_matrix([*world/2, 25], [*world/2, 0], 300/225,
                           extent=max(world[1]+1, (world[0]+1)*225/300))
palette = {'added': '#387cc2', 'changed': '#387cc2', 'unchanged': '#378469', 'removed': '#a0a8b0', 'executed': '#b3b9b5'}
root_yaw = np.unwrap(Rotation.from_quat(g['quaternions'][:, root_body], scalar_first=True).as_euler('xyz')[:, 2])

def text(image, xy, value, size=14, color='#35443e'):
    ImageDraw.Draw(image).text(xy, value, font=fonts[size], fill=color)

def project(camera, xyz, width, height):
    q = camera@np.r_[xyz, 1]
    if q[3] <= 0 or np.any(np.abs(q[:2]/q[3]) > 5):
        return None
    return ((q[0]/q[3]+1)*width/2, (1-q[1]/q[3])*height/2)

def overlays(picture, camera, state, poses, map_view=False):
    draw = ImageDraw.Draw(picture)
    w, h = picture.size
    current, previous = state['current'], state['previous']
    def path(path, color, ghosts):
        z = sizes[path['object_id']][2] + .03
        pts = [project(camera, [*pose[:2], z], w, h) for pose in path['poses']]
        for v, u in zip(pts, pts[1:]):
            if v is not None and u is not None:
                draw.line([v, u], fill=color, width=2 if map_view else 4)
        for v in pts:
            if v is not None:
                x, y = v
                r = 2 if map_view else 3
                draw.ellipse((x-r, y-r, x+r, y+r), fill=color)
        if ghosts:
            for pose in [path['poses'][len(path['poses'])//2], path['poses'][-1]]:
                vv = [project(camera, v, w, h) for v in box_vertices(pose, sizes[path['object_id']])]
                for i, j in [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]:
                    if vv[i] is not None and vv[j] is not None:
                        draw.line([vv[i], vv[j]], fill=color, width=1 if map_view else 2)
    if previous and current and t-current['time'] < 6:
        for old in previous['paths']:
            if state['changes'][old['object_id']] in ['changed', 'removed']:
                path(old, palette['removed'], False)
    if current:
        if current.get('route'):
            route = [project(camera, [*point[:2], .04], w, h) for point in current['route']]
            for v, u in zip(route, route[1:]):
                if v is not None and u is not None:
                    draw.line([v, u], fill='#527e92', width=2)
        pending_paths = [item for item in current['paths'] if item['object_id'] not in state['fulfilled']]
        for item in pending_paths if map_view else pending_paths[:2]:
            path(item, palette[state['changes'][item['object_id']]], True)
    for item in state.get('conditioned', []):
        path(item, '#378469', False)
    for kind in ['start', 'goal']:
        xy = project(camera, [*d['scene'][kind][:2], .03], w, h)
        if xy is not None:
            draw_query_marker(picture, xy, kind, 14 if map_view else 24)
    draw = ImageDraw.Draw(picture)
    xy = project(camera, poses[root_body], w, h)
    if map_view and xy is not None:
        x, y = xy
        draw.ellipse((x-4, y-4, x+4, y+4), fill='#173e3d')
    if state['event']:
        b = objects[state['event']['object_id']]
        xy = project(camera, poses[b]+[0, 0, .6], w, h)
        if xy is not None:
            x, y = xy
            r = 9 if map_view else 22
            draw.ellipse((x-r, y-r, x+r, y+r), outline='#c17835', width=3)
    return picture

end = min(d['duration'], a.end if a.end is not None else d['duration'])
assert end > a.start >= 0 and a.speed > 0
times = [a.start, (a.start+end)/2, end] if a.preview else np.minimum(
    a.start+np.arange(int(np.ceil((end-a.start)*25/a.speed))+1)*a.speed/25, end)
schedule = []
inserted = set()
for stamp in times:
    for plan in d['plans']:
        log = logs.get(plan['call'])
        if (not a.preview and plan['call'] not in inserted and a.start <= plan['time'] <= stamp
                and log and log['time_s'] <= plan['time']+1e-6 and log['snapshots']):
            # Replay measured integration states, with physics time held fixed.
            snapshots = log['snapshots']
            selected = plan.get('selected_candidate')
            candidate = 0 if selected is None else selected
            conditioned_bank = capture['method'] == 'inpainting' and log['prefix'] and len(snapshots) >= 60
            if conditioned_bank and candidate < 4:
                snapshots = snapshots[-30:]
            else:
                snapshots = snapshots[:30]
                if conditioned_bank:
                    candidate -= 4
            for snapshot in snapshots:
                frame = dict(snapshot, sample=candidate, accepted=selected is not None,
                             conditioned=bool(conditioned_bank and (selected is None or selected < 4)))
                schedule.extend([(plan['time'], frame, log)]*2)
            inserted.add(plan['call'])
    schedule.append((stamp, None, None))
if not a.preview and end == d['duration']:
    schedule.extend([(end, None, None)]*50)
proc = None
target = a.output/'replanning-multiview.mp4'
if not a.preview:
    proc = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-v', 'error', '-f', 'rawvideo',
        '-pix_fmt', 'rgb24', '-s', '1280x720', '-r', '25', '-i', '-', '-an', '-map_metadata', '-1',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(target)], stdin=subprocess.PIPE)
audit = []
clock = time.monotonic()
try:
    for index, (t, generating, generation_log) in enumerate(schedule):
        j = min(np.searchsorted(g['time'], t, side='right'), len(g['time'])-1)
        i = max(j-1, 0)
        u = np.clip((t-g['time'][i])/max(g['time'][j]-g['time'][i], 1e-9), 0, 1)
        poses = (1-u)*g['positions'][i] + u*g['positions'][j]
        q0, q1 = g['quaternions'][i], g['quaternions'][j]
        q1 = np.where((q0*q1).sum(-1, keepdims=True) < 0, -q1, q1)
        q = (1-u)*q0+u*q1
        q /= np.linalg.norm(q, axis=-1, keepdims=True)
        rot = Rotation.from_quat(q, scalar_first=True).as_matrix()
        matrices = np.tile(np.eye(4), (len(poses), 1, 1))
        matrices[:, :3, :3], matrices[:, :3, 3] = rot, poses
        # Trailing causal average smooths the camera without changing the poses.
        history = np.linspace(max(0, t-.25), t, 7)
        center = np.array([np.interp(history, g['time'], g['positions'][:, root_body, k]).mean() for k in range(3)])
        yaw = np.interp(history, g['time'], root_yaw).mean()
        heading = np.array([np.cos(yaw), np.sin(yaw), 0])
        chase_eye = center-2.8*heading+[0, 0, 3.5]
        chase_target = center+1.2*heading+[0, 0, .1]
        overview = 0.
        for event in d['events']:
            if event['start_time_s'] <= t <= event['end_time_s']+5:
                overview = float(np.clip(min(t-event['start_time_s'], event['end_time_s']+5-t), 0, 1))
        overview = overview*overview*(3-2*overview)
        map_center = np.r_[world/2, 0.]
        third = camera_matrix((1-overview)*chase_eye+overview*(map_center+[0, -world[1]*.6, max(world)*1.2]),
            (1-overview)*chase_target+overview*map_center, 930/570, fov=52)
        ego_eye = poses[ego_body]+rot[ego_body]@np.asarray(d.get('ego_offset', [.14, 0, .30]))
        ego = camera_matrix(ego_eye, ego_eye+rot[ego_body]@np.array([1., 0, -.36]), 320/180, fov=88)
        state = at_time(d, float(t))
        current = state['current']
        display_state = state
        if generating is not None:
            # Show one actual candidate, never imply it is the accepted plan.
            candidate_paths = []
            ids_in = [o['object_id'] for o in generation_log['scene']['objects']]
            prefix = set(generation_log['prefix'])
            sample = generating['sample']
            ranks = np.asarray(generating['rank'][sample])
            for slot in np.argsort(ranks):
                oid = ids_in[slot]
                if not generating['selected'][sample][slot] or (generating['conditioned'] and oid in prefix):
                    continue
                obj = generation_log['scene']['objects'][slot]
                code = np.asarray(generating['code'][sample][slot]).reshape(-1, 4)
                xy = code[:, :2]*world + obj['pose'][:2]
                yaw_code = np.arctan2(code[:, 2], code[:, 3])
                candidate_paths.append(dict(object_id=oid, poses=[obj['pose']] + np.c_[xy, yaw_code].tolist()))
            display_state = dict(state, current=dict(current, paths=candidate_paths,
                order=[item['object_id'] for item in candidate_paths]), previous=None,
                changes={item['object_id']: 'changed' for item in candidate_paths})
            initial_objects = {o['object_id']: o for o in d['scene']['objects']}
            display_state['conditioned'] = [dict(object_id=o['object_id'],
                poses=[initial_objects[o['object_id']]['pose'], o['pose']])
                for o in generation_log['scene']['objects'] if o['object_id'] in prefix and generating['conditioned']]
        image = Image.new('RGB', (W, H), '#fafbf8')
        main = Image.fromarray(renderer.render(matrices, third, 930, 570))
        image.paste(overlays(main, third, display_state, poses), (0, 52))
        minimap = Image.fromarray(renderer.render(matrices, map_camera, 300, 225))
        trail = [project(map_camera, xyz, 300, 225) for xyz in g['positions'][:i+1:5, root_body]]
        trail.append(project(map_camera, poses[root_body], 300, 225))
        trail = [xy for xy in trail if xy is not None]
        if len(trail) > 1:
            ImageDraw.Draw(minimap).line(trail, fill='#8b9f96', width=1)
        minimap = overlays(minimap, map_camera, display_state, poses, True)
        image.paste(minimap, (16, 384))
        ImageDraw.Draw(image).rectangle((16, 362, 316, 383), fill='#fafbf8')
        text(image, (24, 364), 'Minimap', 13)
        ego_rgb = renderer.render(matrices, ego, 320, 180)
        image.paste(Image.fromarray(ego_rgb), (948, 81))
        text(image, (948, 57), 'Ego RGB', 16)
        telemetry = logs.get(current['call']) if current else None
        if telemetry and telemetry['time_s'] > t+1e-6:
            telemetry = None
        attention = None
        query = None
        if telemetry and telemetry['snapshots']:
            active = [oid for oid in display_state['current']['order'] if oid not in state['fulfilled']]
            if active:
                query = active[0]
                ids = [o['object_id'] for o in telemetry['scene']['objects']]
                # Shared encoder attention precedes sampling. Candidate rows
                # repeat that same observation; take the first row explicitly.
                snapshot = telemetry['snapshots'][0] if generating is None else generating
                attention = np.asarray(snapshot['encoder_attention'])[0, ids.index(query)]
        colors = []
        for mesh in d['meshes']:
            grey = float(np.mean(mesh['color']))/255
            color = np.full(3, .30+.55*grey)
            oid = body_to_object.get(mesh['body'])
            if attention is not None and oid is not None:
                weight = float(attention[1+ids.index(oid)])
                # Fixed scale across every frame/method, never per-frame max.
                strength = min(1., np.sqrt(max(weight, 0))*2.5)
                color = (1-strength)*color+strength*np.array([.02, .32, .17])
            colors.append(color)
        image.paste(Image.fromarray(renderer.render(matrices, ego, 320, 180, colors=colors)), (948, 305))
        text(image, (948, 280), 'Ego attention', 16)
        if attention is None:
            text(image, (948, 493), 'No active object query', 13)
        else:
            text(image, (948, 493), f'Object {query} query · update {current["call"]}', 13)
            object_total = float(attention[1:1+len(ids)].sum())
            text(image, (948, 515), f'Objects {object_total:.0%}   Other tokens {1-object_total:.0%}', 12)
        title = {'naive': 'CLEAR · Naive (fixed plan)', 'replan': 'CLEAR · Replanning', 'inpainting': 'CLEAR · Causal inpainting'}[capture['method']]
        if a.layout_preview:
            title = 'Layout preview · archived motion'
        text(image, (20, 14), title, 22)
        text(image, (1070, 17), f'{t:.1f} s · '+('Planning' if generating is not None else f'{a.speed:g}×'), 16)
        text(image, (948, 554), 'Plan update '+str(current['call']) if current else 'Initial observation', 16)
        if generating is not None:
            text(image, (948, 580), f"Generation t = {generating['flow_t']:.2f}", 14)
            text(image, (948, 603), ('Conditioned' if generating['conditioned'] else 'Fresh') +
                 (' · selected candidate' if generating['accepted'] else ' · example candidate'), 13)
        elif state['event']:
            text(image, (948, 585), f"Object {state['event']['object_id']} displaced", 14, '#b07238')
        elif current:
            removed = [str(oid) for oid, change in state['changes'].items() if change == 'removed']
            if removed and t-current['time'] < 6:
                text(image, (948, 585), 'Removed: '+', '.join(removed), 14)
        text(image, (20, 638), 'Executed', 13, '#378469')
        text(image, (100, 636), ' → '.join(map(str, state['completed'])) or '—', 16, '#378469')
        pending = [] if current is None else [oid for oid in current['order'] if oid not in state['fulfilled']]
        text(image, (400, 638), 'Pending', 13)
        text(image, (480, 636), ' → '.join(map(str, pending)) or '—', 16, '#387cc2')
        draw = ImageDraw.Draw(image)
        x = lambda stamp: 20+910*(stamp-a.start)/(end-a.start)
        draw.line((20, 680, 930, 680), fill='#d5ddd7', width=4)
        for plan in d['plans']:
            if a.start <= plan['time'] <= end:
                draw.line((x(plan['time']), 674, x(plan['time']), 686), fill='#387cc2', width=2)
        draw.ellipse((x(t)-4, 676, x(t)+4, 684), fill='#243c34')
        text(image, (20, 695), 'Blue · updated paths     Green · unchanged paths     Gray · previous plan', 12)
        if t >= d['duration']-.04 and generating is None:
            text(image, (948, 641), d['outcome'].replace('_', ' ').capitalize(), 14)
        if a.preview or index in [0, len(schedule)//2, len(schedule)-1]:
            image.save(a.output/f'frame-{index:04d}.png')
        if proc:
            proc.stdin.write(image.tobytes())
        audit.append(dict(time=float(t), planCall=None if current is None else current['call'],
                          attentionQuery=query, attentionTotal=None if attention is None else float(attention.sum()),
                          generationTime=None if generating is None else generating['flow_t']))
        if index % 100 == 0:
            print(index, '/', len(schedule), 'elapsed', round(time.monotonic()-clock, 1), flush=True)
    if proc:
        proc.stdin.close()
        assert proc.wait() == 0
finally:
    if proc and proc.poll() is None:
        proc.terminate()
        proc.wait()
    renderer.close()
(a.output/'render-audit.json').write_text(json.dumps(dict(frames=audit, sourceEpisode=d['episodeSHA256'],
    layoutPreview=a.layout_preview, method=capture['method'],
    ego='Rendered body-mounted replay camera, not a separately recorded RGB sensor.',
    attention='Shared encoder attention averaged over heads and layers for the active object query at the latest planning call. Other tokens retain their probability mass.'), separators=(',', ':'))+'\n')
print('PASS synchronized multiview render', flush=True)
