"""Group existing evidence into Method, Learning and Results without copying players."""
from pathlib import Path
import json
import re
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'index.html'
soup = BeautifulSoup(path.read_text(), 'html.parser')

def fragment(html):
    return BeautifulSoup(html, 'html.parser')

def disclosure(title, node):
    detail = soup.new_tag('details', attrs={'class': 'research-details'})
    summary = soup.new_tag('summary'); summary.string = title
    detail.append(summary); detail.append(node.extract())
    return detail

if not soup.select_one('#research-nav'):
    for old in soup.select('#page-contents, #contents-toggle'):
        old.decompose()
    nav = fragment('''<nav id="research-nav" aria-label="Main navigation">
    <a class="research-logo" href="#top" aria-label="CLEAR overview">CLEAR</a>
    <div class="research-links"><a href="#method">Method</a><a href="#learning">Learning</a><a href="#results">Results</a></div>
    <div class="research-resources">
    <button type="button" data-resource="paper" aria-label="Paper" aria-haspopup="dialog"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h6"/></svg><span>Paper</span></button>
    <a href="https://anonymous.4open.science/r/clear-page-1209/" target="_blank" rel="noopener noreferrer" aria-label="Code"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 7-5 5 5 5m8-10 5 5-5 5M14 4l-4 16"/></svg><span>Code</span></a>
    <button type="button" data-resource="video" aria-label="Video" aria-haspopup="dialog"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="m10 8 6 4-6 4z"/></svg><span>Video</span></button>
    </div></nav>''')
    soup.body.insert(0, nav)
    main = soup.select_one('main')
    method = soup.select_one('#method')
    experiments = soup.select_one('#experiments')
    learning = fragment('''<section id="learning" class="section wrap research-chapter"><div class="section-heading"><h2>Learning</h2></div>
    <p class="chapter-lead">Reference plans teach the planner what to move. Separate control policies learn how each body moves.</p>
    <nav class="chapter-links" aria-label="Learning sections"><a href="#learning-data">Data and supervision</a><a href="#learning-planner">Planner training</a><a href="#controller-pretraining">Low-level policy training</a></nav>
    <article id="learning-data"><h3>Data and supervision</h3><p>Reference plans and feasibility labels supervise object participation, interaction order, continuous targets and embodiment-conditioned affordances.</p>
    <details class="research-details"><summary>Explore training samples</summary><div class="sample-tabs" role="group" aria-label="Sample dataset"><button type="button" data-sample-panel="grounding-samples" aria-pressed="true">Feasibility samples</button><button type="button" data-sample-panel="ordering-samples" aria-pressed="false">Reference plans</button></div><div data-sample-panels></div></details></article>
    <article id="learning-planner"><h3>Planner training</h3><p>Selection, ordering and conditional generation share a scene context. Loss terms supervise distinct parts of the plan.</p></article>
    </section>''').section
    experiments.insert_before(learning)
    panels = learning.select_one('[data-sample-panels]')
    for id in ['grounding-samples', 'ordering-samples']:
        panels.append(soup.find(id=id).extract())
    panels.select_one('#ordering-samples')['hidden'] = ''
    learning.select_one('#learning-planner').append(soup.select_one('#training-objective').extract())
    learning.append(disclosure('Inspect low-level policy training', soup.select_one('#controller-pretraining')))
    learning.select_one('#pretraining-title').string = 'Low-level policy training'

    # Inputs remain available in the grounding section, rather than ahead of the method.
    encoding = soup.select_one('#encoding')
    encoding.select_one('h2').string = 'Robot, objects and scene'
    soup.select_one('#method-grounding').append(disclosure('Inspect inputs', encoding))
    paper_figure = soup.select_one('.overview-paper-figure')
    method.select_one('#clear-overview').append(disclosure('View paper figure', paper_figure))
    method.select_one('.section-heading').insert_after(fragment('''<nav class="chapter-links" aria-label="Method sections"><a href="#clear-overview">Pipeline</a><a href="#method-grounding">Grounding</a><a href="#method-order">Selection and ordering</a><a href="#method-flow">Generation</a><a href="#method-execution">Execution and replanning</a></nav>'''))
    for id, title in [('method-grounding','Embodiment-aware grounding'),('method-order','Object selection and ordering'),('method-flow','Rank-causal generation'),('method-execution','Execution and replanning')]:
        soup.find(id=id).select_one('h3').string = title

    results = soup.new_tag('section', id='results', attrs={'class':'research-chapter'})
    experiments.wrap(results)
    experiments.select_one('h2').string = 'Results'
    experiments.select_one('.section-heading').insert_after(fragment('''<nav class="chapter-links" aria-label="Result sections"><a href="#experiment-grid">2D Grid</a><a href="#experiment-manipulation">Ordered Manipulation</a><a href="#experiment-maze">Embodiment-aware navigation</a><a href="#experiment-horizon">Long-horizon replanning</a><a href="#failure-cases">Failure cases</a></nav>'''))
    failures = fragment('''<article id="failure-cases" class="experiment"><h3>Failure cases and limitations</h3>
    <p>The teaser transfer does not produce a valid plan. OrderNet selects no objects, and generation conditioned on a supplied order fails the clearance check. These predictions were not executed.</p>
    <p>Recorded execution can also fail after contact loss. The G1 naive controller replay in <a href="#controller-trajectories">Controller details</a> shows the observed continuation.</p></article>''').article
    experiments.append(failures)
    for id, title in [('ordering-context','Inspect teaser object selection'),('flow-learning','Inspect reference-conditioned generation')]:
        failures.append(disclosure(title, soup.find(id=id)))
    # The method example is explicitly explanatory, not a relabelled failed transfer.
    for id, text in [('method-order','Object 1 → Object 2'),('method-flow','Generate Object 1, then Object 2')]:
        soup.find(id=id).append(fragment(f'''<figure class="sequence-explanation"><figcaption>Illustrative visualization · {text}</figcaption><svg viewBox="0 0 800 210" role="img" aria-label="Illustration of two ordered object interactions"><path d="M30 160H760" stroke="#d6dfd7" stroke-width="2"/><path d="M70 165V65h570v95" fill="none" stroke="#8c9a8f" stroke-dasharray="5 5"/><circle cx="70" cy="165" r="7" fill="#485e51"/><circle cx="640" cy="160" r="9" fill="none" stroke="#485e51" stroke-width="2"/><rect x="240" y="90" width="55" height="55" fill="#d9a88c"/><rect x="450" y="90" width="55" height="55" fill="#9bb6cc"/><path d="M268 117V45M478 117V45" stroke="#667e70" stroke-width="2"/><text x="267" y="125" text-anchor="middle">1</text><text x="478" y="125" text-anchor="middle">2</text><text x="60" y="195">Start</text><text x="625" y="195">Goal</text></svg><p>Two selected objects move in the proposed order. This schematic explains the dependency between interactions and does not show a model prediction.</p></figure>'''))
    execution = soup.select_one('#method-execution')
    details = soup.new_tag('details', attrs={'class':'research-details'})
    summary=soup.new_tag('summary');summary.string='Controller details';details.append(summary)
    for child in list(execution.find_all(recursive=False)):
        if child.name not in ['h3'] and 'method-lead' not in child.get('class',[]):details.append(child.extract())
    execution.append(fragment('''<p>Low-level feedback updates commands along the current reference. High-level replanning revises the remaining interactions from new scene observations.</p><p class="method-small-copy">Validation and replanning depend on the experimental protocol. Grid and Ordered Manipulation omit separate feasibility validation. Maze Navigation comparisons omit high-level replanning.</p>'''))
    execution.append(details)
    motivation=soup.select_one('#motivation')
    motivation.select_one('h2').string='Same scene, different bodies'
    for name in ['research-layout.css', 'research-layout.js', 'method-illustration.js']:
        soup.head.append(soup.new_tag('link',rel='stylesheet',href='assets/'+name) if name.endswith('.css') else soup.new_tag('script',src='assets/'+name,defer=''))
    soup.body.append(fragment('''<dialog id="resource-dialog" aria-labelledby="resource-title"><div class="resource-toolbar"><h2 id="resource-title"></h2><a data-resource-download download>Download</a><button type="button" data-resource-close aria-label="Close preview">×</button></div><div data-resource-content></div></dialog>'''))
