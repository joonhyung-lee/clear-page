"""Apply shared prose widths, highlighted phrases, and an anonymous section rail."""
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'index.html';s=BeautifulSoup(p.read_text(),'html.parser')
def content(node,html):
 node.clear()
 for item in list(BeautifulSoup(html,'html.parser').contents):node.append(item)
content(s.select_one('#tldr .academic-copy'),'CLEAR jointly <mark>selects objects</mark>, <mark>determines their interaction order</mark>, and <mark>generates motion references</mark> conditioned on robot morphology and scene geometry.')
content(s.select_one('#motivation .academic-copy'),'A humanoid pushes a box, a quadruped crosses steps, and a wheeled robot follows a slope to reach the same goal. <mark>Robot morphology determines terrain traversability and feasible object interactions.</mark> Planning must account for these constraints and for how each interaction affects subsequent actions.')
old=s.select_one('#section-rail')
if old:old.decompose()
nav=s.new_tag('nav',id='section-rail',attrs={'aria-label':'Page contents'})
label=s.new_tag('span',attrs={'class':'rail-label'});label.string='CONTENTS';nav.append(label)
for target,label in [('tldr','Overview'),('motivation','Motivation'),('method','Method'),('method-grounding','(a) Grounding'),('method-order','(b) Ordering'),('method-flow','(c) Generation'),('method-execution','(d) Execution'),('learning','Training'),('learning-planner','(a) Objective'),('learning-data','(b) Samples'),('controller-pretraining','(c) Policy training'),('experiments','Experiments')]:
 if not s.find(id=target):continue
 a=s.new_tag('a',href='#'+target);a.string=label
 if target.startswith(('method-','learning-')) or target=='controller-pretraining':a['class']=['rail-subsection']
 nav.append(a)
s.body.append(nav)
# Emphasize one key operation per stage without changing mathematical markup.
for ident,phrase in [('method-grounding','combines morphology, object and scene features'),('method-order','selection probability and priority mean and standard deviation'),('method-flow','Flow time describes generation progress, not execution time.'),('method-execution','accounting for the scene changes caused by earlier interactions')]:
 lead=s.select_one('#'+ident+' > .method-lead')
 if not lead:continue
 for text in list(lead.find_all(string=True)):
  if phrase in text and text.parent.name!='mark':
   before,after=str(text).split(phrase,1);mark=s.new_tag('mark');mark.string=phrase
   text.replace_with(before,mark,after);break
p.write_text(str(s).rstrip()+'\n')
