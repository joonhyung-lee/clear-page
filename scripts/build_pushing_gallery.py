"""Publish the two-embodiment pushing gallery after both replays are exported."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('optimized',type=Path);p.add_argument('baseline',type=Path)
p.add_argument('--unshaped-baseline',action='store_true',help='Publish the separately recorded arm-command-shaping variant with its visible scope label')
p.add_argument('--cost-ablation',action='store_true',help='Publish a verified single-term cost ablation with a short visible label')
p.add_argument('--gain-diagnostic',action='store_true',help='Publish a verified arm PD proportional-gain experiment')
a=p.parse_args();root=Path(__file__).resolve().parents[1]
if sum([a.cost_ablation,a.unshaped_baseline,a.gain_diagnostic])>1:p.error('Publish one diagnostic at a time')
previous=json.loads((root/'assets/controller-gallery.json').read_text())
rows=[]
for controller,folder in [('optimized',a.optimized),('baseline',a.baseline)]:
    existing=next(r for r in previous if r['controller']==controller and r.get('body')=='g1')
    rows.append({**existing,'task':'G1','body':'g1','group':'primary'})
    record=json.loads((folder/'result.json').read_text())
    assert record['controller']==('laqdpp' if controller=='optimized' else 'topk')
    variant=controller=='baseline' and a.unshaped_baseline
    settings=record.get('commandSettings',{})
    if variant:
        assert settings.get('armCommandShaping')=='none','Variant label requires verified disabled arm shaping'
    wide=variant and settings['armTrustRegion']!=.35
    held=variant and settings.get('armCommandHz') is not None
    variable=variant and settings.get('commandHoldIntervals') is not None
    scene=('mpc-spot-variable-delay' if variable else 'mpc-spot-held-arm' if held else 'mpc-spot-unshaped-wide' if wide else 'mpc-spot-unshaped') if variant else 'mpc-spot-'+controller
    cost_variant=controller=='baseline' and a.cost_ablation
    if cost_variant:
        cost=record['costAblation']
        changed={key for key,value in cost['effectiveWeights'].items() if value!=cost['originalWeights'][key]}
        assert changed=={'controls'} and cost['term']=='controls','Expected exactly one changed cost term'
        assert cost['weight']==cost['effectiveWeights']['controls']
        assert cost['originalWeight']==cost['originalWeights']['controls']
        assert settings==dict(armCommandShaping='bounded',armCommandHz=None,commandHoldIntervals=None,armTrustRegion=.35)
        scene='mpc-spot-cost-ablation'
    gain_variant=controller=='baseline' and a.gain_diagnostic
    if gain_variant:
        gain=record['gainDiagnostic']
        assert not record.get('costAblation')
        assert {1,16}<=set(gain['verifiedWorldCounts'])
        assert len(gain['actuators'])==6 and gain['scale']==3
        assert all(v['originalKp']==120 and v['kp']==360 and v['kd']==2 for v in gain['actuators'])
        assert settings==dict(armCommandShaping='bounded',armCommandHz=None,commandHoldIntervals=None,armTrustRegion=.35)
        scene='mpc-spot-high-kp'
    for path in [f'media/{scene}.mp4',f'media/{scene}.png',f'recordings/{scene}.hex.js']:
        assert (root/'assets'/path).is_file(),path
    rows.append(dict(task='Spot + arm',body='spot_arm',controller=controller,scene=scene,group='primary',
        interactionComplete=bool(record['pushReportedSuccess']),
        outcome=f"{record['moved']:.2f} m moved · {record['goalError']:.2f} m goal error · {record['duration']:.1f} s",
        note=record['scope']+' '+('The controller reports completion of the interaction.' if record['pushReportedSuccess'] else 'The controller does not report completion of the interaction.')))
    if controller=='baseline' and not (variant or cost_variant or gain_variant):
        rows[-1]['protocolLabel']='MPC port'
        rows[-1]['note']+=' This is a Spot MPC port with a shared Cartesian contact tracker and joint command shaping, not an unmodified upstream SUMO controller. The displayed interval contains the extended-arm push and excludes stowed navigation.'
    if cost_variant:
        rows[-1].update(originalScene='mpc-spot-baseline',variant='Cost ablation',costAblation=cost)
        rows[-1]['note']+=f" Base-command magnitude weight: {cost['originalWeight']:g} to {cost['weight']:g}. All other cost weights, native command shaping and timing are retained. This is not the original baseline configuration."
    if gain_variant:
        rows[-1].update(originalScene='mpc-spot-baseline',variant='P gain ×3',gainDiagnostic=gain)
        rows[-1]['note']+=' Arm joint Kp changes from 120 to 360. Kd remains 2. Original cost weights, torque limits, leg and gripper gains, command shaping and timing are retained in the real and forecast worlds. This is not the original baseline configuration.'
        if record.get('failedAttempt'):
            rows[-1].update(failedAttempt=True,failureReason=record['failureReason'])
            rows[-1]['outcome']=f"No push · Contact preparation failed · {record['duration']:.1f} s"
    if variant:
        rows[-1].update(originalScene='mpc-spot-baseline',variant='Arm command shaping disabled'+(' · Wider arm range' if wide else ''))
        if held:
            rows[-1]['variant']=f"{settings['armCommandHz']:g} Hz arm command diagnostic"
            rows[-1]['note']+=f" Naive MPC command-rate diagnostic. Arm actuator targets update at {settings['armCommandHz']:g} Hz in both actual and forecast worlds. Physics and base control retain their native rate."
        if variable:
            rows[-1]['variant']='Variable-delay actuation stress test'
            rows[-1]['commandHoldIntervals']=settings['commandHoldIntervals']
            schedule=', '.join(f'{t:g}' for t in settings['commandHoldIntervals'])
            rows[-1]['note']+=f' Arm and base outputs use repeating hold intervals of {schedule} s in both actual and forecast worlds. The physical time step is unchanged.'
        rows[-1]['note']+=' This physical variant disables arm command shaping.'
        if wide:
            rows[-1]['note']+=f" Arm target range is {settings['armTrustRegion']:g} rad instead of 0.35 rad."
        rows[-1]['note']+=' Other task and controller settings are matched. This is a command-setting diagnostic, not the original baseline configuration or a measured optimization speedup.'
(root/'assets/controller-gallery.json').write_text(json.dumps(rows,indent=2)+'\n')
subprocess.run([sys.executable,str(root/'scripts/build_controller_gallery.py')],check=True)
