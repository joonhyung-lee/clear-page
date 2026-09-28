"""Add inspection modes to the embodiment gallery."""
from pathlib import Path
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1];s=BeautifulSoup((root/'index.html').read_text(),'html.parser')
gallery=s.select_one('.embodiment-gallery')
if not s.find(id='embodiment-demo'):
 wrapper=s.new_tag('div',id='embodiment-demo');gallery.replace_with(wrapper)
 wrapper.append(BeautifulSoup('''<div class="embodiment-controls" role="group" aria-label="Embodiment inspection mode"><button type="button" data-embodiment-mode="structure" aria-pressed="true">Structure</button><button type="button" data-embodiment-mode="traversability" aria-pressed="false">Traversability</button><button type="button" data-embodiment-mode="manipulation" aria-pressed="false">Manipulation affordance</button></div>''','html.parser'))
 wrapper.append(gallery)
 wrapper.append(BeautifulSoup('<p class="figure-caption embodiment-explanation" aria-live="polite">Translucent visual meshes reveal the links and joints of each body. Inspect any robot in 3D.</p>','html.parser'))
for v in gallery.select('.viewer'):
 name=v.get('data-embodiment',v['data-scene'].removeprefix('structure-'));v['data-embodiment']=name
 video=v.find('video')
 if video:
  video.replace_with(s.new_tag('img',attrs={'class':'preview-image','src':f'assets/media/structure-{name}.png','alt':f'{v["data-title"]} structure and kinematic skeleton','loading':'lazy','width':'560','height':'440'}))
if not s.find('script',src='assets/embodiments.js'):s.head.append(s.new_tag('script',attrs={'src':'assets/embodiments.js','defer':''}))
(root/'index.html').write_text(str(s).rstrip()+'\n')
