"""Publish the two-embodiment pushing gallery after both replays are exported."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('optimized',type=Path);p.add_argument('baseline',type=Path)
p.add_argument('--unshaped-baseline',action='store_true',help='Publish the separately recorded arm-command-shaping variant with its visible scope label')
a=p.parse_args();root=Path(__file__).resolve().parents[1]
previous=json.loads((root/'assets/controller-gallery.json').read_text())
rows=[]
for controller,folder in [('optimized',a.optimized),('baseline',a.baseline)]:
    existing=next(r for r in previous if r['controller']==controller and r['scene']==('mpc-optimized' if controller=='optimized' else 'mpc-baseline-push'))
    rows.append({**existing,'task':'G1','body':'g1','group':'primary'})
    record=json.loads((folder/'result.json').read_text())
    assert record['controller']==('laqdpp' if controller=='optimized' else 'topk')
    variant=controller=='baseline' and a.unshaped_baseline
    settings=record.get('commandSettings',{})
    if variant:
        assert settings.get('armCommandShaping')=='none','Variant label requires verified disabled arm shaping'
    wide=variant and settings['armTrustRegion']!=.35
    held=variant and settings.get('armCommandHz') is not None
    scene=('mpc-spot-held-arm' if held else 'mpc-spot-unshaped-wide' if wide else 'mpc-spot-unshaped') if variant else 'mpc-spot-'+controller
    for path in [f'media/{scene}.mp4',f'media/{scene}.png',f'recordings/{scene}.hex.js']:
        assert (root/'assets'/path).is_file(),path
    rows.append(dict(task='Spot + arm',body='spot_arm',controller=controller,scene=scene,group='primary',
        interactionComplete=bool(record['pushReportedSuccess']),
        outcome=f"{record['moved']:.2f} m moved · {record['goalError']:.2f} m goal error · {record['duration']:.1f} s",
        note=record['scope']+' '+('The controller reports completion of the interaction.' if record['pushReportedSuccess'] else 'The controller does not report completion of the interaction.')))
    if variant:
        rows[-1].update(originalScene='mpc-spot-baseline',variant='Arm command shaping disabled'+(' · Wider arm range' if wide else ''))
        if held:
            rows[-1]['variant']=f"{settings['armCommandHz']:g} Hz arm command diagnostic"
            rows[-1]['note']+=f" Naive MPC command-rate diagnostic. Arm actuator targets update at {settings['armCommandHz']:g} Hz in both actual and forecast worlds. Physics and base control retain their native rate."
        rows[-1]['note']+=' This physical variant disables arm command shaping.'
        if wide:
            rows[-1]['note']+=f" Arm target range is {settings['armTrustRegion']:g} rad instead of 0.35 rad."
        rows[-1]['note']+=' Other task and controller settings are matched. This is a command-setting diagnostic, not the original baseline configuration or a measured optimization speedup.'
(root/'assets/controller-gallery.json').write_text(json.dumps(rows,indent=2)+'\n')
subprocess.run([sys.executable,str(root/'scripts/build_controller_gallery.py')],check=True)
