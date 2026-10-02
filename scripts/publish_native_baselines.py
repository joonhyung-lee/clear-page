"""Replace the two Naive gallery tiles with verified native recordings."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('g1',type=Path);p.add_argument('spot',type=Path)
a=p.parse_args();root=Path(__file__).resolve().parents[1]
path=root/'assets/controller-gallery.json';rows=json.loads(path.read_text())
new=[r for r in rows if r['controller']=='optimized'];protocols=[]
assert len(new)==2
for folder,body,scene in [(a.g1,'g1','mpc-g1-native'),(a.spot,'spot_arm','mpc-spot-native')]:
    r=json.loads((folder/'result.json').read_text())
    assert r['nativeController'] and r['verification']['originalCosts'] and r['verification']['originalCEM']
    assert not r['protocol']['cartesianTracking'] and not r['protocol']['addedJointSmoothing']
    for asset in [f'media/{scene}{suffix}' for suffix in ['.png','.mp4','-ego.mp4','-ego.png']]+[f'recordings/{scene}.hex.js']:
        assert (root/'assets'/asset).is_file(),asset
    note=r['scope']+' '+r['terminalRule']
    if r.get('displayClip'):
        note+=f" Display ends five seconds after toppling at {r['displayClip']['toppleTime']:.2f} s."
    elif r['fell']: note+=f" Body height crosses the native standing threshold at {r['firstFallTime']:.2f} s. The complete attempt remains visible."
    new.append(dict(task='G1' if body=='g1' else 'Spot + arm',body=body,controller='baseline',
        scene=scene,group='primary',interactionComplete=r['pushReportedSuccess'],nativeController=True,
        protocolLabel='',
        outcome=f"{r['moved']:.2f} m moved · {r['goalError']:.2f} m goal error · {r['duration']:.1f} s",
        note=note,**({'displayClip':r['displayClip']} if r.get('displayClip') else {})))
    protocols.append(dict(scene=scene,**r))
path.write_text(json.dumps(new,indent=2)+'\n')
(root/'assets/native-baseline-protocol.json').write_text(json.dumps(protocols,indent=2)+'\n')
subprocess.run([sys.executable,str(root/'scripts/build_controller_gallery.py')],check=True)
