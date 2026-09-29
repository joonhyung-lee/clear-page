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
<div class="loco-row"><figure class="loco-rollout">{videos}<div class="loco-stages" role="group" aria-label="Recorded learning checkpoints"></div><figcaption>32 independent environments · stairs, slopes and flat terrain</figcaption><p class="loco-body-note"></p><p class="loco-camera-note">Drag to orbit · scroll to zoom · shift drag to pan</p></figure>
<div class="loco-evidence"><div class="loco-metrics" role="group" aria-label="Training metrics"><button type="button" data-loco-metrics="optimization" aria-pressed="true">PPO losses</button><button type="button" data-loco-metrics="task" aria-pressed="false">Training progress</button></div>
<p class="loco-loading" role="status">Training evidence loads when this section enters view.</p><div class="loco-charts" hidden>{plots}</div><div class="loco-phases" aria-label="Training stages"></div><p class="loco-status" aria-live="polite"></p></div></div>
<p class="loco-evidence-note">The viewer reconstructs saved intermediate policies on a common terrain bank using sampled actions. It is not footage captured during optimization. Curves are the original logged values, sampled every 25 iterations with stage endpoints retained. The vertical marker identifies the displayed checkpoint. Hover or tap to inspect a value.</p>
<details class="method-details"><summary>Training and deployment context</summary><p>The policy surrogate, value regression and entropy are reported separately. Reward and curriculum traces describe optimization progress and do not establish task success. Each trace follows the checkpoint’s actual training ancestry and ends at the selected iteration.</p><p>Spot is shown with its nominal arm training body. Deployment to the arm free body uses an observation adapter. Spot + arm continues the same policy lineage with an arm pose curriculum. For a controlled checkpoint comparison, both reconstructions hold the arm at the nominal pose and keep the terrain bank fixed. G1 begins from a warm start rather than an untrained policy. The plots, not the reconstructed terrain difficulty, document the historical curricula.</p><p>G1 pushing uses a separate frozen flat ground policy. Husky uses prescribed differential drive in this implementation and has no learned locomotion loss.</p></details>
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
