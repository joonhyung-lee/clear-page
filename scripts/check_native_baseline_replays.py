"""Check native baseline provenance, measured sites, timelines and mesh motion."""
import json
from pathlib import Path
import imageio_ffmpeg
import numpy as np
from scipy.spatial.transform import Rotation
from recording_io import read_recording, validate_binary_arrays

ROOT=Path(__file__).resolve().parents[1]


def check_scene(scene):
    rows=json.loads((ROOT/'assets/native-baseline-protocol.json').read_text())
    row=next(v for v in rows if v['scene']==scene)
    p=row['protocol']
    assert row['nativeController'] and p['nativeArmReset']
    assert all(p[k] is False for k in ['cartesianTracking','addedJointSmoothing','addedJitter','gainOverride','commandHoldOverride'])
    assert row['verification']['sourceMethodsMatched'] and row['verification']['exactRecordedFK']
    assert p['actionDimension']==(3 if row['robot']=='g1' else 10)
    rec,buffers=read_recording(ROOT/f'assets/recordings/{scene}.viser')
    validate_binary_arrays(rec,buffers)
    messages=rec['messages']
    assert abs(rec['durationSeconds']-row['duration'])<1e-6
    for suffix in ['', '-ego']:
        reader=imageio_ffmpeg.read_frames(str(ROOT/f'assets/media/{scene}{suffix}.mp4'))
        meta=next(reader);first=np.frombuffer(next(reader),dtype=np.uint8);reader.close()
        assert abs(meta['duration']-row['duration'])<.1
        assert meta['fps']>=25 and first.std()>10
    for hand,(body,offset) in enumerate(zip(row['eefBodyIds'],row['eefLocalPositions'])):
        positions={t:m['position'] for t,m in messages if m['type']=='SetPositionMessage' and m['name']==f'/body-{body}'}
        quats={t:m['wxyz'] for t,m in messages if m['type']=='SetOrientationMessage' and m['name']==f'/body-{body}'}
        observed={t:m['position'] for t,m in messages if m['type']=='SetPositionMessage' and m['name']==f'/native-overlay/current-{hand}'}
        assert positions.keys()==quats.keys()==observed.keys()
        expected=np.asarray(list(positions.values()))+Rotation.from_quat(list(quats.values()),scalar_first=True).apply(np.tile(offset,(len(positions),1)))
        assert np.allclose(expected,list(observed.values()),atol=1e-6)
        assert np.linalg.norm(np.diff(expected,axis=0),axis=1).sum()>.1
        assert len(observed)==row['verification']['frames']
    target=row['objectBodyId']
    positions={t:m['position'] for t,m in messages if m['type']=='SetPositionMessage' and m['name']==f'/body-{target}'}
    markers={t:m['position'] for t,m in messages if m['type']=='SetPositionMessage' and m['name']=='/native-overlay/object-current'}
    assert positions.keys()==markers.keys()
    actual=np.asarray(list(positions.values()))
    assert np.allclose(actual[:,:2],np.asarray(list(markers.values()))[:,:2],atol=1e-6)
    assert abs(np.linalg.norm(actual[-1,:2]-actual[0,:2])-row['moved'])<1e-6
    assert abs(np.linalg.norm(actual[-1,:2]-row['taskConfig']['goal_position'][:2])-row['goalError'])<1e-6
    if row['robot']=='spot_arm':
        assert np.allclose(row['initialArmPositions'], [0,-.9,1.8,0,-.9,0,0])
        root_positions=np.asarray([m['position'] for t,m in messages
            if m['type']=='SetPositionMessage' and m['name']=='/body-1'])
        assert row['fell']==bool(np.any(root_positions[:,2]<=.35))
    if row.get('displayClip'):
        clip=row['displayClip']
        base_quats=[(t,m['wxyz']) for t,m in messages
            if m['type']=='SetOrientationMessage' and m['name']=='/body-1']
        up=Rotation.from_quat([q for _,q in base_quats],scalar_first=True).as_matrix()[:,2,2]
        first=int(np.flatnonzero(up<=0)[0])
        assert abs(base_quats[first][0]-clip['toppleTime'])<1e-6
        assert abs(rec['durationSeconds']-clip['toppleTime']-5)<1e-6
        assert not row['verification']['fullAttempt'] and row['sourceRecordingDuration']>row['duration']
        assert abs(clip['zoom']-1.25)<1e-6
    print('PASS native replay',scene,'measured sites, object path, complete video/ego/3D and original controller provenance')


if __name__=='__main__':
    for scene in ['mpc-g1-native','mpc-spot-native']:check_scene(scene)
