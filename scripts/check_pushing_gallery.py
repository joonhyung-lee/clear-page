"""Check two body rows, their four panels, and matching recorded evidence."""
import json
from pathlib import Path
from urllib.parse import urlsplit
import imageio_ffmpeg
import numpy as np
from bs4 import BeautifulSoup
from recording_io import read_recording, validate_binary_arrays
from export_spot_eef import export

ROOT=Path(__file__).resolve().parents[1]
s=BeautifulSoup((ROOT/'index.html').read_text(),'html.parser')
assert not s.select('#method-execution .pushing-gallery, #controller-additional')
assert [n.get_text() for n in s.select('.replay-body-title')]==['G1','Spot + arm']
assert len(s.select('#method-execution .controller-summary'))==1
ids=[n['id'] for n in s.select('[id]')];assert len(ids)==len(set(ids))
for section,scenes in [('mpc-process',['mpc-optimized-full','mpc-baseline']),('spot-process',['mpc-spot-optimized','mpc-spot-native'])]:
    root=s.select_one('#'+section)
    assert [n['data-scene'] for n in root.select('.execution-body-viewer')]==scenes
    groups=root.select('.execution-controller')
    assert [s.select_one('#'+g['aria-labelledby']).get_text() for g in groups]==['MPC w/ optimization (ours)','MPC (naive)']
    for group,scene in zip(groups,scenes):
        figures=group.select('.execution-controller-panels > figure');assert len(figures)==2
        assert figures[0].select_one('.execution-body-viewer') and figures[1].select_one('canvas')
        viewer=figures[0].select_one('.viewer');assert viewer['data-external-timeline']=='true'
        assert viewer.get('data-clock-group','g1')==('spot' if section=='spot-process' else 'g1')
        record,buffers=read_recording(ROOT/f'assets/recordings/{scene}.viser')
        validate_binary_arrays(record,buffers)
        final_pose=max(t for t,m in record['messages'] if m['type']=='SetPositionMessage')
        for selector,attr in [('.preview-video source','src'),('.ego-inset video','src')]:
            path=ROOT/urlsplit(viewer.select_one(selector)[attr]).path
            reader=imageio_ffmpeg.read_frames(str(path));meta=next(reader);next(reader);reader.close()
            assert meta['fps']>=25 and abs(meta['duration']-final_pose)<.1,(scene,meta,final_pose)
        assert (ROOT/urlsplit(viewer.select_one('.preview-video')['poster']).path).is_file()
        print('PASS',scene,'paired video/Ego/Viser interval',record['durationSeconds'])

actual=json.loads((ROOT/'assets/spot-eef-data.js').read_text().split('=',1)[1].rstrip(';\n'))
assert actual==export(),'Published plot must exactly match the Viser measurements'
for key,r in actual.items():
    assert np.isfinite(r['observed']).all()
    assert all(a[0]<b[0] for a,b in zip(r['observed'],r['observed'][1:]))
    assert np.allclose(r['observed'][0][4:6],r['reference'][0][:2],atol=.05)
    assert r['observed'][0][0]==0 and abs(r['observed'][-1][0]-r['duration'])<1e-6
protocol=next(r for r in json.loads((ROOT/'assets/native-baseline-protocol.json').read_text()) if r['scene']=='mpc-spot-native')
assert all(protocol['protocol'][k] is False for k in ['cartesianTracking','addedJointSmoothing','addedJitter','gainOverride','commandHoldOverride'])
assert abs(actual['baseline']['duration']-actual['baseline']['toppleTime']-5)<1e-6
from build_body_replays import apply
before=str(s);apply(s);assert str(s)==before,'Body layout generation must be idempotent'
print('PASS two four-panel body rows; distinct measured Spot paths, original naive controller and final-frame stop')
