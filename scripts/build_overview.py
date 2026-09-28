"""A compact, interactive overview of CLEAR's actual computation graph."""
from pathlib import Path
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1]
content='''<section id="clear-overview" class="clear-overview" data-active="grounding" aria-label="CLEAR architecture overview">
<h3>From the body to a plan.</h3>
<p class="overview-intro">Robot structure and scene geometry determine which interactions can achieve the goal.</p>
<div class="overview-flow">
<svg class="overview-wires" aria-hidden="true"><defs><marker id="overview-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z"/></marker></defs><g class="overview-edges"></g></svg>
<div class="overview-column overview-inputs"><span class="overview-category">Observed inputs</span><div id="overview-inputs"><div>Robot structure <small>Morphology encoder</small></div><div>Object states <small>Object encoder</small></div><div>Scene geometry <small>Scene encoder</small></div></div></div>
<div class="overview-column"><span class="overview-category">Affordance guided encoding</span><div class="overview-node" id="overview-grounding">Planning context <span>H</span><small>Capabilities and accessibility</small></div></div>
<div class="overview-column"><span class="overview-category">OrderNet</span><div class="overview-node" id="overview-ordering">Select and order <span>ρ</span><small>Objects and interaction ranks</small></div></div>
<div class="overview-column"><span class="overview-category">CausalFlowNet</span><div class="overview-node" id="overview-generation">Generate motion <span>Y</span><small>Rank causal object targets</small></div></div>
<div class="overview-column"><span class="overview-category">Execution</span><div class="overview-node" id="overview-execution">Validate and execute <span>→</span><small>Update the observation</small></div></div>
</div>
<div class="overview-stages" role="group" aria-label="Explore the architecture"><button type="button" data-overview-stage="grounding" aria-pressed="true">Grounding</button><button type="button" data-overview-stage="ordering" aria-pressed="false">Ordering</button><button type="button" data-overview-stage="generation" aria-pressed="false">Generation</button><button type="button" data-overview-stage="execution" aria-pressed="false">Execution</button></div>
<div class="overview-explanation" aria-live="polite" aria-atomic="true"><strong>Ground the scene in the robot’s body.</strong><p>Structure, object states, and scene geometry form a planning context that represents the robot’s capabilities and accessible interactions.</p><a href="#method-grounding">Explore grounding</a></div>
</section>'''
soup=BeautifulSoup((root/'index.html').read_text(),'html.parser');old=soup.find(id='clear-overview')
if old:old.decompose()
pipeline=soup.select_one('#method > figure.pipeline')
if pipeline:
 details=soup.new_tag('details',attrs={'class':'overview-paper-figure'})
 summary=soup.new_tag('summary');summary.string='View the paper diagram';details.append(summary)
 pipeline.replace_with(details);details.append(pipeline)
heading=soup.select_one('#method>.section-heading');heading.insert_after(BeautifulSoup(content,'html.parser'))
if not soup.find('script',src='assets/overview.js'):soup.head.append(soup.new_tag('script',attrs={'src':'assets/overview.js','defer':''}))
(root/'index.html').write_text(str(soup).rstrip()+'\n')
