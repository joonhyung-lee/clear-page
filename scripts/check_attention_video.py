"""Check encoded videos, real attention weights and recorded observation alignment."""
import argparse
import json
from pathlib import Path
import imageio_ffmpeg
import numpy as np
from PIL import Image
from attention_probability import distribution
from attention_lanes import active_path, box_vertices, contact_guide

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('folder',type=Path)
p.add_argument('--scenes',type=Path,required=True)
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
data=json.loads((a.folder/'video-attention.json').read_text())
manifest=json.loads((a.folder/'video-manifest.json').read_text())
evidence=json.loads((a.folder/'contact-evidence.json').read_text())['cases']
plans=json.loads((a.folder/'recorded-plans.json').read_text())['cases']
raw=(root/'assets/learning-samples.js').read_text()
samples=json.loads(raw[raw.index('=')+1:].strip().rstrip(';'))['ordering']
total=0
total_green_pixels=0
total_red_pixels=0
for case,m,sample_index in zip(data['cases'],manifest,[53,54,52],strict=True):
    sample=samples[sample_index]
    assert m['contrast']['low']==0 and m['contrast']['high']>=max(float(np.asarray(f['encoder']).mean((0,1,2)).max()) for f in case['frames'])
    assert m['topdown']['height']<min(sample['scene']['world_size'])
    scene=json.loads((a.scenes/case['id']/'scene.json').read_text())
    native=np.load(a.scenes/case['id']/'geometry.npz')
    for f,idx in zip(case['frames'][1:],np.linspace(0,len(sample['rollout'])-1,41).astype(int),strict=True):
        recorded=sample['rollout'][idx]
        assert f['time']==recorded[0] and f['scene']['start']==recorded[1:4]
        assert [o['pose'] for o in f['scene']['objects']]==recorded[4]
        w=np.asarray(f['encoder'])
        assert np.isfinite(w).all() and (w>=0).all()
        assert np.allclose(w.sum(-1),1,atol=2e-6,rtol=0)
        mean=w.mean((0,1,2))
        labels,prob,units,colors=distribution(mean,f['keys'])
        domain=[i for i,k in enumerate(f['keys']) if k['kind'] in ['object','terrain']]
        assert np.isclose(prob.sum(),1) and units.sum()==1000 and (prob>=0).all()
        assert abs(prob[-1]-sum(mean[i] for i,k in enumerate(f['keys']) if k['kind']=='terrain')/mean[domain].sum())<1e-12
        assert len(labels)==len(f['scene']['objects'])+1
        assert np.max(abs(units/1000-prob))<.001
        assert np.allclose(colors[domain],mean[domain]/mean[domain].sum())
        assert np.isclose(colors.sum(),1), 'Terrain aggregate was repeated on every tile'
        assert 'Not a selection probability' in m['legend']['normalization']
        j=np.abs(native['time']-f['time']).argmin()
        # Public observations and native mesh replay were sampled independently.
        assert abs(native['time'][j]-f['time'])<=.041
        assert np.max(np.abs(native['positions'][j,1,:2]-recorded[1:3]))<.03
        for name,oid in scene['objectBodies'].items():
            b=scene['bodies'].index(name)
            assert np.max(np.abs(native['positions'][j,b,:2]-recorded[4][oid][:2]))<.03
    path=a.folder/m['file']
    frames,seconds=imageio_ffmpeg.count_frames_and_secs(str(path))
    assert frames==m['frames'] and abs(seconds-frames/m['fps'])<.05
    stream=imageio_ffmpeg.read_frames(str(path));meta=next(stream);decoded=np.frombuffer(next(stream),dtype='uint8').reshape(720,1280,3);stream.close()
    assert meta['size']==(1280,720) and meta['fps']==25
    previews=sorted(a.folder.glob(path.stem.replace('-topdown-ego','')+'-frame-*.png'))
    assert len(previews)==3
    assert np.mean(abs(decoded.astype(float)-np.asarray(Image.open(previews[0])).astype(float)))<3, 'Encoded video differs from reviewed render'
    audit=json.loads((a.folder/(path.stem.replace('-topdown-ego','')+'-render-audit.json')).read_text())['frames']
    assert len(audit)==frames
    for row in audit:
        assert row['eefTargetGuides']==0, 'Unrecorded EEF target guide in output'
        if not row['pushing']:
            assert row['eefTraces']==row['contacts']==row['contactTargets']==0, 'Motion/contact layer remains after push'
    egos=[np.asarray(Image.open(f))[52:316,904:1256].astype(float) for f in previews]
    assert all(np.std(ego)>10 for ego in egos)
    assert max(np.mean(np.abs(egos[0]-ego)) for ego in egos[1:])>3
    overlays=[np.asarray(Image.open(f))[372:636,904:1256].astype(float) for f in previews]
    green_pixels=0
    for preview,rgb,overlay in zip(previews,egos,overlays,strict=True):
        red=(overlay[:,:,0]>overlay[:,:,1]+65)&(overlay[:,:,0]>overlay[:,:,2]+65)&(abs(overlay[:,:,1]-overlay[:,:,2])<45)
        total_red_pixels+=int(red.sum())
        cyan=(overlay[:,:,2]>overlay[:,:,0]+60)&(overlay[:,:,1]>overlay[:,:,0]+60)
        assert not cyan.any(), 'Old cyan contact anchor remains in Ego attention'
        # The two cameras must preserve the same background/geometry silhouette.
        rgb_sky=(rgb.min(-1)>245)&(np.ptp(rgb,axis=-1)<8)
        overlay_sky=(overlay.min(-1)>245)&(np.ptp(overlay,axis=-1)<8)
        # Exact raster coverage of intentional flow ghosts, lanes and contact
        # markers, including faint transparent faces and white anchor borders.
        markers=np.asarray(Image.open(preview.with_name(preview.name.replace('-frame-','-mask-'))))>0
        assert np.array_equal(rgb_sky[~markers],overlay_sky[~markers])
        green=(overlay[:,:,1]>overlay[:,:,0]+12)&(overlay[:,:,1]>overlay[:,:,2]+8)
        green_pixels+=int(green.sum())
        chromatic=overlay[(np.ptp(overlay,axis=-1)>12)&~markers]
        assert ((chromatic[:,1]>chromatic[:,0])&(chromatic[:,1]>chromatic[:,2])).all()
    # Views with low scene attention need not contain strong object highlights.
    total_green_pixels+=green_pixels
    recorded=evidence[case['id']]
    plan=plans[case['id']]
    assert m['trajectories']['ghostsPerActiveObject']==2
    assert m['trajectories']['ghostViews']==['topdown','minimap']
    assert m['trajectories']['egoLayers']==['eef','contact']
    assert m['trajectories']['eefTargetCount']==0
    eef=np.asarray([row['eef'] for row in recorded['frames']])
    assert np.isfinite(eef).all() and eef.shape==(len(recorded['frames']),2 if case['body']=='g1' else 1,3)
    assert m['trajectories']['eefSites']==recorded['eefSites']
    if case['body']=='g1':
        assert recorded['eefSites']==['left_palm','right_palm']
        assert np.linalg.norm(eef[:,0]-eef[:,1],axis=1).min()>.05
    assert m['trajectories']['flowProposalIndex']==plan['flowProposalIndex']
    for flow,executed in zip(plan['flowPaths'],plan['paths'],strict=True):
        poses=np.asarray(flow['poses']);end=np.asarray(executed['poses'][-1]).copy()
        assert len(poses)==8 and np.isfinite(poses).all()
        direction=end[:2]-np.asarray(executed['poses'][0])[:2]
        end[:2]-=.15*direction/np.linalg.norm(direction)
        assert np.allclose(poses[-1],end,atol=1e-6,rtol=0)
        assert active_path(plan['flowPaths'],(flow['start']+flow['end'])/2) is flow
        assert box_vertices(poses[-1],flow['size']).shape==(8,3)
        assert np.allclose(contact_guide(poses,[0,0,.5])[:,:2],poses[:,:2])
    assert bool(recorded['targets'])==(m['contacts']['projectedMarkers']['target']>0)
    assert any(row['contacts'] for row in recorded['frames'])==(m['contacts']['projectedMarkers']['contact']>0)
    assert all(t['time']<t['until'] and np.isfinite(t['position']).all() for t in recorded['targets'])
    total+=frames
    print('PASS',path.name,frames,'frames, source alignment, normalized group legend, matched RGB/green grayscale ego views')
frames,seconds=imageio_ffmpeg.count_frames_and_secs(str(a.folder/'attention-topdown-ego.mp4'))
assert frames==total
assert total_green_pixels>100, 'No visible green ego overlay in saved frames'
assert total_red_pixels>20, 'No visible red contact highlight in saved frames'
print('PASS combined MP4:',frames,'frames,',seconds,'seconds')
