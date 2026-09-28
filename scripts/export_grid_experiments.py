"""Export anonymous grid experiment replays from recorded numeric frames.

Only geometry, poses, public method labels, and observed outcomes are emitted.
The source bundle and its provenance remain outside the website.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import trimesh
import viser

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
methods = {'autoregressive': 'Autoregressive', 'gumbel_sinkhorn': 'Gumbel–Sinkhorn',
           'polynet': 'PolyNet', 'clear_ro': 'CLEAR-RO', 'clear_ho': 'CLEAR-HO', 'clear': 'CLEAR (ours)'}
colors = [(120, 162, 174), (189, 147, 111), (157, 168, 125), (162, 146, 180), (194, 168, 116)]
manifest = []
for family in sorted(args.source.iterdir()):
    if not family.is_dir(): continue
    for method, label in methods.items():
        folder = family / method
        if not (folder / 'frames.npz').exists(): continue
        bundle = json.loads((folder / 'bundle.json').read_text())
        frames = np.load(folder / 'frames.npz', allow_pickle=False)
        grid = bundle['grid']; height = len(grid); width = len(grid[0])
        key = 'grid-' + family.name.split('_', 1)[-1] + '-' + method.replace('_', '-')
        server = viser.ViserServer(host='127.0.0.1', port=8099, verbose=False)
        server.gui.configure_theme(show_logo=False, show_share_button=False)
        server.scene.world_axes.visible = False
        server.initial_camera.position = (width/2, -height*.35, height*1.3)
        server.initial_camera.look_at = (width/2, height/2, 0)
        server.initial_camera.fov = .9
        def xyz(rc, z): return (float(rc[1])+.5, height-float(rc[0])-.5, z)
        wall = trimesh.creation.box(extents=(.98,.98,.45))
        for r, row in enumerate(grid):
            for c, cell in enumerate(row):
                if cell == '#':
                    server.scene.add_mesh_simple(f'/wall-{r}-{c}', vertices=wall.vertices, faces=wall.faces,
                                                 color=(187,193,199), position=xyz((r,c),.225))
        sphere = trimesh.creation.icosphere(subdivisions=2, radius=.32)
        agent = server.scene.add_mesh_simple('/agent', vertices=sphere.vertices, faces=sphere.faces, color=(48,112,149))
        block = trimesh.creation.box(extents=(.75,.75,.65))
        objects = [server.scene.add_mesh_simple(f'/object-{j}', vertices=block.vertices, faces=block.faces,
                                                color=colors[j%len(colors)]) for j in range(frames['obj_rc'].shape[1])]
        goal = trimesh.creation.cylinder(radius=.4,height=.04,sections=32)
        server.scene.add_mesh_simple('/goal',vertices=goal.vertices,faces=goal.faces,color=(98,153,110),position=xyz(bundle['goal'],.025))
        server.scene.add_grid('/floor',width=width,height=height,position=(width/2,height/2,0),cell_color=(234,236,238),section_color=(234,236,238))
        def pose(k):
            agent.position = xyz(frames['agent_rc'][k], .33)
            for j, obj in enumerate(objects):obj.position = xyz(frames['obj_rc'][k,j],.325)
        pose(0); recording = server.get_scene_serializer()
        count = len(frames['agent_rc'])
        for k in range(count):
            pose(k);recording.insert_sleep(max(.08,min(.25,12/max(1,count))))
        (root/'assets/recordings'/f'{key}.viser').write_bytes(recording.serialize());server.stop()
        # A pixel-only top view is a lightweight entry point to each 3D replay.
        scale = 24; pad = 24
        poster = Image.new('RGB',(width*scale+2*pad,height*scale+2*pad),'white');draw=ImageDraw.Draw(poster)
        def rect(rc,inset=1):
            r,c=rc;return (pad+c*scale+inset,pad+r*scale+inset,pad+(c+1)*scale-inset,pad+(r+1)*scale-inset)
        for r,row in enumerate(grid):
            for c,cell in enumerate(row):draw.rectangle(rect((r,c)),fill=(187,193,199) if cell=='#' else (248,249,250))
        draw.ellipse(rect(bundle['goal'],3),fill=(98,153,110))
        for j,rc in enumerate(frames['obj_rc'][0]):draw.rectangle(rect(rc,3),fill=colors[j%len(colors)])
        draw.ellipse(rect(frames['agent_rc'][0],4),fill=(48,112,149))
        poster.save(root/'assets/media'/f'{key}.png')
        outcome=bundle['outcome']
        manifest.append(dict(scene=key,family=family.name.split('_',1)[-1],method=label,
                             success=bool(outcome['task_success']),interactions=len(outcome.get('executed_order',[])),
                             frames=count))
        print(key,flush=True)
(root/'assets/grid-experiments.json').write_text(json.dumps(manifest,indent=2)+'\n')
