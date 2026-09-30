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
gallery=s.select_one('#method-execution>.pushing-gallery')
assert gallery and not s.select_one('#controller-additional')
assert not gallery.select('.media-unavailable')
for controller in ['optimized','baseline']:
    group=gallery.select_one(f'[data-controller="{controller}"]')
    tiles=group.select('.media-tile')
    assert len(tiles)==2
    assert [tile.select_one('span').get_text() for tile in tiles]==['G1','Spot + arm']
    assert all(tile.select_one('video source')['src'].split('?')[0]==f"assets/media/{tile['data-scene']}.mp4" for tile in tiles)
for row in rows:
    scene=row['scene'];assert scene
    script=(root/f'assets/recordings/{scene}.hex.js').read_text()
    binary=bytes.fromhex(json.loads(script.rsplit(' = ',1)[1].rstrip(';\n')))
    with tempfile.NamedTemporaryFile() as f:
        f.write(binary);f.flush();record,buffers=read_recording(f.name)
    validate_binary_arrays(record,buffers)
    video=imageio_ffmpeg.read_frames(str(root/f'assets/media/{scene}.mp4'))
    metadata=next(video);video.close()
    assert metadata['fps']>=24
    assert abs(metadata['duration']-record['durationSeconds'])<.1,(scene,metadata,record['durationSeconds'])
    assert (root/f'assets/media/{scene}.png').is_file()
    assert any(t>0 and m['type']=='SetPositionMessage' for t,m in record['messages'])
    print('PASS',scene,'video and native recording duration',record['durationSeconds'])
print('PASS G1 and Spot + arm in one row per controller, four distinct moving replays, no unavailable tiles')
