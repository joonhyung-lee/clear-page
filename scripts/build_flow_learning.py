"""Pair a teaser map with its native replay on one shared generation timeline."""
from pathlib import Path
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1];path=root/'index.html'
s=BeautifulSoup(path.read_text(),'html.parser');part=s.select_one('#method-flow')
for old in list(part.select(':scope > #flow-learning, :scope > .maze-flow-controls, :scope > .maze-flow-viewer, :scope > .generation-progress, :scope > .figure-caption')):
    old.decompose()
html='''<section id="flow-learning" class="reading-detail" aria-labelledby="flow-learning-title">
<h4 id="flow-learning-title">Generate and inspect an object sequence</h4>
<p class="method-small-copy">The map and 3D view show the same raw checkpoint predictions in the teaser environment. A supplied example order conditions the flow head. This transfer attempt does not produce a feasible plan.</p>
<p class="flow-diagnostic method-small-copy" id="flow-diagnostic" role="status"></p>
<div class="control-row flow-pair-controls"><label>Noise draw <select id="maze-flow-sample"><option value="0">1</option><option value="1">2</option><option value="2">3</option><option value="3">4</option></select></label><span class="flow-sequence" aria-label="Supplied interaction order"></span></div>
<div class="flow-pair"><figure class="flow-map-figure"><figcaption>Teaser map · shared waypoints</figcaption><canvas id="teaser-flow-map" tabindex="0" role="img" aria-label="Teaser scene with generated object waypoints. Arrow keys seek the shared timeline."></canvas><div class="flow-map-tooltip" hidden></div></figure><div class="viewer maze-method-viewer maze-flow-viewer" data-generation="true" data-external-timeline="true" data-scene="teaser-flow-0" data-title="Teaser object sequence"><img class="preview-image" src="assets/media/method-order-maze.png" alt="The same teaser environment in 3D" loading="lazy"/><button class="launch" type="button">Play in 3D</button></div></div>
<div class="generation-progress"><button id="flow-play" type="button">Play</button><button id="flow-replay" type="button">Replay</button><input type="range" id="flow-progress" min="0" max="16" step="0.0333333333" value="0" aria-label="Shared generation and sequence timeline"/><output id="flow-time">Flow t = 0.00</output></div>
<p class="figure-caption" id="maze-flow-caption" aria-live="polite">Loading the recorded flow prediction.</p>
<p class="figure-caption">Circles mark box-center waypoints. Two translucent corner outlines show the intermediate and final poses. Hover a waypoint on the map to inspect its coordinates. The generated paths are predictions, not a physical execution.</p>
</section>'''
part.select_one(':scope > .method-small-copy').insert_after(BeautifulSoup(html,'html.parser'))
if not any((n.get('src') or '').split('?')[0]=='assets/flow-learning.js' for n in s.select('script[src]')):
    s.head.append(s.new_tag('script',src='assets/flow-learning.js',defer=''))
path.write_text(str(s).rstrip()+'\n')
