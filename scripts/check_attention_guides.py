"""Regression checks for logged-only targets and map-only flow overlays."""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from attention_lanes import guide_anchors,draw_lanes,draw_minimap_path,draw_query_marker,draw_contact_field
base=Path(__file__).resolve().parents[1]/'attention/videos'
evidence=json.loads((base/'contact-evidence.json').read_text())['cases']
plans=json.loads((base/'recorded-plans.json').read_text())['cases']
for case,data in evidence.items():
 assert not data['eefTargets'], 'Re-audit new EEF target recordings before accepting them'
 for path in data['pushWindows']:
  for t in np.arange(path['start'],path['end'],.08):
   anchors=guide_anchors(data,t,path)
   assert not anchors, 'Invented EEF guide from contact point or observed palm'
  assert not guide_anchors(data,path['start']-.01,path)
  assert not guide_anchors(data,path['end']+.01,path)
  assert not guide_anchors(data,path['end'],None)
# Missing physical contacts stay missing in the raw evidence.
data=evidence['sample-54'];path=plans['sample-54']['flowPaths'][0];t=22.74
frame=max((f for f in data['frames'] if f['time']<=t),key=lambda f:f['time'])
assert [c['link'] for c in frame['contacts']]==['right_wrist_yaw_link']
assert not guide_anchors(data,t,path)

path=dict(poses=[[-.5,0,0],[0,0,0],[.5,0,0]],size=[.25,.3,.2])
guide=np.array([[-.5,-.2,.1],[0,-.2,.1],[.5,-.2,.1]])
ego=Image.new('RGB',(200,200),'white')
draw_lanes(ego,np.eye(4),(0,0,200,200),path,[guide],ghosts=False,flow=False)
pixels=np.asarray(ego).astype(int)
assert not ((pixels[:,:,2]>pixels[:,:,0]+30)&(pixels[:,:,2]>pixels[:,:,1]+30)).any(), 'Blue flow leaked into ego'
assert ((pixels[:,:,0]>pixels[:,:,1]+30)&(pixels[:,:,1]>pixels[:,:,2]+30)).any(), 'Guide absent from ego'
mini=Image.new('RGB',(200,200),'white')
draw_minimap_path(ImageDraw.Draw(mini),lambda p:(100+p[0]*100,100-p[1]*100),path)
assert np.any(np.asarray(mini)!=255), 'Minimap flow absent'
for kind in ['start','goal']:
    marker=Image.new('RGB',(80,80),'white')
    draw_query_marker(marker,(40,60),kind,30)
    pixels=np.asarray(marker)
    assert (pixels[55:62,37:43].min(-1)<100).any(), 'Marker misses its query coordinate'
print('PASS no inferred EEF guides, push scope, original contact gaps, ego layers and query markers')

field=Image.new('RGB',(200,200),'white')
alpha=np.asarray(draw_contact_field(field,np.eye(4),(0,0,200,200),{'position':[0,0,0]}))
assert alpha[100,100]>alpha[100,110]>alpha[100,120]>alpha[100,130]>alpha[100,140]>0
assert alpha[100,120]==alpha[120,100]==alpha[100,80]
assert alpha[0,0]==0
lanes=Image.new('RGB',(200,200),'white')
draw_lanes(lanes,np.eye(4),(0,0,200,200),None,[],traces=[np.array([[-.7,.25,0],[.7,.25,0]]),np.array([[-.7,-.25,0],[.7,-.25,0]])])
pixels=np.asarray(lanes)
assert (pixels[75,100]!=255).any() and (pixels[125,100]!=255).any()
assert (pixels[100,100]==255).all(), 'Two palm lanes were averaged into one'
print('PASS independent left/right lanes and smooth radial contact field')