if not soup.select_one('[data-grounding-body]'):
    demo=soup.select_one('#embodiment-demo')
    controls=soup.new_tag('div',attrs={'class':'grounding-bodies','role':'group','aria-label':'Grounding robot'})
    for i,(key,label) in enumerate([('g1','G1'),('spot','Spot'),('spot_arm','Spot + arm'),('husky','Husky')]):
        button=soup.new_tag('button',type='button',attrs={'data-grounding-body':key,'aria-pressed':str(i==0).lower()});button.string=label;controls.append(button)
    demo.insert(0,controls)
    for figure in demo.select('.embodiment-gallery>figure')[1:]:figure['hidden']=''
    demo.select_one('[data-embodiment-mode="manipulation"]').string='Interaction feasibility'
for explorer in soup.select('.learning-explorer'):
    scatter=explorer.select_one('.sample-scatter')
    if not scatter.find_parent('details') or 'research-representations' not in scatter.find_parent('details').get('class',[]):
        figure=scatter.parent
        detail=soup.new_tag('details',attrs={'class':'research-details research-representations'})
        summary=soup.new_tag('summary');summary.string='Explore representations';detail.append(summary)
        figure.wrap(detail)
loss=soup.select_one('#training-losses .loss-content')
if not loss.find_parent('details'):
    detail=disclosure('View training curves',loss)
    soup.select_one('#training-losses').append(detail)
