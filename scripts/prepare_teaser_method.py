"""Convert the archived teaser map into the planner's metric scene schema.

Only geometry and explicitly designated reference routes are exported. No
archived notes, machine paths, or execution claims are copied into public data.
"""
import argparse
import json
from pathlib import Path


def convert(spec):
    grid = list(reversed(spec['rows_north_to_south']))
    depth, width = len(grid), len(grid[0])
    walls, terrain = [], []
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            bounds = [x, y, x + 1, y + 1]
            if cell == '#':
                walls.append(bounds)
            elif cell == 'P':
                terrain.append(dict(kind='flat', bounds=bounds,
                                    height_m=spec['plateau_h'], friction=.8))
            elif cell in 'SR':
                rise = spec['terrain_rise_per_cell']
                base = sum(grid[j][x] == cell for j in range(y)) * rise
                if cell == 'S':
                    for step in range(2):
                        terrain.append(dict(kind='stair_tread',
                            bounds=[x, y + step / 2, x + 1, y + (step + 1) / 2],
                            height_m=base + (step + 1) * rise / 2, friction=.8))
                else:
                    terrain.append(dict(kind='ramp', bounds=bounds, axis=1,
                        start_height_m=base, end_height_m=base + rise, friction=.8))
    # Physical border surrounds the entire original course.
    walls += [[-1, -1, width + 1, 0], [-1, depth, width + 1, depth + 1],
              [-1, 0, 0, depth], [width, 0, width + 1, depth]]
    objects = []
    for i, crate in enumerate(spec['crates'].values()):
        y, x = crate['cell']
        objects.append(dict(object_id=i, pose=[x + .5, y + .5, 0.],
                            size=[.88, .88, 1.2], mass_kg=3., friction=.4))
    sy, sx = spec['start']; gy, gx = spec['goal']
    return dict(world_size=[width, depth], start=[sx + .5, sy + .5, spec['initial_yaw']],
                goal=[gx + .5, gy + .5], walls=walls, terrain=terrain, objects=objects)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('map', type=Path); p.add_argument('output', type=Path)
    a = p.parse_args(); spec = json.loads(a.map.read_text()); scene = convert(spec)
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output / 'scene.json').write_text(json.dumps(scene, indent=2))
    initial = scene['objects'][0]['pose']
    target = spec['routes']['g1']['push_target_xy'] + [0.]
    plan = dict(plan=dict(paths=[dict(object_id=0, poses=[initial, target])]),
                scope='Designated teaser reference interaction. This route was specified for the demonstration, not produced by the learned planner or logged as a training target.')
    (a.output / 'planner.json').write_text(json.dumps(plan, indent=2))
    print('Prepared teaser scene:', len(scene['objects']), 'objects, two stairs and one ramp')
