"""Publish the two-embodiment pushing gallery after both replays are exported."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('optimized',type=Path);p.add_argument('baseline',type=Path)
a=p.parse_args();root=Path(__file__).resolve().parents[1]
previous=json.loads((root/'assets/controller-gallery.json').read_text())
rows=[]
for controller,folder in [('optimized',a.optimized),('baseline',a.baseline)]:
    existing=next(r for r in previous if r['controller']==controller and r['scene']==('mpc-optimized' if controller=='optimized' else 'mpc-baseline-push'))
    rows.append({**existing,'task':'G1','body':'g1','group':'primary'})
    record=json.loads((folder/'result.json').read_text())
    assert record['controller']==('laqdpp' if controller=='optimized' else 'topk')
    scene='mpc-spot-'+controller
    for path in [f'media/{scene}.mp4',f'media/{scene}.png',f'recordings/{scene}.hex.js']:
        assert (root/'assets'/path).is_file(),path
    rows.append(dict(task='Spot + arm',body='spot_arm',controller=controller,scene=scene,group='primary',
        outcome=f"{record['moved']:.2f} m moved · {record['goalError']:.2f} m goal error · {record['duration']:.1f} s",
        note=record['scope']+' '+('The controller reports completion of the interaction.' if record['pushReportedSuccess'] else 'The controller does not report completion of the interaction.')))
(root/'assets/controller-gallery.json').write_text(json.dumps(rows,indent=2)+'\n')
subprocess.run([sys.executable,str(root/'scripts/build_controller_gallery.py')],check=True)
