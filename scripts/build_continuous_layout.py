"""Expose the research story with fewer gates while retaining recorded evidence."""
from pathlib import Path
from bs4 import BeautifulSoup
import json
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'index.html';s=BeautifulSoup(p.read_text(),'html.parser')
def frag(html):return BeautifulSoup(html,'html.parser')
def unwrap_details(node):
 d=node.find_parent('details')
 if d:
  d.select_one(':scope > summary').decompose();d.unwrap()
def ego_view(scene,title):
 return frag(f'''<figure class="execution-record"><figcaption>{title}</figcaption><div class="viewer execution-body-viewer" data-scene="{scene}" data-ego="true" data-generation="true" data-title="{title}"><video class="preview-video" data-autoplay muted loop playsinline preload="none" poster="assets/media/{scene}.png"><source src="assets/media/{scene}.mp4" type="video/mp4"></video><div class="ego-inset"><span>Ego RGB</span><video muted playsinline preload="none" src="assets/media/{scene}-ego.mp4"></video></div><button class="launch" type="button">Inspect in 3D</button></div><p class="record-scope">Recorded simulation · Palm anchors follow the saved contact geometry in 3D.</p></figure>''').figure
# Keep stable hashes while simplifying the visible names.
s.select_one('.research-links a[href="#results"]').string='Experiment'
s.select_one('#experiments .section-heading h2').string='Experiment'
# One row of category widgets, directly above the corresponding pipeline nodes.
stages=s.select_one('.overview-stages')
if stages:
 for button in list(stages.select('[data-overview-stage]')):
  stage=button['data-overview-stage'];column=s.select_one('#overview-'+stage).parent
  column.insert(0,button.extract())
 stages.decompose()
for column in s.select('.overview-column'):
 if column.select_one('[data-overview-stage]') and column.select_one('.overview-category'):column.select_one('.overview-category')['class']=['overview-model-name']
# Associate the original diagram directly, without another accordion.
figure=s.select_one('.overview-paper-figure')
if figure and figure.find_parent('details'):
 d=figure.find_parent('details');d.replace_with(frag('''<button class="paper-figure-link" data-paper-figure type="button"><img src="assets/pipeline-anonymous.png" alt="Paper architecture figure" loading="lazy"><span>Architecture in the paper ↗</span></button>'''))
# Three neighboring grounding columns, with all four bodies visible together.
ground=s.select_one('#method-grounding')
if not s.select_one('.grounding-columns'):
 columns=s.new_tag('div',attrs={'class':'grounding-columns'});ground.append(columns)
 demo=s.select_one('#embodiment-demo');demo.select_one('.grounding-bodies').decompose()
 for f in demo.select('.embodiment-gallery>figure'):f.attrs.pop('hidden',None)
 encoding=s.select_one('#encoding');unwrap_details(encoding)
 affordance=encoding.select_one('.affordances');unwrap_details(affordance)
 for node in [demo,encoding,affordance]:columns.append(node.extract())
 for v in demo.select('.viewer'):v['data-autostart']=''
# Ordering and generation share a scene and a single horizontal reading row.
if not s.select_one('.planning-pair'):
 pair=s.new_tag('div',attrs={'class':'planning-pair'});order=s.select_one('#method-order');order.insert_before(pair)
 for id in ['method-order','method-flow']:pair.append(s.select_one('#'+id).extract())
# The controller's body and the very same recorded palm traces are neighbors.
execution=s.select_one('#method-execution')
detail=execution.select_one(':scope > details')
if detail:detail['open']=''
if not s.select_one('.execution-pair'):
 pair=s.new_tag('div',attrs={'class':'execution-pair'});left=s.new_tag('div',attrs={'class':'execution-bodies'})
 left.append(ego_view('mpc-optimized','MPC w/ optimization (ours)'))
 left.append(ego_view('mpc-baseline-push','MPC (naive)'))
 pair.append(left);pair.append(s.select_one('#controller-trajectories').extract())
 execution.select_one('.execution-preview').replace_with(pair)
 s.select_one('#controller-trajectories > h4').decompose()
 s.select_one('#mpc-process > h4').string='Palm trajectories'
