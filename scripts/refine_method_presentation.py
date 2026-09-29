"""Keep method explanations compact and synchronize the visible camera labels."""
from bs4 import BeautifulSoup

def refine(soup):
 marker=soup.find(id='overview-arrow')
 if marker:
  marker.attrs.pop('markerWidth',None);marker.attrs.pop('markerHeight',None)
  marker['markerwidth']='10';marker['markerheight']='10'
 for section in soup.select('.learning-explorer'):
  kind=section.get('data-kind');section.select_one('h4 + p').string=('Select a point to replay the recorded attempt and compare its outcome with the prediction.' if kind=='grounding' else 'Select a reference rollout to inspect which objects participate and in which order.')
  section.select_one('.sample-scatter').find_next_sibling('figcaption').string='Select a recorded sample.'
  if not section.select_one('.sample-explanation-details'):
   details=soup.new_tag('details',attrs={'class':'sample-explanation-details method-details'});summary=soup.new_tag('summary');summary.string='Data and supervision';details.append(summary)
   for node in section.select('.sample-projection-note,.learning-loss'):
    details.append(node.extract())
   section.select_one('.learning-content').append(details)
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
  process.select_one('h4 + p').string='Each recorded update reveals the complete candidate ensemble. Select an anchor to inspect its spatial spread.'
  for caption in process.select('.mpc-process-pair figcaption'):caption.decompose()
  for canvas in process.select('canvas'):canvas['aria-label']='Recorded candidate palm deviations with a magnified spatial anchor'
  stages=process.select_one('.mpc-stages')
  if stages:stages.decompose()
  if not process.select_one('.mpc-display-options'):
   options=BeautifulSoup('<div class="mpc-display-options"><div class="mpc-hand" role="group" aria-label="Palm trajectory"><button data-palm="0" aria-pressed="true" type="button">Left palm</button><button data-palm="1" aria-pressed="false" type="button">Right palm</button></div><div class="mpc-legend"><span class="candidate">Candidates</span><span class="chosen">Selected</span><span class="observed">Observed</span></div></div>','html.parser')
   process.select_one('.mpc-process-controls').insert_after(options)
  if not process.select_one('#mpc-process-speed'):
   speed=BeautifulSoup('<label class="mpc-speed">Speed <select id="mpc-process-speed" aria-label="Search replay speed"><option value="1">1×</option><option value="2" selected>2×</option><option value="4">4×</option></select></label>','html.parser');process.select_one('.mpc-process-controls').append(speed)
  if not process.select_one('.mpc-anchor-controls'):
   options=BeautifulSoup('<div class="mpc-anchor-controls" role="group" aria-label="Magnified forecast anchor"><span>Inspect anchor</span><button type="button" data-anchor="0" aria-pressed="false">Current</button><button type="button" data-anchor="1" aria-pressed="true">Midpoint</button><button type="button" data-anchor="2" aria-pressed="false">Endpoint</button></div>','html.parser');process.select_one('.mpc-display-options').insert_after(options)
  scope=process.select_one('.method-details p')
  if scope:scope.string='The search replay advances through saved controller updates. Replay speed changes presentation time only. The physical execution videos retain their original timing. The inset shows candidate displacement relative to the nominal prediction, not extra noise or modified trajectories. Our controller searches bounded contact residuals while SUMO searches base commands. Candidate spread is not a measure of control quality.'
  captions=process.select('.mpc-process-content > .figure-caption')
  if captions:
   captions[0].string='The main plot shows every candidate over the full prediction horizon. Values are deviations from the nominal forecast in millimetres. The annotated anchor shows the same candidate points in the horizontal plane. Each panel labels its own scale.'
   for node in captions[1:]:
    details=soup.new_tag('details',attrs={'class':'method-details'});summary=soup.new_tag('summary');summary.string='Controller and replay scope';details.append(summary);node.replace_with(details);details.append(node)
 return soup

if __name__=='__main__':
 from pathlib import Path
 p=Path(__file__).resolve().parents[1]/'index.html';p.write_text(str(refine(BeautifulSoup(p.read_text(),'html.parser'))).rstrip()+'\n')
