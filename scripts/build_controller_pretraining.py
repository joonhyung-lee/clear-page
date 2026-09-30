"""Add a compact embodiment-wise view of policy playback and recorded PPO training."""
from pathlib import Path
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1]
p=root/'index.html';s=BeautifulSoup(p.read_text(),'html.parser')
old=s.select_one('#controller-pretraining')
if old:old.decompose()
buttons=''.join(f'<button type="button" data-loco-body="{key}" aria-pressed="{str(key=="g1").lower()}">{label}</button>' for key,label in [('g1','G1'),('spot','Spot'),('spot_arm','Spot + arm')])
videos=''.join(f'<div class="viewer loco-viewer" data-loco-viewer="{key}" data-scene="learning-{key}" data-generation="true" data-title="{label} learning checkpoints" {"" if key=="g1" else "hidden"}><img class="preview-image" src="assets/media/learning-{key}.png" alt="{label} checkpoint on a mixed terrain bank"/><button class="launch" type="button">Explore learning in 3D</button></div>' for key,label in [('g1','G1'),('spot','Spot'),('spot_arm','Spot + arm')])
plots=''.join(f'<figure class="loco-chart" data-loco-chart="{i}"><figcaption></figcaption><canvas tabindex="0" role="img" aria-label="Recorded controller training metric. Use arrow keys, Home and End to inspect iterations."></canvas><div class="loco-tooltip" hidden></div></figure>' for i in range(3))
html=f'''<section id="controller-pretraining" aria-labelledby="pretraining-title"><h4 id="pretraining-title">Learning to move across terrain</h4>
<p class="method-small-copy">Intermediate checkpoints reveal how navigation policies develop during PPO training. Compare the same terrain bank at successive iterations and inspect the corresponding recorded losses and curriculum traces. CLEAR uses these controllers beneath its interaction planner.</p>
<div class="loco-toolbar"><div class="loco-bodies" role="group" aria-label="Controller embodiment">{buttons}</div><span class="loco-checkpoint"></span></div>
<div class="loco-row"><figure class="loco-rollout">{videos}<div class="loco-stages" role="group" aria-label="Recorded learning checkpoints"></div><figcaption>32 independent environments · stairs, slopes and flat terrain</figcaption><div class="loco-terrain-legend" aria-label="Terrain colors"><span data-terrain="flat" style="--terrain:rgb(160,199,224)">Flat floor</span><span data-terrain="stairs_up" style="--terrain:rgb(235,177,140)">Stairs up</span><span data-terrain="stairs_down" style="--terrain:rgb(232,215,143)">Stairs down</span><span data-terrain="slope_up" style="--terrain:rgb(153,205,168)">Slope up</span><span data-terrain="slope_down" style="--terrain:rgb(177,166,218)">Slope down</span><span data-terrain="random_rough" style="--terrain:rgb(218,162,197)">Rough terrain</span></div><p class="loco-body-note"></p><p class="loco-camera-note">Drag to orbit · scroll to zoom · shift drag to pan</p></figure>
<div class="loco-evidence"><div class="loco-metrics" role="group" aria-label="Training metrics"><button type="button" data-loco-metrics="optimization" aria-pressed="true">PPO losses</button><button type="button" data-loco-metrics="task" aria-pressed="false">Training progress</button></div>
<p class="loco-loading" role="status">Training evidence loads when this section enters view.</p><div class="loco-charts" hidden>{plots}</div><div class="loco-phases" aria-label="Training stages"></div><p class="loco-status" aria-live="polite"></p></div></div>
<p class="loco-evidence-note">Reconstructed checkpoint policies share a fixed terrain bank. Curves show the original logged training values. Numbered markers connect each replay to its training iteration.</p>
<p class="figure-caption training-context-summary">Checkpoint curves follow the recorded training lineage. Spot and Spot + arm have separate physical models and new training lineages. G1 pushing uses a separate frozen policy, while Husky uses differential drive.</p>
</section>'''
s.select_one('#method-grounding > .method-lead').insert_after(BeautifulSoup(html,'html.parser'))
node=s.select_one('#method-grounding > #embodiment-demo')
if node:
 d=s.new_tag('section',attrs={'class':'reading-detail','id':'grounding-mesh'})
 summary=s.new_tag('h4');summary.string='Inspect embodiment mesh and interaction highlights';d.append(summary)
 node.insert_before(d);d.append(node.extract())
for name in ['controller-pretraining.css','controller-pretraining.js']:
 path='assets/'+name
 if not any((e.get('src') or e.get('href') or '').split('?')[0]==path for e in s.select('script[src],link[href]')):
  s.head.append(s.new_tag('link',rel='stylesheet',href=path) if name.endswith('css') else s.new_tag('script',src=path,defer=''))
p.write_text(str(s).rstrip()+'\n')
# Keep the shared embodiment selector and new training panel on rebuilds.
import subprocess, sys
subprocess.run([sys.executable, str(root/'scripts/build_spot_curriculum.py')], check=True)