# Important samples and training curves are visible on entry.
for node in [s.select_one('[data-sample-panels]'),s.select_one('#training-losses .loss-content'),s.select_one('#controller-pretraining')]:
 unwrap_details(node)
summary=s.select_one('#learning-policy-summary')
if summary:summary.decompose()
for link in s.select('.chapter-links a[href="#controller-pretraining"]'):link.string='Policy training'
s.select_one('#pretraining-title').name='h3'
supervision=s.select_one('.supervision-map')
if supervision:
 supervision['class']=['experiment-supervision'];s.select_one('#experiments .section-heading').insert_after(supervision.extract())
if not s.select_one('.learning-pair'):
 pair=s.new_tag('div',attrs={'class':'learning-pair'});data=s.select_one('#learning-data');data.insert_before(pair)
 pair.append(data.extract());pair.append(s.select_one('#learning-planner').extract())
# Replays with recorded motion start as they enter the page. No-plan scenes stay
# visibly static; never invent motion for an absent execution.
maze={r['scene']:r for r in json.loads((ROOT/'assets/maze-experiments.json').read_text())}
grid={r['scene']:r for r in json.loads((ROOT/'assets/grid-experiments.json').read_text())}
for viewer in s.select('.experiment-viewer'):
 key=viewer['data-scene'];r=maze.get(key,grid.get(key,{}));moving=r.get('replay',r.get('frames',2)>1)
 if moving:viewer['data-autostart']='';viewer['data-generation']='true'
 else:viewer['data-no-execution']='true'
# Failure outcomes are visible before any inspection. Examples are observations,
# not speculative explanations or invented successful counterfactuals.
failure=s.select_one('#failure-cases')
if not failure.select_one('.failure-gallery'):
 gallery=frag('''<div class="failure-gallery"><article class="failure-example" data-failure-example="planning"><h4>No valid plan</h4><div class="failure-visual"><img src="assets/media/maze-e03-highmass-g1-cdgs.png" alt="Initial G1 navigation scene without an execution recording" loading="lazy"><span class="failure-status">FAILED · No execution</span></div><p>CDGS returns no valid plan for this navigation query. Only the initial scene is recorded.</p></article><article class="failure-example" data-failure-example="execution"><h4>Contact lost before the goal</h4><div class="failure-visual"><video controls muted loop playsinline data-autoplay preload="none" poster="assets/media/mpc-baseline.png"><source src="assets/media/mpc-baseline.mp4" type="video/mp4"></video><span class="failure-status">FAILED · Goal not reached</span><output class="failure-event">Contact lost at 14.14 s</output></div><p>G1 naive MPC moves the box 0.70 m, leaving 1.33 m of goal error. Contact is lost at 14.14 s. The box is stationary from 15 s onward while the robot continues moving.</p></article><article class="failure-example" data-failure-example="transfer"><h4>Generated references fail clearance</h4><div class="failure-visual"><canvas data-failure-map aria-label="Actual teaser prediction with obstacle intersections highlighted"></canvas><span class="failure-status">FAILED · Prediction only</span></div><p>OrderNet selects no objects. Supplying the reference order still produces an infeasible path. Red segments mark geometric overlap with obstacles. No execution took place.</p></article></div>''').div
 failure.select_one('h3').insert_after(gallery)
 for para in list(failure.select(':scope > p')):para.decompose()
for h in s.select('.experiment > .reading-detail > h4'):
 if h.get_text(strip=True)=='Recorded comparison':h.decompose()
