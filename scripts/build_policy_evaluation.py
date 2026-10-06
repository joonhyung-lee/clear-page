"""Add measured policy evaluations, with an explicit unavailable state per lineage."""
from pathlib import Path
from bs4 import BeautifulSoup

root = Path(__file__).resolve().parents[1]
path = root / 'index.html'
soup = BeautifulSoup(path.read_text(), 'html.parser')
old = soup.select_one('#policy-evaluation')
if old:
    old.decompose()
if soup.select_one('[data-training-layout="unified"]'):
    path.write_text(str(soup).rstrip()+'\n')
    print('Unified training shows PPO losses and Training progress only')
    raise SystemExit(0)
html = '''<section id="policy-evaluation" aria-labelledby="policy-evaluation-title" data-mode="unmeasured">
<div class="eval-heading"><h5 id="policy-evaluation-title">Evaluating locomotion progress</h5><button type="button" data-eval-example aria-pressed="false">Show illustrative example</button></div>
<p class="eval-disclosure" role="status">Fixed-protocol evaluation has not been recorded for these plots. No measured values are shown.</p>
<div class="step"></div><p class="body-note"></p><div class="plots"></div>
<div class="legend" hidden><span><i class="swatch"></i>Example mean and illustrative spread</span><span><i class="dash"></i>Example value at update 0</span><span>Hover, tap or use arrow keys to inspect</span></div>
<div class="phases"></div>
<label class="scrub"><span>Update 0</span><input type="range" min="0" max="20" value="20" disabled aria-label="Inspect illustrative evaluation checkpoint"><span class="last-step"></span></label>
<details><summary>Evaluation protocol and interpretation</summary><p>The measured suite uses five terrain templates at four difficulty levels, with three initial condition seeds per tile. Every checkpoint receives the same terrain bank and initial states, with a world forward command of 0.5 m/s. Success requires 3 m of forward progress with lateral displacement no greater than 0.75 m at the goal, before a fall or the 20 s limit. A fall is a body tilt greater than 70 degrees. The robot starts at each tile center and travels toward its forward edge. Terrain names identify templates, not the direction of ascent.</p><p>Tracking is the mean of individual episode planar velocity RMSE values. Its band shows one episode standard deviation. Success and fall bands show 95% Wilson intervals. Each episode ends at its first goal, fall, or timeout. Short failed episodes can have low tracking error, so all three metrics must be read together. These bands do not measure variation across training seeds.</p><p>The archived G1 begins from a warm start. The new G1 and both new Spot lineages begin from their own random policies. Spot + arm is evaluated with its nominal arm pose throughout, so these plots do not measure robustness to arm motion. Dots identify evaluated checkpoints and straight lines connect them. A completed training phase does not establish task mastery.</p><p>An unevaluated controller lineage remains explicitly unmeasured. Any optional layout example uses synthetic values and is labeled separately.</p></details>
</section>'''
soup.select_one('#controller-pretraining').append(BeautifulSoup(html, 'html.parser'))
for name in ['policy-evaluation.css', 'policy-evaluation.js']:
    asset = 'assets/' + name
    if not any((node.get('src') or node.get('href') or '').split('?')[0] == asset
               for node in soup.select('script[src],link[href]')):
        soup.head.append(soup.new_tag('link', rel='stylesheet', href=asset)
                         if name.endswith('.css') else soup.new_tag('script', src=asset, defer=''))
data_asset = 'assets/policy-evaluation-data.js'
if (root / data_asset).exists():
    for node in list(soup.select('script[src^="assets/policy-evaluation-data.js"]')):
        node.decompose()
    script = soup.new_tag('script', src=data_asset, defer='')
    soup.select_one('script[src^="assets/policy-evaluation.js"]').insert_before(script)
scratch_asset = 'assets/g1_scratch-evaluation-data.js'
if (root / scratch_asset).exists():
    for node in list(soup.select('script[src^="assets/g1_scratch-evaluation-data.js"]')):
        node.decompose()
    soup.select_one('script[src^="assets/policy-evaluation.js"]').insert_before(
        soup.new_tag('script', src=scratch_asset, defer=''))
path.write_text(str(soup).rstrip() + '\n')
