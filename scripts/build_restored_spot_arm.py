"""Adapt the archived controller's matching logs and eight native replay segments."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'assets/locomotion-training-spot_arm.js').read_text()
data = json.loads(source.split('["spot_arm"]=', 1)[1].rstrip(';\n'))
ids = ['locomotion', 'terrain', 'arm']
descriptions = [
    'Locomotion training on mixed terrain.',
    'Continue mixed-terrain locomotion with torso control.',
    'Adapt locomotion to an expanding range of arm postures.',
]
stages = []
for i, phase in enumerate(data['phases']):
    end = data['phases'][i + 1]['start'] if i + 1 < len(ids) else data['checkpointIteration']
    stages.append(dict(id=ids[i], label=phase['label'], description=descriptions[i],
                       state='complete', updates=end-phase['start'],
                       targetUpdates=end-phase['start'], cumulativeUpdates=end, replay=None))
curves = []
for sample in data['samples']:
    row = dict(zip(data['columns'], sample))
    row['update'] = row.pop('step')
    row['stage'] = ids[row.pop('phase')]
    row['return'] = row.pop('reward')
    curves.append(row)
checkpoints = [dict(id=f'checkpoint-{step}', label=('Initialization' if step==0 else 'Mixed terrain' if step<7000 else 'Torso control' if step<13200 else 'Arm pose curriculum'), replay=dict(
    scene='learning-spot_arm', cumulativeUpdates=step, startTime=i*8, duration=8,
    body='spot_arm',headingTracking=True,trackingEvidence='assets/policy-tracking-spot_arm.json',video=f'assets/media/learning-spot_arm-update-{step:05d}.mp4')) for i, step in enumerate([0, 4000, 7000, 10000, 13200, 18000, 22600, 28000])]
result = dict(schema=2, body='spot_arm', source='archived-controller', numEnvironments=32,
              complete=True, stages=stages, checkpoints=checkpoints, curves=curves,
              defaultCheckpoint='checkpoint-28000',
              intro='Recorded Spot + arm controller training on mixed terrain, followed by torso control and arm pose adaptation.',
              replayNote='Eight checkpoint replays span mixed-terrain locomotion, torso control and arm pose adaptation.',
              baselineNote='Dashed lines mark the first logged value. Curves show the archived training record.')
target = ROOT / 'assets/spot_arm-restored-data.js'
target.write_text('window.CLEAR_BODY_CURRICULA = window.CLEAR_BODY_CURRICULA || {};\n'
                  'window.CLEAR_BODY_CURRICULA["spot_arm"] = '+json.dumps(result, separators=(',', ':'))+';\n')
print(f'Restored {len(curves)} archived samples and eight Spot + arm checkpoints')
