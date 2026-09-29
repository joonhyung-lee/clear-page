"""Keep method explanations compact and synchronize the visible camera labels."""
from bs4 import BeautifulSoup

def refine(soup):
 marker=soup.find(id='overview-arrow')
 if marker:
  marker.attrs.pop('markerWidth',None);marker.attrs.pop('markerHeight',None)
  marker['markerwidth']='10';marker['markerheight']='10'
 for section in soup.select('.learning-explorer'):
  kind=section.get('data-kind');section.select_one('h4 + p').string=('Select a point to replay the recorded attempt and compare its outcome with the prediction.' if kind=='grounding' else 'Follow the recorded route from start to goal and inspect the objects moved along it.')
  section.select_one('.sample-scatter').find_next_sibling('figcaption').string='Select a recorded sample.'
  if not section.select_one('.sample-explanation-details'):
   details=soup.new_tag('details',attrs={'class':'sample-explanation-details method-details'});summary=soup.new_tag('summary');summary.string='Data and supervision';details.append(summary)
   for node in section.select('.sample-projection-note,.learning-loss'):
    details.append(node.extract())
   section.select_one('.learning-content').append(details)
  if kind=='ordering':
   flow=section.select_one('.learning-dataflow')
   if flow:flow.decompose()
 for viewer in soup.select('.mpc-comparison .viewer'):
  caption=viewer.select_one('.ego-inset figcaption')
  if caption:caption.string='Robot chase view' if viewer['data-scene'].endswith('baseline') else 'Ego view'
 readout=soup.select_one('.maze-order-readout')
 if readout and not readout.select_one('.contour-details'):
  note=readout.select_one('.figure-caption')
  if note:
   details=soup.new_tag('details',attrs={'class':'contour-details method-details'});summary=soup.new_tag('summary');summary.string='Reading the contours';details.append(summary);note.replace_with(details);details.append(note)
 execution=soup.find(id='overview-execution')
 if execution:
  for span in execution.find_all('span',recursive=False):
   if span.get_text(strip=True)=='→':span.decompose()
 process=soup.find(id='mpc-process')
 if process:
  process.select_one('h4 + p').string='The full execution stays on fixed time axes. The outlined window is magnified above, with matching A, B and C anchors.'
  for caption in process.select('.mpc-process-pair figcaption'):caption.decompose()
  for figure in process.select('[data-process]'):
   if len(figure.select('canvas'))==1:
    second=soup.new_tag('canvas',attrs={'width':'560','height':'440'});figure.select_one('canvas').insert_after(second)
   for hand,canvas in enumerate(figure.select('canvas')):
    canvas['aria-label']=('Left' if hand==0 else 'Right')+' palm full execution with a magnified forecast window and time-aligned XY anchor'
    canvas['data-palm']=str(hand)
  hand_picker=process.select_one('.mpc-hand')
  if hand_picker:hand_picker.decompose()
  stages=process.select_one('.mpc-stages')
  if stages:stages.decompose()
  if not process.select_one('.mpc-display-options'):
   options=BeautifulSoup('<div class="mpc-display-options"><div class="mpc-legend"><span class="candidate">Candidates</span><span class="chosen">Selected</span><span class="observed">Observed</span></div></div>','html.parser')
   process.select_one('.mpc-process-controls').insert_after(options)
  if not process.select_one('#mpc-process-speed'):
   speed=BeautifulSoup('<label class="mpc-speed">Speed <select id="mpc-process-speed" aria-label="Search replay speed"><option value="1">1×</option><option value="2" selected>2×</option><option value="4">4×</option></select></label>','html.parser');process.select_one('.mpc-process-controls').append(speed)
  if not process.select_one('.mpc-anchor-controls'):
   options=BeautifulSoup('<div class="mpc-anchor-controls" role="group" aria-label="Magnified forecast anchor"><span>Inspect anchor</span><button type="button" data-anchor="0" aria-pressed="false">Current</button><button type="button" data-anchor="1" aria-pressed="true">Midpoint</button><button type="button" data-anchor="2" aria-pressed="false">Endpoint</button></div>','html.parser');process.select_one('.mpc-display-options').insert_after(options)
  for b,label in zip(process.select('[data-anchor]'),['A · Now','B · Midpoint','C · End']):b.string=label
  if not process.select_one('.mpc-candidate-controls'):
   options=BeautifulSoup('<div class="mpc-candidate-controls" role="group" aria-label="Candidate selection display"><button type="button" data-candidates="all" aria-pressed="true">All candidates</button><button type="button" data-candidates="retained" aria-pressed="false">Retained only</button></div>','html.parser');process.select_one('.mpc-anchor-controls').append(options)
  legend=process.select_one('.mpc-legend')
  if legend:legend.clear();legend.append(BeautifulSoup('<span class="candidate">Candidates</span><span class="chosen">Retained</span><span class="applied">Applied</span><span class="observed">Observed</span>','html.parser'))
  scope=process.select_one('.method-details p')
  if scope:scope.string='The main axes cover the full 40 s execution and the final prediction horizon. The optimized recording ends at 14 s. Faint main traces show the complete recorded execution and dark traces show the portion already observed. Forecast details subtract the common nominal motion to reveal real candidate variation in millimetres. CLEAR applies a retained candidate, while SUMO rolls out the command formed from its two elites. Anchor inspection and filtering pause the display so the same population can be compared. These controls do not resample the optimizer.'
  captions=process.select('.mpc-process-content > .figure-caption')
  if captions:
   captions[0].string='Candidates are selected as whole trajectories at each MPC update. A, B and C are time slices through those same trajectories, not separate sampling decisions. The XY dots are the candidate positions at the highlighted time.'
   for node in captions[1:]:
    details=soup.new_tag('details',attrs={'class':'method-details'});summary=soup.new_tag('summary');summary.string='Controller and replay scope';details.append(summary);node.replace_with(details);details.append(node)
 return soup

if __name__=='__main__':
 from pathlib import Path
 p=Path(__file__).resolve().parents[1]/'index.html';p.write_text(str(refine(BeautifulSoup(p.read_text(),'html.parser'))).rstrip()+'\n')