data=soup.select_one('#learning-data')
if not data.select_one('.supervision-map'):
    data.select_one('p').insert_after(fragment('''<div class="supervision-map"><dl><dt>2D Grid</dt><dd>Exact-search solutions supervise selection, order and targets.</dd><dt>Ordered Manipulation</dt><dd>Policy demonstrations provide reference interactions and targets.</dd><dt>Maze Navigation</dt><dd>Reference sequences and object trajectories condition plans on the body.</dd><dt>Affordance labels</dt><dd>Interaction and terrain feasibility provide binary targets.</dd></dl></div>'''))
if not soup.select_one('.execution-preview'):
    soup.select_one('#method-execution > details').insert_before(fragment('''<figure class="execution-preview"><video controls playsinline preload="none" poster="assets/media/mpc-optimized.png" aria-label="Recorded G1 object interaction"><source src="assets/media/mpc-optimized.mp4" type="video/mp4"/></video><figcaption>Qualitative replay · Single G1 interaction. This clip illustrates low-level execution. The long-horizon results evaluate high-level replanning separately.</figcaption></figure>'''))
if not soup.select_one('[data-input-panel]'):
    inputs=soup.select_one('#encoding .three-up')
    tabs=soup.new_tag('div',attrs={'class':'input-tabs','role':'group','aria-label':'Observed inputs'})
    for i,(key,label) in enumerate([('structure','Robot structure'),('objects','Object states'),('scene','Scene')]):
        button=soup.new_tag('button',type='button',attrs={'data-input-panel':key,'aria-pressed':str(i==0).lower()});button.string=label;tabs.append(button)
        panel=inputs.find_all('article',recursive=False)[i];panel['data-input-content']=key
        if i:panel['hidden']=''
    inputs.insert_before(tabs)
    definitions=soup.select_one('#encoding .affordances')
    marker=soup.new_tag('span');definitions.insert_before(marker)
    marker.replace_with(disclosure('Accessibility and capability',definitions))

