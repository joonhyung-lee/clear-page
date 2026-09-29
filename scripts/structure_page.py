"""Keep a short reading path, with deep links into optional interactive detail."""
from pathlib import Path
from bs4 import BeautifulSoup
root = Path(__file__).resolve().parents[1]
p = root / 'index.html'
s = BeautifulSoup(p.read_text(), 'html.parser')

def disclosure(node, title, identity):
    if node.parent.get('id') == identity:
        return node.parent
    old = s.select_one('#' + identity)
    if old:
        old.append(node.extract())
        return old
    d = s.new_tag('details', attrs={'class': 'reading-detail', 'id': identity})
    summary = s.new_tag('summary')
    summary.string = title
    d.append(summary)
    node.insert_before(d)
    d.append(node.extract())
    return d

for key, title in [('grounding', 'Explore grounding samples'), ('ordering', 'Explore selection and ordering samples')]:
    node = s.select_one('#learning-' + key)
    if node:
        disclosure(node, title, key + '-samples')
node = s.select_one('#method-grounding > .method-with-notation')
if node:
    d = disclosure(node, 'Grounding representation and supervision', 'grounding-formulation')
    for selector in ['#method-grounding > .method-loss', '#method-grounding > .training-loss-jump', '#method-grounding > .method-details']:
        child = s.select_one(selector)
        if child:
            d.append(child.extract())
node = s.select_one('#mpc-process')
if node:
    disclosure(node, 'Inspect controller trajectories and palm contact', 'controller-trajectories')
for key in ['grid', 'manipulation', 'maze', 'horizon']:
    article = s.select_one('#experiment-' + key)
    if not article.select_one('#experiment-' + key + '-replays'):
        nodes = [c for c in article.find_all(recursive=False) if c.name != 'h3' and 'experiment-claim' not in c.get('class', [])]
        d = disclosure(nodes[0], 'Explore recorded comparisons', 'experiment-' + key + '-replays')
        for node in nodes[1:]:
            d.append(node.extract())
for node in s.select('.method-nav, #page-contents, #contents-toggle'):
    node.decompose()
items = [
 ('tldr', 'Overview', [('motivation', 'Motivation', [])]),
 ('encoding', 'Embodiment encoding', []),
 ('method', 'Method', [
  ('clear-overview', 'Architecture', []),
  ('method-grounding', 'Grounding', [('controller-pretraining', 'Controller pretraining', []), ('grounding-mesh', 'Body and interaction', []), ('grounding-samples', 'Training samples', []), ('grounding-formulation', 'Representation', [])]),
  ('method-order', 'Interaction ordering', [('ordering-samples', 'Training samples', [])]),
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