for name in ['continuous-layout.css','continuous-layout.js','failure-map.js']:
 if not any((e.get('src')or e.get('href')or'').split('?')[0]=='assets/'+name for e in s.select('script[src],link[href]')):
  s.head.append(s.new_tag('link',rel='stylesheet',href='assets/'+name) if name.endswith('.css') else s.new_tag('script',src='assets/'+name,defer=''))
# Keep the controls above both views and align corresponding controller rows.
s.body['data-reading-layout']='continuous'
for v in s.select('.affordances video'):v['data-autoplay']=''
old=s.select_one('#grounding-mesh')
if old and not old.select_one('.viewer'):old.decompose()
demo=s.select_one('#embodiment-demo')
if not demo.select_one('h4'):demo.insert(0,frag('<h4>Embodiment mesh</h4>').h4)
rule=s.select_one('#ordering-rule')
if rule: s.select_one('#method-order .sequence-explanation').insert_after(rule.extract())
process=s.select_one('#mpc-process')
if not s.select_one('.mpc-playback-speed'):s.select_one('#mpc-process-counter').insert_after(frag('<span class="mpc-playback-speed">2× replay</span>'))
if not s.select_one('.execution-process-grid'):
 grid=s.new_tag('div',attrs={'class':'execution-process-grid'})
 content=process.select_one('.mpc-process-content');content.append(grid)
 grid.append(s.select_one('.execution-bodies').extract());grid.append(process.select_one('.mpc-process-pair').extract())
for viewer in s.select('.execution-body-viewer'):
 scene=viewer['data-scene']
 if scene=='mpc-baseline-push':
  viewer['data-scene']='mpc-baseline';scene='mpc-baseline'
  viewer.select_one('.preview-video')['poster']='assets/media/'+scene+'.png'
  viewer.select_one('.preview-video source')['src']='assets/media/'+scene+'.mp4'
 main=viewer.select_one('.preview-video');main.attrs.pop('data-autoplay',None);main.attrs.pop('loop',None)
 viewer['data-execution-clock']='optimized' if scene=='mpc-optimized' else 'baseline'
 viewer['data-external-timeline']='true'
 ego=viewer.select_one('.ego-inset video');ego['poster']='assets/media/'+scene+'-ego.png';ego['src']='assets/media/'+scene+'-ego.mp4'
 viewer.find_next_sibling('p')['class']=['record-scope']
 viewer.find_next_sibling('p').string='Recorded simulation · Paired palm anchors and forecasts from the saved controller states.'
 if not viewer.select_one('.execution-clock-note'):viewer.append(frag('<output class="execution-clock-note"></output>'))
# Side views contain the exact saved palm markers and candidate paths.
for v in s.select('.execution-body-viewer,.media-tile[data-scene]'):
 scene=v.get('data-scene','');contact=scene+'-contact'
 if (ROOT/'assets/media'/f'{contact}.mp4').exists():
  video=v.select_one('video');source=video.select_one('source');source['src']='assets/media/'+contact+'.mp4'
  video['poster']='assets/media/'+contact+'.png';v['data-contact-side']='true'
fv=s.select_one('[data-failure-example="execution"] video')
fv['poster']='assets/media/mpc-contact-lost.png';fv.select_one('source')['src']='assets/media/mpc-baseline-contact.mp4'
# Compact reading density without replacing recorded evidence or interactions.
for inset in s.select('.ego-inset'):
 inset['title']='Rendered robot camera, synchronized with the recorded motion'
s.select_one('.research-links a[href="#learning"]').string='Training'
s.select_one('#learning > .section-heading h2').string='Training'
s.select_one('#learning .chapter-links')['aria-label']='Training sections'
s.select_one('#learning .chapter-links a[href="#learning-data"]').string='Training samples'
s.select_one('#learning-planner > h3').string='The full training objective'
intro=s.select_one('#learning-planner > p')
if intro:intro.decompose()
lead=s.select_one('#learning > .chapter-lead')
if lead:lead.decompose()
for id,copy in [('method-order','Select blocking objects and sample their interaction order.'),('method-flow','Generate each object reference conditioned on earlier interactions.')]:
 section=s.select_one('#'+id);section.select_one('.method-lead').string=copy
 for e in list(section.select(':scope > .method-small-copy,:scope > .training-loss-jump')):e.decompose()
