"""Attach the new continuous Spot curriculum without relabeling old evidence."""
from pathlib import Path
from bs4 import BeautifulSoup

root = Path(__file__).resolve().parents[1]
path = root / 'index.html'
soup = BeautifulSoup(path.read_text(), 'html.parser')
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
html = f'''<div id="spot-curriculum" hidden>
<p class="method-small-copy" data-curriculum-intro>A new PPO training run starts from random initialization.</p>
<p class="scratch-status" data-curriculum-status role="status">Training progress loads nearby.</p>
<div class="loco-row scratch-layout">
<div class="loco-rollout">
<div data-curriculum-view></div>
<div class="scratch-description">
<p data-curriculum-caption>Initialization · 0 cumulative PPO updates</p>
<p>All replays use the same terrain bank, initial conditions and camera. The policy mean is evaluated without exploration noise. Replay time starts before the first action.</p>
<p>Arm adaptation trains the leg policy to maintain balance as commanded arm postures change. It does not train a manipulation policy. Spot has no arm in its physical model. Spot + arm keeps the arm throughout its own training, and evaluates changing arm commands during arm adaptation.</p>
</div></div>
<div class="loco-evidence">
<div class="loco-metrics" role="group" aria-label="Training metrics">{controls}</div>
<p class="loco-evidence-note curriculum-baseline-note">Update 0 is the saved initial policy. Loss logging begins with PPO update 1. Horizontal dashed lines mark each metric’s first recorded value.</p>
<div class="scratch-curves" data-curriculum-curves></div>
<div class="loco-phases" data-curriculum-phases aria-label="Training stages"></div>
<p class="loco-evidence-note">Numbered markers on the first plot select saved checkpoint replays. Shaded brackets show training phases. Unreached phases contain no curve.</p>
<p class="loco-status" data-curriculum-readout aria-live="polite"></p>
</div></div></div>'''
section = soup.select_one('#controller-pretraining')
section.select_one('#pretraining-title').string = 'Learning Low-Level Policy'
section.select_one(':scope > .method-small-copy').string = 'Select a robot to inspect its learning progress, training stages and checkpoint replays.'
archive = section.select_one('[data-policy-recorded]')
if archive is None:
    controls = soup.new_tag('div', attrs={'class':'policy-controls'})
    controls.append(section.select_one('.loco-bodies').extract())
    controls.append(BeautifulSoup('<div class="policy-sources" role="group" aria-label="Training record" hidden><button type="button" data-loco-source="new" aria-pressed="true">New training</button><button type="button" data-loco-source="recorded" aria-pressed="false">Recorded controller</button></div>', 'html.parser'))
    archive = soup.new_tag('div', attrs={'data-policy-recorded':''})
    for child in list(section.children):
        if getattr(child, 'name', None) and child.get('id') != 'pretraining-title' and 'method-small-copy' not in child.get('class', []):
            archive.append(child.extract())
    section.append(controls)
    section.append(archive)
archive.insert_before(BeautifulSoup(html, 'html.parser'))
for link in soup.select('#page-contents a[href="#controller-pretraining"]'):
    link.string = 'Learning Low-Level Policy'
for link in soup.select('#page-contents a[href="#spot-curriculum"]'):
    link.parent.decompose()
if not soup.select_one('script[src^="assets/spot-curriculum.js"]'):
    soup.head.append(soup.new_tag('script', src='assets/spot-curriculum.js', defer=''))
path.write_text(str(soup).rstrip() + '\n')
# Keep the evaluation panel outside both source-specific replay containers.
import subprocess, sys
subprocess.run([sys.executable, str(root / 'scripts/build_policy_evaluation.py')], check=True)
