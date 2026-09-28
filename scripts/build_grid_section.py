"""Build the grid comparison section from the anonymous replay manifest."""
import html
import json
from pathlib import Path
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1]
entries=json.loads((root/'assets/grid-experiments.json').read_text())
families=list(dict.fromkeys(x['family'] for x in entries))
labels={'direct':'Direct','single_gate':'Single gate','chain':'Chain','branch':'Branch','distractor':'Distractor'}
parts=['<section class="section wrap" id="experiments"><div class="section-heading"><h2>Experiments</h2></div><section id="experiment-grid" class="experiment"><h3>2D Grid</h3><p class="experiment-claim">Selective, ordered interactions open routes through blocked grids.</p><p>Five scene families isolate direct navigation, a single obstruction, interaction chains, branching alternatives, and irrelevant objects. Six planners are replayed on the same scene within each family. These evaluations execute the generated plan without a separate feasibility filter.</p><label class="scenario-control">Scene family <select id="grid-family">']
for family in families:parts.append(f'<option value="{family}"'+(' selected' if family=='chain' else '')+f'>{labels[family]}</option>')
parts.append('</select></label>')
for family in families:
 parts.append(f'<div class="experiment-matrix" data-family="{family}"'+(' hidden' if family!='chain' else '')+'>')
 for item in (x for x in entries if x['family']==family):
  key=item['scene'];label=html.escape(item['method']);status='Goal reached' if item['success'] else 'Goal not reached'
  parts.append(f'<article><h4>{label}</h4><div class="viewer experiment-viewer" data-scene="{key}" data-title="{label}"><img class="preview-image" src="assets/media/{key}.png" alt="{label} in the {labels[family].lower()} scene" loading="lazy" width="432" height="432"><button class="launch" type="button">Play in 3D</button></div><p class="replay-outcome">{status} · {item["interactions"]} recorded interactions</p></article>')
 parts.append('</div>')
parts.append('<p class="viewer-note">Blue denotes the robot and green denotes the goal. Colored blocks are movable objects. Each tile is an individual recorded episode, not an aggregate success rate. Playback preserves discrete grid transitions.</p></section></section>')
soup=BeautifulSoup((root/'index.html').read_text(),'html.parser')
old=soup.find(id='experiments')
preserved=[]
if old:
 for section in old.find_all('section',recursive=False):
  if section.get('id')!='experiment-grid':preserved.append(section.extract())
 old.decompose()
new=BeautifulSoup(''.join(parts),'html.parser')
for section in preserved:new.find(id='experiments').append(section)
soup.find('main').append(new)
(root/'index.html').write_text(str(soup).rstrip()+'\n')