rule=s.select_one('#ordering-rule p')
if rule:rule.decompose()
if not s.select_one('.planning-scope'):
 s.select_one('.planning-pair').insert_after(frag('<p class="planning-scope">Illustrative example, not a model prediction.</p>'))
data=s.select_one('#learning-data');data.select_one(':scope > h3').string='Training samples'
data.select_one(':scope > p').string='Select a sample to compare its representation, recorded outcome and trajectory.'
for id in ['grounding-samples','ordering-samples']:
 panel=s.select_one('#'+id)
 for e in list(panel.select(':scope > h4,:scope > .training-loss-jump')):e.decompose()
 explorer=panel.select_one('.learning-explorer')
 for e in list(explorer.select(':scope > h5,:scope > .method-small-copy,:scope > .learning-dataflow')):e.decompose()
 loss=explorer.select_one(':scope > .method-loss')
 if loss:
  detail=s.new_tag('details',attrs={'class':'research-details sample-supervision'})
  detail.append(frag('<summary>Affordance supervision</summary>'))
  loss.select_one('h4').decompose();detail.append(loss.extract());s.select_one('#learning-planner').append(detail)
 representation=panel.select_one('.research-representations')
 if representation.name=='details':
  representation.name='section';representation.attrs.pop('open',None)
  heading=representation.select_one('summary');heading.name='h5';heading.string='Representation'
 for e in list(representation.select('figcaption')):e.decompose()

# Finish the method's visual hierarchy without changing the underlying examples.
columns=s.select_one('.grounding-columns')
encoding=s.select_one('#encoding');columns.insert(0,encoding.extract())
s.select_one('#embodiment-demo>h4').string='Robot embodiment'
# Keep the four robot viewers in one place; the neighboring input panel is
# dedicated to objects and scene geometry.
encoding.select_one('.section-heading h2').string='Objects and scene'
robot_link=s.select_one('.overview-input-links a[href="#input-structure"]')
if robot_link:robot_link['href']='#embodiment-demo'
for duplicate in list(encoding.select('[data-input-panel="structure"],#input-structure')):
 duplicate.decompose()
for button in encoding.select('[data-input-panel]'):
 button['aria-pressed']='true' if button['data-input-panel']=='objects' else 'false'
for panel in encoding.select('[data-input-content]'):
 if panel['data-input-content']=='objects':panel.attrs.pop('hidden',None)
 else:panel['hidden']=''
encoding.select_one('.section-intro').string='Object poses and scene geometry combine with the robot embodiment to define the planning context.'
controller_notes={r['scene']:r['note'] for r in json.loads((ROOT/'assets/controller-gallery.json').read_text())}
for tile in s.select('.pushing-gallery .media-tile[data-scene^="mpc-spot-"]'):
 note='Blue dashed lanes show the intended object path. Teal follows the measured object motion. Rose anchors mark the recorded gripper path, with a 0.8 s live trail. Both clips show the extended arm during pushing.'
 tile['data-note']=controller_notes[tile['data-scene']]+' '+note
 tile['title']=note
gallery=s.select_one('#method-execution .pushing-gallery')
for old in s.select('.pushing-motion-legend'):old.decompose()
gallery.insert_after(frag('''<p class="pushing-motion-legend"><span>Spot overlays</span><span><i class="object-target"></i>Object target</span><span><i class="object-motion"></i>Object motion</span><span><i class="eef-motion"></i>EEF · recent 0.8 s</span></p>'''))
s.select_one('.embodiment-controls')['class']=['embodiment-controls','structure-branches']
for node in list(s.select('.planning-scope')):node.decompose()
for id in ['method-order','method-flow']:
 section=s.select_one('#'+id);figure=section.select_one('.sequence-explanation')
 for node in list(figure.select('p')):node.decompose()
 lead=section.select_one('.method-lead');section.append(lead.extract())
 if id=='method-flow' and not section.select_one('#generation-rule'):
  formula=s.new_tag('div',attrs={'id':'generation-rule'})
  eq=s.new_tag('div',attrs={'class':'equation','data-tex':r'\dot{\mathbf{x}}_{\rho_k}(t)=v_\theta\!\left(\mathbf{x}_{\rho_{\leq k}}(t),t,H\right)'})
  formula.append(eq);lead.insert_before(formula)
