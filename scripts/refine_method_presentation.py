"""Keep method explanations compact and synchronize the visible camera labels."""
from bs4 import BeautifulSoup

def refine(soup):
 marker=soup.find(id='overview-arrow')
 if marker:
  marker.attrs.pop('markerWidth',None);marker.attrs.pop('markerHeight',None)
  marker['markerwidth']='10';marker['markerheight']='10'
 for section in soup.select('.learning-explorer'):
  kind=section.get('data-kind');section.select_one('h4 + p, h5 + p').string=('Select a point to replay the recorded attempt and compare its outcome with the prediction.' if kind=='grounding' else 'Follow the recorded route from start to goal and inspect the objects moved along it.')
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
  process.select_one('h4 + p').string='Both palms move in a shared XYZ frame. Gray paths show the saved candidates. Dark lines follow the recorded execution.'
  for node in process.select('.mpc-display-options,.mpc-anchor-controls,.mpc-coordinate-controls,.mpc-process-readout,.mpc-view-controls'):
   node.decompose()
  controls=process.select_one('.mpc-process-controls');controls.clear()
  controls.append(BeautifulSoup('<div class="mpc-view-controls" role="group" aria-label="Trajectory view"><button type="button" data-mpc-view="2d" aria-pressed="false">2D View</button><button type="button" data-mpc-view="3d" aria-pressed="true">3D View</button></div><button type="button" id="mpc-robot-context" aria-pressed="false">Robot overlay</button><button id="mpc-process-play" type="button">Pause</button><div class="mpc-timeline"><button class="mpc-time-pin" type="button" title="CLEAR first interaction completes at 14.0 s">Ours · 14.0 s</button><input aria-label="Replay time" id="mpc-process-update" type="range" min="0" max="1" step="0.0001" value="0"/></div><span id="mpc-process-counter">0.0 / 15.0 s</span><label class="mpc-full-control"><input id="mpc-full-rollout" type="checkbox"/> Full rollout · 40 s</label>','html.parser'))
  note=process.select_one('.mpc-phase-note')
  if not note:
   note=soup.new_tag('p',attrs={'class':'mpc-phase-note'});controls.insert_after(note)
  note.string='The first interaction completes at 14 s for CLEAR. SUMO loses contact at 14.14 s. Full rollout shows both controllers through 40 s, including recorded motion after the interaction. The endpoints do not measure a speedup.'
  for figure in process.select('[data-process]'):
   for canvas in figure.select('canvas')[1:]:canvas.decompose()
   canvas=figure.select_one('canvas');canvas['width']='560';canvas['height']='560';canvas['aria-label']='Both palm trajectories in a shared XYZ coordinate frame';canvas.attrs.pop('data-palm',None)
   if not figure.select_one('.mpc-recording-status'):
    status=soup.new_tag('p',attrs={'class':'mpc-recording-status'});figure.select_one('canvas').insert_before(status)
  for caption in process.select('.mpc-process-content > .figure-caption'):caption.decompose()
  scope=process.select_one('.method-details p')
  if scope:scope.string='L and R identify the recorded left and right palms. X follows the reference push direction, Y is lateral, and Z is height. Both hands share an origin at their initial horizontal midpoint. Gray paths include every saved candidate from all recorded updates and the complete recorded execution. They provide replay context and were not available to the controller in advance. Colored paths show the current candidates and applied forecast. The 2D and 3D views preserve the same source positions and replay time. Drag rotates the shared camera, shift drag pans, and the wheel or a two finger pinch zooms. Double click or Home resets the camera. The outlined region and upper right detail show the same current palm trajectories. Default playback stops at 15 s after contact loss and settling. The full recording remains available through 40 s. The optimized clip starts at the first interaction update, 6.5 s into its run. SUMO starts at its native reset and first contacts the object at 1.545 s. These starts and stopping criteria differ. The 14 s pin marks completion of the first CLEAR interaction. Its continuation contains navigation and a subsequent interaction from the same recorded run. Current forecasts are shown only while valid and the gray archive retains the first interaction candidates. Robot overlay shows the measured kinematic skeleton inside translucent meshes and follows the body in the same reference direction. Both records extend through 40 s. These clips are not a measured speedup.'

 return soup

if __name__=='__main__':
 from pathlib import Path
 p=Path(__file__).resolve().parents[1]/'index.html';p.write_text(str(refine(BeautifulSoup(p.read_text(),'html.parser'))).rstrip()+'\n')
