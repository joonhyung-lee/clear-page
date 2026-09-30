"""One numeric timeline for teaser flow integration and ordered ghost inspection.

The first six seconds replay the model's joint flow integration. The following
segments inspect the generated object paths in the supplied rank order. This
display schedule does not change the model sampler or claim physical execution.
"""
import argparse
import copy
import json
from pathlib import Path
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation
from export_teaser_method import setup, elevation, box_edges, COLORS
from maze_geometry_refinement import Clearance


def center(scene, i, pose):
    return [*pose[:2], elevation(scene, pose[:2]) + scene['objects'][i]['size'][2] / 2 + .01]


def interpolate(poses, fraction):
    k = np.clip(fraction, 0, 1) * (len(poses) - 1)
    lo = int(k)
    return (1 - (k-lo)) * np.asarray(poses[lo]) + (k-lo) * np.asarray(poses[min(lo+1, len(poses)-1)])


def state_at(trace, time, order):
    if time <= 6:
        k = min(time / 6 * 30, 30)
        lo, hi = int(k), min(int(k)+1, 30)
        return [dict(object=p['object'], poses=(1-(k-lo))*np.asarray(p['poses'])+(k-lo)*np.asarray(q['poses']))
                for p,q in zip(trace['states'][lo], trace['states'][hi])]
    return trace['states'][-1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('data', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    d = json.loads(a.data.read_text().split(' = ',1)[1].rstrip(';\n'))
    scene, order = d['scene'], d['conditionedOrder']
    d['timeline'] = dict(flowSeconds=6, objectSeconds=3, durationSeconds=6+3*len(order)+1)
    d['anchorHeightOffset'] = .01
    d['displayScope'] = 'Flow integration is joint. The subsequent ordered ghost inspection is a visualization of predicted paths, not an executed rollout.'
    base = setup(a.source, scene)
    for message_time, message in base.record['messages']:
        if message['type']=='SetCameraPositionMessage': message['position']=[17.,-10.,25.]
        if message['type']=='SetCameraLookAtMessage': message['look_at']=[5.,6.,.35]
    a.output.mkdir(parents=True, exist_ok=True)
    for sample, trace in enumerate(d['referenceFlow']):
        r = copy.deepcopy(base)
        r.record['durationSeconds'] = d['timeline']['durationSeconds']
        trace['refinement'] = []
        placed = {}
        for path in trace['states'][-1]:
            i = path['object']
            try:
                refined = Clearance(scene, i, placed).refine(np.asarray(path['poses']))
                placed[i] = refined[-1]
                trace['refinement'].append(dict(object=i, refined=True))
            except ValueError:
                trace['refinement'].append(dict(object=i, refined=False))
        # Clearance outcomes are reported, but both views retain the same raw
        # generated coordinates. Failed paths are never silently repaired.
        for path in trace['states'][0]:
            i, poses = path['object'], path['poses']
            points = np.array([center(scene,i,pose) for pose in poses])
            r.lines(f'/path-{i}', np.stack([points[:-1],points[1:]],1), COLORS[i], 3.)
            for j, point in enumerate(points):
                marker = trimesh.creation.icosphere(subdivisions=1, radius=.07)
                r.mesh(f'/anchor-{i}-{j}', marker.vertices, marker.faces, COLORS[i], point)
                if j == len(points)-1:
                    r.label(f'/anchor-label-{i}-{j}', f'Target {i}', point + [0,0,.12])
            for slot in range(2):
                r.lines(f'/ghost-{i}-{slot}', box_edges(scene['objects'][i]['size']), COLORS[i], 2.)
                box = trimesh.creation.box(extents=scene['objects'][i]['size'])
                r.mesh(f'/box-{i}-{slot}', box.vertices, box.faces, COLORS[i], points[-1], opacity=.12)
        for frame in range(round(r.record['durationSeconds']*30)+1):
            time = frame/30
            paths = state_at(trace, time, order)
            for path in paths:
                i, poses = path['object'], np.asarray(path['poses'])
                points = np.array([center(scene,i,pose) for pose in poses])
                if time <= 6:
                    r.line_update(f'/path-{i}', np.stack([points[:-1],points[1:]],1), COLORS[i], time)
                    for j,point in enumerate(points):
                        r.position(f'/anchor-{i}-{j}', point, time)
                        if j == len(points)-1:
                            r.position(f'/anchor-label-{i}-{j}', point+[0,0,.12], time)
                slot_poses = [poses[len(poses)//2], poses[-1]]
                if time > 6:
                    fraction = np.clip((time-6)/3-order.index(i), 0, 1)
                    slot_poses[0] = interpolate(poses, fraction)
                for slot, pose in enumerate(slot_poses):
                    xyz = center(scene,i,pose)
                    quat = Rotation.from_euler('z',pose[2]).as_quat(scalar_first=True).tolist()
                    for prefix in ('ghost', 'box'):
                        name = f'/{prefix}-{i}-{slot}'
                        r.position(name,xyz,time)
                        r.emit('SetOrientationMessage', time, name=name, wxyz=quat)
        # Native playback consumes messages strictly before the playhead.
        # Place each sample just before its displayed frame boundary.
        for entry in r.record['messages']:
            if entry[0] > 0: entry[0] -= 1e-6
        r.save(a.output / f'teaser-flow-{sample}.viser')
        print('Saved paired teaser flow', sample, 'order', order, 'checks', trace['refinement'], flush=True)
    a.data.write_text('window.CLEAR_TEASER_FLOW = '+json.dumps(d,separators=(',',':'))+';\n')


if __name__ == '__main__':
    main()