# The execution introduction uses its full available reading row.
section=s.select_one('#method-execution')
section.select_one(':scope > .method-lead').string='The controller tracks object targets and updates its commands from new observations. High-level replanning revises the remaining interactions.'
for para in list(section.select(':scope > p:not(.method-lead):not(.method-small-copy):not(.figure-caption):not(.pushing-motion-legend)')):para.decompose()

# Use the manuscript's component names and notation throughout the Method.
components=[
 ('a','grounding','method-grounding','Embodiment-Aware Scene Grounding','Grounding'),
 ('b','ordering','method-order','Latent Interaction Ordering','Selection and ordering'),
 ('c','generation','method-flow','Rank-Causal Generation','Generation'),
 ('d','execution','method-execution','Execution and Replanning','Execution and replanning'),
]
for letter,stage,id,title,short in components:
 s.select_one('#'+id+'>h3').string=f'({letter}) {title}'
 s.select_one(f'#method .chapter-links a[href="#{id}"]').string=f'({letter}) {short}'
 button=s.select_one(f'[data-overview-stage="{stage}"]')
 button.string=f'({letter}) '+('Ordering' if stage=='ordering' else short)
 button['aria-label']=f'({letter}) {title}'

def replace_content(node,html):
 node.clear()
 for child in list(frag(html).contents):node.append(child.extract())

replace_content(s.select_one('#clear-overview .overview-intro'),r'''Given a scene <span data-tex="S"></span> and robot embodiment <span data-tex="B"></span>, CLEAR proposes plans <span data-tex="\pi=((i_1,\xi_1),\ldots,(i_K,\xi_K))"></span>. The scene includes the observed geometry, <span data-tex="N"></span> movable objects, the robot state and a task goal. Each plan entry specifies an object and its target configuration or trajectory. Among candidates accepted by the task's feasibility checks, the planner selects one with the fewest object interactions.''')
s.select_one('#overview-grounding').parent.select_one('.overview-model-name').string='Affordance-Guided Encoding'
s.select_one('#overview-generation>span').string='Yₜ'
s.select_one('#overview-generation>small').string='Decode object references ξₖ'
s.select_one('#overview-execution').parent.select_one('.overview-model-name').string='Feasibility check + MPC'
replace_content(s.select_one('#method-grounding>.method-lead'),r'''Affordance-Guided Encoding combines morphology, object and scene features into the planning context <span data-tex="\mathbf H"></span>. Predicted traversal and interaction feasibility augment the object features. Reachability accounts for the terrain transitions needed to approach an object.''')

