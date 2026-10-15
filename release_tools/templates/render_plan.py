"""Draw a maze scene with its planned object paths and route: a window, a PNG or an mp4."""
import argparse
import json
import math
from pathlib import Path

import numpy as np

COLORS = dict(wall='#9aa0a6', terrain='#9fc5e8', object='#e8b36b', moved='#c98a4b', route='#3b76d9', robot='#1f3f8f', goal='#d94040')


def load(input_path, plan_path):
    return json.loads(Path(input_path).read_text())['scene'], json.loads(Path(plan_path).read_text())


def box(ax, x, y, sx, sy, yaw=0.0, **kw):
    from matplotlib.patches import Rectangle
    from matplotlib.transforms import Affine2D
    patch = Rectangle((-sx / 2, -sy / 2), sx, sy, **kw)
    patch.set_transform(Affine2D().rotate(yaw).translate(x, y) + ax.transData)
    ax.add_patch(patch)
    return patch


def draw_scene(ax, scene):
    w, h = scene['world_size']
    for x0, y0, x1, y1 in scene['walls']:
        box(ax, (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0, facecolor=COLORS['wall'], edgecolor='none', zorder=2)
    top = max([t.get('height_m', 0) for t in scene.get('terrain', [])] + [1e-6])
    for t in scene.get('terrain', []):
        x0, y0, x1, y1 = t['bounds']
        box(ax, (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0, facecolor=COLORS['terrain'],
            alpha=0.25 + 0.6 * t.get('height_m', 0) / top, edgecolor='#5b8ab8', lw=0.5, zorder=1)
    ax.plot(scene['start'][0], scene['start'][1], 's', color=COLORS['robot'], ms=9, zorder=5)
    ax.plot(scene['goal'][0], scene['goal'][1], '*', color=COLORS['goal'], ms=16, zorder=5)
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])


def interpolate(points, s):
    """Point at normalised arc length s in [0, 1] along a polyline."""
    p = np.asarray(points, float)
    if len(p) < 2:
        return p[0]
    seg = np.linalg.norm(np.diff(p[:, :2], axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    d = s * cum[-1]
    i = min(int(np.searchsorted(cum, d, side='right')) - 1, len(seg) - 1)
    f = 0 if seg[i] == 0 else (d - cum[i]) / seg[i]
    return p[i] + f * (p[i + 1] - p[i])


def animation(scene, plan, fps=30, seconds_per_segment=2.0):
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    fig, ax = plt.subplots(figsize=(6, 6))
    draw_scene(ax, scene)
    paths = {p['object_id']: p for p in plan['plan']['paths']}
    patches = {}
    for o in scene['objects']:
        x, y, yaw = o['pose']
        moved = o['object_id'] in paths
        patches[o['object_id']] = box(ax, x, y, o['size'][0], o['size'][1], yaw, facecolor=COLORS['moved' if moved else 'object'],
                                      edgecolor='k', lw=0.6, zorder=3)
        ax.text(x, y, str(o['object_id']), ha='center', va='center', fontsize=8, zorder=4)
    route = plan.get('route') or [scene['start'][:2]]
    ax.plot([p[0] for p in route], [p[1] for p in route], '-', color=COLORS['route'], lw=1.5, alpha=0.6, zorder=4)
    robot, = ax.plot([scene['start'][0]], [scene['start'][1]], 'o', color=COLORS['robot'], ms=11, zorder=6)
    segments = [('object', p) for p in plan['plan']['paths']] + [('route', route)]
    ax.set_title(f"{plan['status']} · {len(paths)} interaction(s)", fontsize=10)
    frames = int(fps * seconds_per_segment)

    def update(k):
        i, s = divmod(k, frames)
        kind, item = segments[min(i, len(segments) - 1)]
        s = min(s / max(frames - 1, 1), 1.0)
        if kind == 'object':
            x, y, yaw = interpolate(item['poses'], s)
            o = next(o for o in scene['objects'] if o['object_id'] == item['object_id'])
            patches[item['object_id']].remove()
            patches[item['object_id']] = box(ax, x, y, o['size'][0], o['size'][1], yaw, facecolor=COLORS['moved'], edgecolor='k', lw=0.6, zorder=3)
        else:
            x, y = interpolate(item, s)[:2]
            robot.set_data([x], [y])
        return [robot, *patches.values()]

    return fig, FuncAnimation(fig, update, frames=frames * len(segments), interval=1000 / fps, blit=False, repeat=True)


def show(input_path, plan_path, video=None, png=None, fps=30):
    import matplotlib
    if video or png:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    scene, plan = load(input_path, plan_path)
    if png:
        fig, ax = plt.subplots(figsize=(6, 6)); draw_scene(ax, scene)
        route = plan.get('route') or []
        for o in scene['objects']:
            box(ax, *o['pose'][:2], o['size'][0], o['size'][1], o['pose'][2], facecolor=COLORS['object'], edgecolor='k', lw=0.6, zorder=3)
        if route:
            ax.plot([p[0] for p in route], [p[1] for p in route], '-', color=COLORS['route'], lw=2, zorder=4)
        ax.set_title(plan['status'], fontsize=10); fig.savefig(png, dpi=120, bbox_inches='tight'); plt.close(fig)
    if video:
        try:
            import imageio_ffmpeg
            matplotlib.rcParams['animation.ffmpeg_path'] = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass
        from matplotlib.animation import FFMpegWriter
        fig, anim = animation(scene, plan, fps)
        anim.save(video, writer=FFMpegWriter(fps=fps, bitrate=1800)); plt.close(fig)
        print('wrote', video)
    elif not png:
        if 'agg' in matplotlib.get_backend().lower():
            print('no display available: pass --video FILE.mp4 to render headless')
            return
        fig, anim = animation(scene, plan, fps)
        plt.show()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True); p.add_argument('--plan', required=True)
    p.add_argument('--video'); p.add_argument('--png')
    a = p.parse_args(); show(a.input, a.plan, a.video, a.png)
