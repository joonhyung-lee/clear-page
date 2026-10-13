"""Build qualitative replay matrices from anonymous numeric manifests."""
import json,html
from pathlib import Path
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1]
maze=json.loads((root/'assets/maze-experiments.json').read_text());manip=json.loads((root/'assets/manipulation-experiments.json').read_text())
def tile(e):
 key=e['scene'];label=html.escape(e['method']);replay=e.get('replay',True)
 status=('Goal reached' if e['success'] else 'Goal not reached') if replay else 'No valid plan'
 detail=f'{e["duration"]:g} s execution' if replay else ''
 if 'violations' in e:detail+=f' · {e["violations"]} precondition violations'
 return f'<article><h4>{label}</h4><div class="viewer experiment-viewer" data-scene="{key}" data-title="{label}"><img class="preview-image" src="assets/media/{key}.png" alt="{label} scene" width="700" height="540" loading="lazy"><button class="launch" type="button">'+('Play in 3D' if replay else 'Inspect in 3D')+f'</button></div><p class="replay-outcome">{status}<br>{detail}</p></article>'
def matrix(entries):return '<div class="experiment-matrix">'+''.join(tile(e) for e in sorted(entries,key=lambda e:0 if e['method']=='CLEAR (ours)' else 1))+'</div>'
parts=['''<section class="experiment" id="experiment-manipulation"><h3>Ordered Manipulation</h3><p class="experiment-claim">Successful manipulation requires both correct targets and satisfied interaction preconditions.</p><p>A UR5e arm manipulates a cube, two buttons, a drawer, and a sliding window. Button requirements determine when the drawer and window become available. The evaluation tests unseen combinations of those requirements. All methods share an MPC controller and replan after interactions.</p><p>The comparison evaluates classical search, behavior cloning, and ablations of grounding, affordance conditioning, and causal attention. Episode outcomes report goal completion and precondition violations.</p>''',matrix(manip),'<p class="viewer-note">Joint configurations and button states show the interaction sequence.</p></section>']
parts.append('''<section class="experiment" id="experiment-maze"><h3>Maze Navigation</h3><p class="experiment-claim">Robot structure changes which routes and object interactions are feasible.</p><p>The evaluation considers G1, Spot, Spot with an arm, and Husky in shared environments with terrain and movable obstacles. Standard scenes vary traversability and interaction requirements. High mass scenes include objects weighing 11.5 kg. Each embodiment uses a fixed controller across planning methods.</p><p>The sequences show high-mass interactions for G1 and Spot + arm, followed by terrain traversal for G1.</p><label class="scenario-control">Comparison <select id="maze-family"><option value="highmass-g1">High mass · G1</option><option value="highmass-spot-arm">High mass · Spot with arm</option><option value="terrain-g1">Terrain · G1</option></select></label>''')
for group in ['highmass-g1','highmass-spot-arm','terrain-g1']:
 parts.append(f'<div data-maze-family="{group}"'+(' hidden' if group!='highmass-g1' else '')+'>'+matrix([e for e in maze if e['experiment']=='exp3' and e['group']==group])+'</div>')
parts.append('<p class="viewer-note">Candidates without a valid plan are shown in the initial scene.</p></section>')
parts.append('''<section class="experiment" id="experiment-horizon"><h3>Long Horizon Planning</h3><p class="experiment-claim">Replanning updates later interactions when changes in the scene invalidate the remaining plan.</p><p>The experiment compares CLEAR with a variant that retains its initial plan. Both share the learned checkpoint, controller, and execution limits. The paper evaluates nominal execution, displaced target objects, and changes in access to later interactions. Low level feedback alone cannot revise the high level interaction sequence.</p><p>The paired replays show how the planner responds to external object relocations and updates the remaining interactions.</p>''')
for group in ['A','B']:
 parts.append(f'<h4 class="comparison-label">Scene {group}</h4><div class="experiment-matrix paired-matrix">'+''.join(tile(e) for e in maze if e['experiment']=='exp4' and e['group']==group)+'</div>')
parts.append('<p class="viewer-note">External object relocations perturb the planned interaction sequence.</p></section>')
soup=BeautifulSoup((root/'index.html').read_text(),'html.parser');parent=soup.find(id='experiments')
for name in ['experiment-manipulation','experiment-maze','experiment-horizon']:
 old=soup.find(id=name)
 if old:old.decompose()
parent.append(BeautifulSoup(''.join(parts),'html.parser'));(root/'index.html').write_text(str(soup).rstrip()+'\n')
