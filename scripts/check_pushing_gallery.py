"""Verify the requested two-by-one controller galleries and real replay assets."""
import json
from pathlib import Path
import tempfile

from bs4 import BeautifulSoup
import imageio_ffmpeg
from recording_io import read_recording,validate_binary_arrays

root=Path(__file__).resolve().parents[1]
rows=json.loads((root/'assets/controller-gallery.json').read_text())
assert len(rows)==4
assert {(r['controller'],r['body']) for r in rows}=={
    (c,b) for c in ['optimized','baseline'] for b in ['g1','spot_arm']}
assert len({r['scene'] for r in rows})==4,'Four distinct physical replays are required'
s=BeautifulSoup((root/'index.html').read_text(),'html.parser')
gallery=s.select_one('#method-execution .pushing-gallery')
assert gallery and not s.select_one('#controller-additional')
assert not gallery.select('.media-unavailable')
for controller in ['optimized','baseline']:
    group=gallery.select_one(f'[data-controller="{controller}"]')
    tiles=group.select('.media-tile')
    assert len(tiles)==2
    assert [tile.select_one('span').get_text() for tile in tiles]==['G1','Spot + arm']
    for tile in tiles:
        suffix='-contact' if tile.get('data-contact-side')=='true' else ''
        assert tile.select_one('video source')['src'].split('?')[0]==f"assets/media/{tile['data-scene']}{suffix}.mp4"
for row in rows:
    scene=row['scene'];assert scene
    if row.get('protocolLabel'):
        tile=gallery.select_one(f'[data-scene="{scene}"]')
        assert row['protocolLabel'] in tile.get_text(' ',strip=True)
        if row.get('nativeController'):
            assert row['protocolLabel']=='Native SUMO'
            assert 'Original CEM' in row['note']
            if row.get('displayClip'):
                clip=row['displayClip']
                assert abs(clip['end']-clip['toppleTime']-5)<1e-6
                assert 'five seconds after toppling' in row['note']
            else:
                assert 'Full attempt from reset' in row['note']
        else:
            assert 'not an unmodified upstream SUMO controller' in row['note']
            assert 'extended-arm push' in row['note']
    if row.get('variant'):
        tile=gallery.select_one(f'[data-scene="{scene}"]')
        assert row['variant'] in tile.get_text(' ',strip=True)
        assert row['variant'] in tile['data-title']
        original=row['originalScene']
        assert (root/f'assets/media/{original}.mp4').is_file()
        assert gallery.select_one(f'a[href^="assets/media/{original}.mp4"]')
        assert 'not the original baseline' in row['note']
        if row.get('gainDiagnostic'):
            gain=row['gainDiagnostic']
            assert scene=='mpc-spot-high-kp' and row['variant']=='P gain ×3'
            assert gain['scale']==3 and {1,16}<=set(gain['verifiedWorldCounts'])
            assert len(gain['actuators'])==6
            assert all(v['originalKp']==120 and v['kp']==360 and v['kd']==2 for v in gain['actuators'])
            assert 'Original cost weights' in row['note'] and not row.get('costAblation')
            if row.get('failedAttempt'):
                assert row['interactionComplete'] is False and 'No push' in row['outcome']
                assert row['failureReason']=='contact reference transition incomplete'
                assert 'No object push occurred' in row['note']
        if row.get('costAblation'):
            cost=row['costAblation']
            assert scene=='mpc-spot-cost-ablation' and row['variant']=='Cost ablation'
            assert cost['term']=='controls' and cost['weight']==0 and cost['originalWeight']==2
            assert {key for key,value in cost['effectiveWeights'].items() if value!=cost['originalWeights'][key]}=={'controls'}
            assert cost['effectiveWeights']['controls']==0
            assert 'native command shaping and timing are retained' in row['note']
        if row.get('commandHoldIntervals'):
            assert row['scene']=='mpc-spot-variable-delay'
            assert row['variant']=='Variable-delay actuation stress test'
            assert row['commandHoldIntervals']==[.1,.8,.2,1.,.16,.6]
    script=(root/f'assets/recordings/{scene}.hex.js').read_text()
    binary=bytes.fromhex(json.loads(script.rsplit(' = ',1)[1].rstrip(';\n')))
    with tempfile.NamedTemporaryFile() as f:
        f.write(binary);f.flush();record,buffers=read_recording(f.name)
    validate_binary_arrays(record,buffers)
    video=imageio_ffmpeg.read_frames(str(root/f'assets/media/{scene}.mp4'))
    metadata=next(video);video.close()
    tile=gallery.select_one(f'[data-scene="{scene}"]')
    published=tile.select_one('video source')['src'].split('?')[0]
    display=imageio_ffmpeg.read_frames(str(root/published));display_metadata=next(display);display.close()
    assert display_metadata['fps']>=20
    assert abs(display_metadata['duration']-record['durationSeconds'])<.1,(scene,'Display timeline must match native replay')
    assert metadata['fps']>=24
    assert abs(metadata['duration']-record['durationSeconds'])<.1,(scene,metadata,record['durationSeconds'])
    if row.get('body')=='spot_arm':
        ego=imageio_ffmpeg.read_frames(str(root/f'assets/media/{scene}-ego.mp4'))
        ego_metadata=next(ego);ego.close()
        assert abs(ego_metadata['duration']-record['durationSeconds'])<.1,(scene,'Ego view must use the same interval')
        assert (root/f'assets/media/{scene}-ego.png').is_file()
    assert (root/f'assets/media/{scene}.png').is_file()
    assert any(t>0 and m['type']=='SetPositionMessage' for t,m in record['messages'])
    print('PASS',scene,'video and native recording duration',record['durationSeconds'])
print('PASS G1 and Spot + arm in one row per controller, four distinct moving replays, no unavailable tiles')
