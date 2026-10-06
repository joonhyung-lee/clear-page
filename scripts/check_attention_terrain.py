"""Verify native terrain geometry, token probabilities, overview and rendered maps."""
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image
from attention_probability import distribution
from attention_terrain import PALETTE,features,height

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--folder',type=Path,default=Path(__file__).resolve().parents[1]/'attention/videos')
p.add_argument('--scenes',type=Path,required=True)
a=p.parse_args()
case=json.loads((a.folder/'video-attention.json').read_text())['cases'][2]
meta=json.loads((a.scenes/case['id']/'scene.json').read_text())
source=np.load(a.scenes/case['id']/'geometry.npz')
tiles=meta['scene']['terrain'];keys=case['frames'][0]['keys']
for index,tile in enumerate(tiles):
    key=next(i for i,k in enumerate(keys) if k['source_id']==f'terrain:{index}')
    vertices=np.concatenate([source[f'vertices_{i}'] for i,mesh in enumerate(meta['meshes']) if mesh['key']==key])
    l,b,r,u=tile['bounds']
    assert np.allclose([vertices[:,0].min(),vertices[:,1].min(),vertices[:,0].max(),vertices[:,1].max()],[l,b,r,u],atol=1e-5)
    borders,risers,contours,arrow=features(tile)
    assert len(borders)==4
    assert np.isclose(vertices[:,2].max(),max(height(tile,x,y) for x,y in [(l,b),(r,b),(r,u),(l,u)]),atol=1e-5)
    if tile['kind']=='ramp':
        assert len(contours)==3 and len(arrow)==3
        start,end=arrow[0]
        assert end[2]>start[2], 'Slope arrow points downhill'
    else:assert not contours and not arrow, 'Invented terrain subdivisions'
for frame in case['frames']:
    w=np.asarray(frame['encoder']).mean((0,1,2));labels,p,units,spatial=distribution(w,frame['keys'])
    domain=[i for i,k in enumerate(frame['keys']) if k['kind'] in ['object','terrain']]
    terrain=[i for i,k in enumerate(frame['keys']) if k['kind']=='terrain']
    assert np.allclose(spatial[domain],w[domain]/w[domain].sum())
    assert np.isclose(spatial[terrain].sum(),p[-1]) and np.isclose(spatial.sum(),1) and units.sum()==1000
# Renderer exports the actual camera parameters used for every movie frame.
audit=json.loads((a.folder/'attention-terrain-g1-render-audit.json').read_text())
assert audit['frames'][0]['overview']==1 and audit['frames'][-1]['overview']==0
for frame in audit['frames']:
    seconds=frame['time']/2
    if seconds<=1.5:assert frame['overview']==1
    if seconds>=3:assert frame['overview']==0
first=np.asarray(audit['frames'][0]['camera'])
points=np.array([[x,y,height(tile,x,y)+.02,1] for tile in tiles for x in [tile['bounds'][0],tile['bounds'][2]] for y in [tile['bounds'][1],tile['bounds'][3]]])
clip=points@first.T
assert (abs(clip[:,:3]/clip[:,3,None])<1).all(), 'Overview omits part of the terrain'
previews=sorted(a.folder.glob('attention-terrain-g1-frame-*.png'))
assert len(previews)==3
for preview in previews:
    image=np.asarray(Image.open(preview)).astype(int)
    mini=image[464:687,36:259]
    for kind,color in PALETTE.items():
        assert (np.max(abs(mini-color),axis=-1)<2).sum()>30, (preview.name,kind,'minimap type missing')
first_image=np.asarray(Image.open(previews[0])).astype(int)
profile_image=np.asarray(Image.open(previews[1])).astype(int)[458:703,289:562]
for kind,color in PALETTE.items():
    assert (np.max(abs(profile_image-color),axis=-1)<2).sum()>500, (kind,'terrain profile missing')
# A follow camera must retain relief instead of returning to a vertical view.
last=np.asarray(audit['frames'][-1]['camera'])
assert abs(last[1,2])>.02, 'Follow camera loses terrain height cues'
for kind,color in PALETTE.items():
    main=first_image[60:640,280:735]
    assert (np.max(abs(main-color),axis=-1)<15).sum()>100, (kind,'overview type missing')
print('PASS native terrain bounds/heights, uphill arrows, individual token attention, 3 s overview and persistent semantic minimap')
