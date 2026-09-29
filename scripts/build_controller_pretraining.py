"""Add a compact embodiment-wise view of policy playback and recorded PPO training."""
from pathlib import Path
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1]
p=root/'index.html';s=BeautifulSoup(p.read_text(),'html.parser')
old=s.select_one('#controller-pretraining')
if old:old.decompose()
buttons=''.join(f'<button type="button" data-loco-body="{key}" aria-pressed="{str(key=="g1").lower()}">{label}</button>' for key,label in [('g1','G1'),('spot','Spot'),('spot_arm','Spot + arm')])
videos=''.join(f'<video data-loco-video="{key}" data-src="assets/media/locomotion-{key}.mp4" poster="assets/media/locomotion-{key}.png" aria-label="32 independent {label} policy rollouts" controls muted loop playsinline preload="none" {"" if key=="g1" else "hidden"}></video>' for key,label in [('g1','G1'),('spot','Spot'),('spot_arm','Spot + arm')])
plots=''.join(f'<figure class="loco-chart" data-loco-chart="{i}"><figcaption></figcaption><canvas tabindex="0" role="img" aria-label="Recorded controller training metric. Use arrow keys, Home and End to inspect iterations."></canvas><div class="loco-tooltip" hidden></div></figure>' for i in range(3))
html=f'''<section id="controller-pretraining" aria-labelledby="pretraining-title"><h4 id="pretraining-title">Pretrained low level control</h4>
<p class="method-small-copy">PPO trains the legged navigation policies to track velocity commands from proprioception. Terrain and body control curricula prepare them for execution. CLEAR then plans object interactions above these pretrained controllers.</p>
<div class="loco-toolbar"><div class="loco-bodies" role="group" aria-label="Controller embodiment">{buttons}</div><span class="loco-checkpoint"></span></div>
<div class="loco-row"><figure class="loco-rollout">{videos}<figcaption>32 parallel environments · random velocity commands</figcaption><p class="loco-body-note"></p></figure>
<div class="loco-evidence"><div class="loco-metrics" role="group" aria-label="Training metrics"><button type="button" data-loco-metrics="optimization" aria-pressed="true">PPO losses</button><button type="button" data-loco-metrics="task" aria-pressed="false">Training progress</button></div>
<p class="loco-loading" role="status">Training curves load when this section is nearby.</p><div class="loco-charts" hidden>{plots}</div><div class="loco-phases" aria-label="Training stages"></div><p class="loco-status" aria-live="polite"></p></div></div>
<p class="loco-evidence-note">Rollouts replay the selected frozen checkpoint on a flat practice floor. Curves come from its original training logs, sampled every 25 iterations with stage endpoints retained. Colors mark training stages. Hover or tap for recorded values.</p>
<details class="method-details"><summary>Training and deployment context</summary><p>The policy surrogate, value regression and entropy are reported separately. Reward and curriculum traces describe optimization progress and do not establish task success. Each trace follows the checkpoint’s actual training ancestry and ends at the selected iteration.</p><p>Spot transfers a policy trained with the arm in its nominal pose to the arm free body through the deployed observation adapter. Spot + arm continues with a curriculum that samples arm poses from a growing range. These playback videos are newly recorded policy evaluations, not footage captured during optimization.</p><p>G1 pushing uses a separate frozen flat ground policy. Husky uses prescribed differential drive in this implementation and has no learned locomotion loss.</p></details>
</section>'''
s.select_one('#method-grounding > .method-lead').insert_after(BeautifulSoup(html,'html.parser'))
node=s.select_one('#method-grounding > #embodiment-demo')
if node:
 d=s.new_tag('details',attrs={'class':'reading-detail','id':'grounding-mesh'})
 summary=s.new_tag('summary');summary.string='Inspect embodiment mesh and interaction highlights';d.append(summary)
 node.insert_before(d);d.append(node.extract())
for name in ['controller-pretraining.css','controller-pretraining.js']:
 path='assets/'+name
 if not any((e.get('src') or e.get('href') or '').split('?')[0]==path for e in s.select('script[src],link[href]')):
  s.head.append(s.new_tag('link',rel='stylesheet',href=path) if name.endswith('css') else s.new_tag('script',src=path,defer=''))
p.write_text(str(s).rstrip()+'\n')
