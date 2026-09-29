"""Keep essential method sections visible, with stable hierarchical deep links."""
from pathlib import Path
from bs4 import BeautifulSoup
root = Path(__file__).resolve().parents[1]
p = root / 'index.html'
s = BeautifulSoup(p.read_text(), 'html.parser')

# The main reading path is visible by default. Deep links keep stable IDs.
for d in s.select('details'):
    d.name = 'section' if d.get('id') or 'reading-detail' in d.get('class', []) else 'div'
    d.attrs.pop('open', None)
    title = d.find('summary', recursive=False)
    if title:
        title.name = 'h4' if 'reading-detail' in d.get('class', []) else 'h5'
        if title.get_text(strip=True) == 'Read the abstract +': title.string = 'Abstract'
        if title.get_text(strip=True) == 'View the paper diagram': title.string = 'Architecture in the paper'

def subsection(node, title, identity):
    old = s.select_one('#' + identity)
    if old:
        if node.parent is not old:
            old.append(node.extract())
        return old
    section = s.new_tag('section', attrs={'class': 'reading-detail', 'id': identity})
    heading = s.new_tag('h4'); heading.string = title; section.append(heading)
    node.insert_before(section); section.append(node.extract())
    return section

for key, title in [('grounding', 'Dataset, representation and supervision'), ('ordering', 'Dataset and reference interactions')]:
    node = s.select_one('#learning-' + key)
    if node:
        section = subsection(node, title, key + '-samples')
        section.select_one('h4').string = title
        heading = node.find('h4', recursive=False)
        if heading: heading.name = 'h5'

mesh = s.select_one('#embodiment-demo')
if mesh: subsection(mesh, 'Inspect embodiment mesh and interaction highlights', 'grounding-mesh')
formulation = s.select_one('#grounding-formulation')
samples = s.select_one('#grounding-samples')
if formulation and samples:
    for child in list(formulation.find_all(recursive=False)):
        if child.name not in ['h4', 'summary']: samples.append(child.extract())
    formulation.decompose()
# Builders can also supply the representation without a wrapper.
for selector in ['#method-grounding > .method-with-notation', '#method-grounding > .method-loss', '#method-grounding > .training-loss-jump', '#method-grounding > .method-details']:
    node = s.select_one(selector)
    if node and samples: samples.append(node.extract())
layout = s.select_one('.maze-order-layout')
if layout:
    context = subsection(layout, 'From scene context to an interaction order', 'ordering-context')
    for node in list(s.select('#method-order > .method-details')): context.append(node.extract())
# The concise encoder and BCE equations already appear beside the dataset.
# Retain the concrete input definition without repeating equations and pseudocode.
detail = s.select_one('#grounding-samples > .method-details')
if detail:
    for node in list(detail.find_all(recursive=False)):
        if node.name != 'div' or 'feature-columns' not in node.get('class', []): node.decompose()
    detail['class'] = 'grounding-input-definition'
for node in s.select('#ordering-context .method-code'): node.decompose()
for node in s.select('#ordering-context > .method-details > h5'):
    node.string = 'Selection and ordering supervision'
node = s.select_one('#mpc-process')
if node: subsection(node, 'Controller trajectories and palm contact', 'controller-trajectories')
for key in ['grid', 'manipulation', 'maze', 'horizon']:
    article = s.select_one('#experiment-' + key)
    if article and not article.select_one('#experiment-' + key + '-replays'):
        nodes = [c for c in article.find_all(recursive=False) if c.name != 'h3' and 'experiment-claim' not in c.get('class', [])]
        section = subsection(nodes[0], 'Recorded comparisons', 'experiment-' + key + '-replays')
        for node in nodes[1:]: section.append(node.extract())
for title in s.select('.abstract > h5'): title.string = 'Abstract'
for title in s.select('.overview-paper-figure > h5'): title.string = 'Architecture in the paper'
for video in s.select('video[autoplay]'): video.attrs.pop('autoplay', None)
for node in s.select('.method-nav, #page-contents, #contents-toggle'):
    node.decompose()
items = [
 ('tldr', 'Overview', [('motivation', 'Motivation', [])]),
 ('encoding', 'Embodiment encoding', []),
 ('method', 'Method', [
  ('clear-overview', 'Architecture', []),
  ('method-grounding', 'Grounding', [('controller-pretraining', 'Learning to move', []), ('grounding-mesh', 'Body and interaction', []), ('grounding-samples', 'Dataset and supervision', [])]),
  ('method-order', 'Interaction ordering', [('ordering-samples', 'Reference interactions', []), ('ordering-context', 'Context and sampling', [])]),
  ('method-flow', 'Motion generation', [('training-objective', 'Training objective', [])]),
  ('method-execution', 'Execution', [('controller-trajectories', 'Controller trajectories', [])])]),
 ('experiments', 'Experiments', [(f'experiment-{key}', title, []) for key, title in [('grid', '2D grid'), ('manipulation', 'Manipulation'), ('maze', 'Maze navigation'), ('horizon', 'Long horizon')]])]

def entries(items, depth=1):
    result = '<ol>'
    for key, label, children in items:
        # Pretraining is added by its own builder when its recorded assets are ready.
        if not s.select_one('#' + key):
            continue
        result += f'<li data-depth="{depth}"><a href="#{key}">{label}</a>'
        if children:
            result += entries(children, depth + 1)
        result += '</li>'
    return result + '</ol>'
nav = BeautifulSoup('<button id="contents-toggle" type="button" aria-controls="page-contents" aria-expanded="false">Contents</button><nav id="page-contents" aria-label="Contents"><div class="contents-heading">Contents</div>' + entries(items) + '<a class="contents-top" href="#top">Back to top ↑</a></nav>', 'html.parser')
s.body.append(nav)
for name in ['page-structure.css', 'page-structure.js']:
    path = 'assets/' + name
    if not any((e.get('src') or e.get('href') or '').split('?')[0] == path for e in s.select('script[src],link[href]')):
        s.head.append(s.new_tag('link', rel='stylesheet', href=path) if name.endswith('css') else s.new_tag('script', src=path, defer=''))
p.write_text(str(s).rstrip() + '\n')
