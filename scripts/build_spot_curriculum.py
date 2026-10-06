"""Publish one from-scratch policy history per robot, with two metric views."""
from pathlib import Path
from bs4 import BeautifulSoup

root = Path(__file__).resolve().parents[1]
path = root / 'index.html'
soup = BeautifulSoup(path.read_text(), 'html.parser')
section = soup.select_one('#controller-pretraining')
toolbar = section.select_one('.policy-controls')
if toolbar:
    toolbar.extract()
    for metrics in toolbar.select('.loco-metrics'):
        metrics.decompose()
old = soup.select_one('#spot-curriculum')
if old:
    old.decompose()
# Both lineages use the same metric controls and visual vocabulary.
icons = {
    'optimization': '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 3v14h14M5 6l4 5 3-3 4 6"/></svg>',
    'task': '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 17h14M5 14V9m5 5V6m5 8V3"/></svg>',
}
labels = {'optimization': 'PPO losses', 'task': 'Training progress'}
for button in soup.select('[data-loco-metrics]'):
    key = button['data-loco-metrics']
    button.clear()
    button.append(BeautifulSoup(icons[key], 'html.parser'))
    button.append(labels[key])
controls = ''.join(f'<button type="button" data-curriculum-metrics="{key}" aria-pressed="{str(key == "optimization").lower()}">{icons[key]}{label}</button>' for key, label in labels.items())
html = f'''<div id="spot-curriculum">
<p class="method-small-copy" data-curriculum-intro>A new PPO training run starts from random initialization.</p>
<p class="scratch-status" data-curriculum-status role="status">Training progress loads nearby.</p>
<div class="loco-row scratch-layout">
<div class="loco-rollout">
<div data-curriculum-view></div>
<div class="scratch-description">
<p data-curriculum-caption>Initialization · 0 cumulative PPO updates</p>
<button type="button" data-curriculum-reset>Replay from update 0</button>
<p>Update 0 shows the random policy before its first action, including the recorded loss of balance.</p>
</div></div>
<div class="loco-evidence">
<div class="loco-metrics" role="group" aria-label="Training metrics">{controls}</div>
<div class="curriculum-timeline" data-curriculum-phases role="group" aria-label="Training phases"></div>
<p class="curriculum-phase-caption" data-curriculum-explanations aria-live="polite"></p>
<div class="scratch-curves" data-curriculum-curves></div>
<details class="curriculum-notes"><summary>About these plots</summary>
<p class="loco-evidence-note curriculum-baseline-note">Loss logging begins with PPO update 1. Dashed lines mark the first logged value.</p>
<p class="loco-evidence-note" data-curriculum-metric-note></p>
<p class="loco-evidence-note">The ribbon shows the planned schedule. Plots show recorded updates. Numbered markers open checkpoint replays.</p>
</details>
<p class="loco-status" data-curriculum-readout aria-live="polite"></p>
</div></div></div>'''
section = soup.select_one('#controller-pretraining')
section.select_one('#pretraining-title').string = 'Low-level policy training'
section.select_one(':scope > .method-small-copy').string = 'Select a robot to inspect its recorded PPO training and checkpoint replays.'
section['data-training-layout'] = 'unified'
controls = toolbar
if controls is None:
    controls = soup.new_tag('div', attrs={'class':'policy-controls'})
    controls.append(section.select_one('.loco-bodies').extract())
for node in list(section.select('.policy-sources, [data-policy-recorded], #policy-evaluation, .loco-toolbar, :scope > .loco-row, :scope > .loco-evidence-note, .training-context-summary')):
    node.decompose()
for script in list(soup.select('script[src],link[href]')):
    asset=(script.get('src') or script.get('href') or '').split('?')[0]
    if asset in ['assets/policy-evaluation.js','assets/policy-evaluation.css','assets/policy-evaluation-data.js','assets/g1_scratch-evaluation-data.js']:
        script.decompose()
section.append(BeautifulSoup(html, 'html.parser'))
panel = section.select_one('#spot-curriculum')
controls.append(panel.select_one('.loco-metrics').extract())
panel.insert(0, controls)
for link in soup.select('#page-contents a[href="#controller-pretraining"]'):
    link.string = 'Learning Low-Level Policy'
for link in soup.select('#page-contents a[href="#spot-curriculum"]'):
    link.parent.decompose()
if not soup.select_one('script[src^="assets/spot-curriculum.js"]'):
    soup.head.append(soup.new_tag('script', src='assets/spot-curriculum.js', defer=''))
path.write_text(str(soup).rstrip() + '\n')