rule=s.select_one('#ordering-rule');rule.clear()
rule.append(frag(r'''<div class="equation" data-tex="\begin{aligned}m_i&amp;\sim\operatorname{Bernoulli}(q_i),&amp;\mathcal I&amp;=\{i:m_i=1\}\\u_i&amp;\sim\mathcal N(\mu_i,\sigma_i^2),&amp;\boldsymbol\rho&amp;=\operatorname{argsort}_{i\in\mathcal I}u_i\end{aligned}"></div>'''))
rule=s.select_one('#generation-rule');rule.clear()
rule.append(frag(r'''<div class="equation" data-tex="\begin{aligned}\mathbf v_t&amp;=v_\theta(\mathbf Y_t,t\mid\mathbf H,\boldsymbol\rho)\\\mathbf Y_{t+\Delta t}&amp;=\mathbf Y_t+\Delta t\,\mathbf v_t\end{aligned}"></div>'''))
replace_content(s.select_one('#method-order>.method-lead'),r'''From <span data-tex="\mathbf H"></span>, OrderNet predicts a selection probability <span data-tex="q_i"></span> and priority mean and standard deviation <span data-tex="\mu_i,\sigma_i"></span> for each object <span data-tex="o_i"></span>. A sampled indicator <span data-tex="m_i"></span> determines participation. Sorting sampled scores <span data-tex="u_i"></span> from low to high gives the order <span data-tex="\boldsymbol\rho"></span>.''')
replace_content(s.select_one('#method-flow>.method-lead'),r'''With <span data-tex="\mathbf H,\mathcal I,\boldsymbol\rho"></span> fixed, CausalFlowNet integrates from Gaussian noise in the active coordinates of <span data-tex="\mathbf Y_0"></span> to <span data-tex="\mathbf Y_1"></span>. In <span data-tex="\mathbf Y_t\in\mathbb R^{N\times D}"></span>, row <span data-tex="\mathbf y_i(t)"></span> stores <span data-tex="D"></span> coordinates for object <span data-tex="o_i"></span>. Fixed and padding coordinates remain unchanged. The selected rows are decoded in order <span data-tex="\boldsymbol\rho"></span> into references <span data-tex="(\xi_1,\ldots,\xi_K)"></span>. Flow time <span data-tex="t\in[0,1]"></span> describes generation progress, not execution time.''')
explanations={
 'method-order':r'''<p>Sampling admits alternative object sets and orders for the same query. Selection considers the complete sequence, including objects that become reachable after earlier interactions.</p><p class="method-example"><strong>In this scene.</strong> <span data-tex="o_2"></span> blocks the first passage. Moving it creates access to <span data-tex="o_3"></span>. The example order is <span data-tex="\boldsymbol\rho=(2,3)"></span>, while <span data-tex="o_1"></span> remains outside the route.</p>''',
 'method-flow':r'''<p>All selected rows evolve over the same flow interval. Rank causal attention lets each row read its own and preceding ranks. Context tokens cannot read generated rows, preventing later interactions from influencing earlier ones through <span data-tex="\mathbf H"></span>.</p><p class="method-example"><strong>In this scene.</strong> <span data-tex="\xi_1"></span> relocates <span data-tex="o_2"></span> to clear the first passage. <span data-tex="\xi_2"></span> plans the motion of <span data-tex="o_3"></span> with access through that passage. Feasibility is checked after generation.</p>''',
}
for id,html in explanations.items():
 section=s.select_one('#'+id)
 for old in list(section.select(':scope > .method-explanation')):old.decompose()
 section.append(frag('<div class="method-explanation">'+html+'</div>'))
 figure=section.select_one('.sequence-explanation')
 caption=figure.select_one('figcaption');caption['hidden']=''
 caption.string='Selection and ordering in a two-passage scene' if id=='method-order' else 'Object references under the same interaction order'
 figure.select_one('svg')['aria-label']='Example interaction order o₂ followed by o₃'
 for label in figure.select('svg text'):
  if label.get_text() in ['1','2']:label.string={'1':'o₂','2':'o₃'}[label.get_text()]
replace_content(s.select_one('#method-execution>.method-lead'),r'''Decoded references <span data-tex="(\xi_1,\ldots,\xi_K)"></span> are checked in order <span data-tex="\boldsymbol\rho"></span>, accounting for the scene changes caused by earlier interactions. The planner selects a candidate that satisfies the goal with the fewest interactions among those accepted. A valid plan requiring no object interaction bypasses generation. MPC tracks the object references using updated state estimates. When enabled, replanning uses the updated scene to revise the remaining interactions.''')

p.write_text(str(s).rstrip()+'\n')