# A small checkpoint comparison precedes the optional, full PPO dashboard.
# Missing final checkpoints remain visibly unavailable rather than borrowing
# a different controller lineage or calling an intermediate policy final.
old=soup.select_one('#learning-policy-summary')
if old:old.decompose()
summary=fragment('''<article id="learning-policy-summary"><h3>Low-level policy training</h3><p>Compare actual checkpoints from each robot’s independent training run, then inspect its losses and fixed-protocol evaluations.</p><div class="policy-summary-bodies" role="group" aria-label="Checkpoint comparison robot"></div><div class="policy-summary-panels"></div><p class="method-small-copy">Recorded simulation · Checkpoint snapshots on the same terrain bank. A completed training budget does not establish successful locomotion. Spot + arm learns balance across arm poses, not a manipulation policy.</p></article>''').article
for i,(body,label) in enumerate([('g1','G1'),('spot','Spot'),('spot_arm','Spot + arm')]):
    source=(ROOT/'assets'/f'{body}-curriculum-data.js').read_text()
    match=re.search(r'window\.CLEAR_BODY_CURRICULA\[.*?\]\s*=\s*(\{.*\});',source)
    data=json.loads(match.group(1))
    button=soup.new_tag('button',type='button',attrs={'data-policy-summary-body':body,'aria-pressed':str(i==0).lower()});button.string=label
    summary.select_one('.policy-summary-bodies').append(button)
    panel=soup.new_tag('div',attrs={'class':'policy-summary-checkpoints','data-policy-summary-panel':body})
    if i:panel['hidden']=''
    available=[s for s in data['stages'] if s.get('replay')]
    initial=next((s for s in available if s['id']=='initialization'),None)
    trained=[s for s in available if s['id']!='initialization']
    middle=trained[max(0,(len(trained)-1)//2)] if trained else None
    final=available[-1] if data.get('complete') and available else None
    for title,stage in [('Initial',initial),('Intermediate',middle),('Final',final)]:
        card=soup.new_tag('button',type='button',attrs={'class':'policy-summary-checkpoint','data-summary-body':body})
        heading=soup.new_tag('strong');heading.string=title;card.append(heading)
        if stage:
            replay=stage['replay'];card['data-summary-stage']=stage['id'];card['data-summary-scene']=replay['scene']
            card['aria-label']=f"Inspect {label} {title.lower()}, update {replay['cumulativeUpdates']:,}"
            card.append(soup.new_tag('img',src=f"assets/media/{replay['scene']}.png",alt=f"{label} at update {replay['cumulativeUpdates']:,}",loading='lazy'))
            text=soup.new_tag('span');text.string=f"Update {replay['cumulativeUpdates']:,}";card.append(text)
        else:
            card['disabled']='';text=soup.new_tag('span',attrs={'class':'policy-checkpoint-pending'});text.string='Not available · Training incomplete';card.append(text)
        panel.append(card)
    summary.select_one('.policy-summary-panels').append(panel)
soup.select_one('#controller-pretraining').find_parent('details').insert_before(summary)
for heading in soup.select('#policy-evaluation h5'):
    heading.decompose()
soup.select_one('#motivation figcaption').string='Illustrative visualization · Different capabilities change the available routes and interactions.'
flow_training=soup.select_one('#method-flow > .method-details')
if flow_training:
    soup.select_one('#learning-planner').append(disclosure('Flow matching and causal conditioning',flow_training))
if not soup.select_one('#ordering-rule'):
    rule=fragment(r'''<div id="ordering-rule"><div class="equation" data-tex="\boldsymbol{\rho}=\operatorname{argsort}_{i\in\mathcal{S}}u_i"></div><p class="method-small-copy">Sort the sampled priority scores of the selected objects. Lower scores execute first.</p></div>''')
    soup.select_one('#method-order .sequence-explanation').insert_before(rule)
if not soup.select_one('[data-failure-kind="planning"]'):
    planning=fragment('''<p data-failure-kind="planning">Planning failure · Some navigation queries return no valid plan and have no execution recording. Their comparison tiles show the initial scene with an explicit no-execution label.</p>''')
    soup.select_one('#failure-cases > p').insert_after(planning)
for panel in soup.select('[data-input-content]'):
    panel['id']='input-'+panel['data-input-content']
if not soup.select_one('.overview-input-links'):
    soup.select_one('#motivation').append(fragment('''<nav class="overview-input-links" aria-label="Explore the planning inputs"><a href="#input-structure"><strong>Robot</strong><span>Links, joints and available motions</span></a><a href="#input-objects"><strong>Objects</strong><span>Poses, geometry and motion references</span></a><a href="#input-scene"><strong>Scene</strong><span>Terrain, obstacles and accessible routes</span></a></nav>'''))
path.write_text(str(soup).rstrip()+'\n')
