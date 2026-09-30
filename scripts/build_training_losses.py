"""Present the original CLEAR objective and its matching interactive loss curves."""
from pathlib import Path
from bs4 import BeautifulSoup
root = Path(__file__).resolve().parents[1]
page = root / 'index.html'
s = BeautifulSoup(page.read_text(), 'html.parser')
objective = s.select_one('.objective')
objective['id'] = 'training-objective'
if objective.parent.name == 'details':
    objective.parent.insert_after(objective.extract())
objective.clear()

formula = r'\mathcal{L}(\theta)=\mathcal{L}_{\mathrm{order}}+\lambda_{\mathrm{flow}}\mathcal{L}_{\mathrm{flow}}+\lambda_{\mathrm{aff}}\mathcal{L}_{\mathrm{aff}}+\lambda_{\mathrm{avail}}\mathcal{L}_{\mathrm{avail}}'

def plot(key, title, copy):
    return f'<figure class="training-loss-chart" id="loss-{key}" data-loss="{key}"><figcaption><h5>{title}</h5><p>{copy}</p></figcaption><canvas role="img" tabindex="0" aria-label="{title}. Use left and right arrows to inspect recorded steps. Home and End select the endpoints."></canvas><div class="loss-tooltip" hidden></div></figure>'

components = ''.join(plot(*p) for p in [
    ('selection', '(a) Selection', 'Object selection BCE'),
    ('order', '(b) Ranking', 'Sampled priority supervision'),
    ('kl', '(c) Regularization', 'Gaussian KL before weighting'),
    ('flow', '(d) Flow', 'Conditional velocity regression'),
    ('affordance', '(e) Affordance', 'Interaction capability BCE')])
html = f'''<h4>The full training objective</h4>
<section id="training-losses" aria-label="Interactive training losses">
<p class="method-small-copy">CLEAR jointly learns object selection, interaction order, conditional targets and embodiment conditioned affordances.</p>
<div class="paper-equation-row"><div class="equation" data-tex="{formula}" data-objective-annotations="true"></div></div>
<p class="loss-scope">The plotted run uses λflow = 1, λKL = 0.001, λaff = 1 and λavail = 0. The availability term is inactive in this run. Hover a curve to inspect its recorded values.</p>
<div class="loss-loading" role="status">Loading recorded losses…</div>
<div class="loss-content" hidden>
{plot('loss', 'Full objective loss', 'Original CLEAR objective · 100,000 training steps')}
<div class="loss-chart-grid" tabindex="0" role="region" aria-label="Five component loss plots, scroll horizontally">{components}</div>
<p class="loss-scope loss-band-note">One training run. The line shows a local mean over 21 logged samples. Shading shows ±1 standard deviation within that window, not variation across seeds. Windows are shortened at the endpoints. Hover or tap to inspect the raw loss and local statistics. Training loss does not measure task performance.</p>
<p class="loss-keyboard-status" aria-live="polite"></p></div></section>'''
objective.append(BeautifulSoup(html, 'html.parser'))
for link in s.select('.training-loss-jump'):
    link.decompose()
for selector, key, label in [
    ('#method-grounding .method-loss', 'affordance', 'Inspect affordance training loss'),
    ('#method-order > .method-small-copy', 'selection', 'Inspect selection and ordering losses'),
    ('#method-flow > .method-small-copy', 'flow', 'Inspect generation training loss')]:
    node = s.select_one(selector)
    if node:
        node.insert_after(BeautifulSoup(f'<p class="training-loss-jump"><a href="#loss-{key}">{label} <span aria-hidden="true">↗</span></a></p>', 'html.parser'))
if not any((x.get('src') or '').split('?')[0] == 'assets/training-losses.js' for x in s.find_all('script')):
    s.body.append(s.new_tag('script', src='assets/training-losses.js'))
page.write_text(str(s).rstrip() + '\n')
