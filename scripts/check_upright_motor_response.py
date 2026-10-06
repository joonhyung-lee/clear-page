"""Reject an upright walker that drifts, falls or cannot reverse on empty floor."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

p = argparse.ArgumentParser()
p.add_argument('--result', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
record = json.loads(a.result.read_text())
samples = record['samples']
summary, failures = {}, []
for phase in ('raise_and_settle', 'forward', 'stop', 'reverse', 'settle'):
    rows = [r for r in samples if r['phase'] == phase]
    if len(rows) < 10:
        failures.append(phase+': insufficient observations')
        continue
    tail = rows[-10:]
    yaw = np.asarray([r['pose'][2] for r in tail])
    xy_velocity = np.asarray([r['velocity_world'][:2] for r in tail])
    body_forward = xy_velocity[:, 0]*np.cos(yaw)+xy_velocity[:, 1]*np.sin(yaw)
    target = rows[-1]['requested_forward_m_s']
    summary[phase] = dict(requested_m_s=target, measured_forward_m_s=float(body_forward.mean()),
                          horizontal_speed_m_s=float(np.linalg.norm(xy_velocity, axis=1).mean()),
                          minimum_root_height_m=min(r['root_z'] for r in rows))
    if summary[phase]['minimum_root_height_m'] < .67:
        failures.append(phase+': upright height lost')
    if abs(float(body_forward.mean())-target) > .08:
        failures.append(phase+': velocity tracking failed')
    if target == 0 and summary[phase]['horizontal_speed_m_s'] > .05:
        failures.append(phase+': did not stop')
if max(abs(r['pose'][2]) for r in samples) > .35:
    failures.append('uncommanded heading drift')
report = dict(qualified=not failures, failures=failures, phases=summary,
              source_sha256=hashlib.sha256(a.result.read_bytes()).hexdigest(),
              arm_observation=record['arm_observation'], gravity_support=record.get('gravity_support', False),
              arm_reference_sha256=record.get('arm_reference_sha256'),
              crouch_offsets=record.get('crouch_offsets'), checkpoints=record.get('checkpoints', {}))
a.output.write_text(json.dumps(report, indent=2)+'\n')
print(('PASS' if report['qualified'] else 'FAIL')+' upright motor response: '+', '.join(failures))
raise SystemExit(0 if report['qualified'] else 1)
