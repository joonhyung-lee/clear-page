"""Keep the method scene-led, with derivations available on demand."""
from pathlib import Path
from bs4 import BeautifulSoup
from html import escape
root=Path(__file__).resolve().parents[1]
soup=BeautifulSoup((root/'index.html').read_text(),'html.parser')
def fragment(text):return BeautifulSoup(text,'html.parser')
def equation(tex):return '<div class="equation" data-tex="'+escape(tex,quote=True)+'"></div>'
for key in ['grounding','order','flow','execution']:
 article=soup.find(id='method-'+key)
 if article.get('data-compact')=='true':continue
 article['data-compact']='true'
 heading=article.find('h3',recursive=False).extract()
 lead=article.select_one('.method-lead').extract()
 retained=[]
 if key=='grounding':
  old=article.find(id='context-demo')
  if old:old.decompose()
 elif key in ['order','flow']:
  retained=[e.extract() for e in article.select('.method-interactive')]
 else:
  retained=[e.extract() for e in article.select('.scenario-control,.mpc-comparison')]
  comparison_caption=article.select_one('.figure-caption')
  if comparison_caption:retained.append(comparison_caption.extract())
 details=soup.new_tag('details',attrs={'class':'method-details'})
 summary=soup.new_tag('summary');summary.string='Equations and implementation';details.append(summary)
 for child in list(article.contents):details.append(child.extract())
 article.append(heading);article.append(lead)
 if key=='grounding':
  article.append(fragment('''<div class="embodiment-gallery" aria-label="Robot embodiments">'''+''.join(f'''<figure><div class="viewer embodiment-viewer" data-scene="structure-{name}" data-title="{label}"><video muted playsinline loop preload="none" poster="assets/media/structure-{name}.png"><source src="assets/media/structure-{name}.mp4" type="video/mp4"></video><button class="launch" type="button">Inspect in 3D</button></div><figcaption>{label}</figcaption></figure>''' for name,label in [('g1','G1'),('spot','Spot'),('spot_arm','Spot + arm'),('husky','Husky')])+'''</div>'''))
  article.append(fragment('''<div class="method-with-notation"><div><div class="feature-columns">'''+''.join('<div><h4>'+title+'</h4>'+equation(tex)+'<p>'+copy+'</p></div>' for title,tex,copy in [
   ('Morphology',r'\mathbf z_B=\operatorname{Pool}_{\ell}\phi_B(\mathbf b_\ell)','Link geometry, joints, and actuation describe the body.'),
   ('Object',r'\mathbf h_i=\phi_O(\mathbf o_i)+\phi_N(\mathbf n_i)','Object state is augmented with affordance and accessibility.'),
   ('Scene',r'\mathbf Z_S=\phi_S(S)','Geometry describes obstacles, surfaces, and routes.')])+'''</div>'''+equation(r'\mathbf H=\operatorname{Transformer}([\mathbf z_B,\{\mathbf h_i\},\mathbf Z_S])')+'''<p class="method-small-copy">A shared planning context conditions both object ordering and motion generation.</p></div><aside class="method-notation" aria-label="Notation"><h4>Notation</h4><dl><dt>B</dt><dd>Robot body</dd><dt>oᵢ</dt><dd>Object state</dd><dt>nᵢ</dt><dd>Affordance and accessibility</dd><dt>S</dt><dd>Scene geometry</dd><dt>H</dt><dd>Planning context</dd><dt>ρ</dt><dd>Interaction order</dd><dt>Y</dt><dd>Generated targets</dd><dt>φ</dt><dd>Learned encoder</dd><dt>ℓ</dt><dd>Link index</dd><dt>b</dt><dd>Binary affordance labels</dd></dl></aside></div>'''))
  article.append(fragment('<div class="method-loss"><h4>Affordance supervision</h4>'+equation(r'\mathcal L_{\mathrm{aff}}=\operatorname{BCE}(\hat{\mathbf p}_{\mathrm{aff}},\mathbf b)')+'<p>Observed interaction labels supervise capability prediction. Ordering and generation also train the shared representation.</p></div>'))
 for node in retained:article.append(node)
 if key=='order':
  article.append(fragment('<p class="method-small-copy">The planning context predicts object selection and interaction priorities. Sampling these priorities produces candidate orders for the same scene.</p>'))
 elif key=='flow':
  article.append(fragment('<p class="method-small-copy">Each generated interaction can depend on the observed context and preceding ranks. Feasibility is checked separately before execution.</p>'))
 elif key=='execution':
  article.append(fragment('<p class="method-small-copy">The controller applies a short segment, then updates from the observed state. High level replanning revises the remaining interactions when enabled.</p>'))
 article.append(details)
(root/'index.html').write_text(str(soup).rstrip()+'\n')
import runpy
runpy.run_path(str(root/'scripts/build_embodiment_gallery.py'))
if (root/'assets/maze-method-trace.js').exists():runpy.run_path(str(root/'scripts/build_maze_method.py'))
if (root/'assets/mpc-comparison.json').exists():runpy.run_path(str(root/'scripts/build_execution_section.py'))

if (root/'assets/learning-explorer.js').exists():runpy.run_path(str(root/'scripts/build_learning_sections.py'))
