"""Connect archived G1 training samples to their eight recorded checkpoints."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'assets/locomotion-training-g1.js'
data = json.loads(source.read_text().split('["g1"]=', 1)[1].rstrip(';\n'))
ids = ['terrain', 'regularization']
descriptions = [
    'Adapt a pretrained SUMO walking policy to stairs, slopes and rough terrain.',
    'Continue terrain training with action-rate regularization.',
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
labels = ['Pretrained initialization', 'Terrain adaptation', 'Terrain adaptation', 'Terrain adaptation', 'Action rate regularization', 'Action rate regularization', 'Action rate regularization', 'Action rate regularization']
checkpoints = [dict(id=f'checkpoint-{step}', label=labels[i], replay=dict(
    scene='learning-g1', cumulativeUpdates=step, startTime=i*8, duration=5.5, videoStartOffset=2.5, body='g1',headingTracking=True,trackingEvidence='assets/policy-tracking-g1.json',
    video=f'assets/media/learning-g1-update-{step:05d}.mp4'))
    for i, step in enumerate([0, 100, 500, 17000, 18000, 20000, 21600, 22800])]
result = dict(schema=2, body='g1', source='archived-controller', complete=True,
              checkpointIteration=data['checkpointIteration'], defaultMetricMode='task',
              stages=stages, checkpoints=checkpoints, curves=curves,
              defaultCheckpoint='checkpoint-0',
              intro='G1 adapts a pretrained SUMO walking policy to terrain, then continues with action-rate regularization. Update 0 is pretrained initialization, not a random policy.',
              replayNote='Eight reconstructed checkpoints share a fixed terrain bank: 0, 100, 500, 17,000, 18,000, 20,000, 21,600 and 22,800. Deterministic forward-command evaluations with heading feedback; not footage captured during training.',
              baselineNote='Original training samples at 25-update intervals, plus phase endpoints. Dashed lines mark the first logged value. Resumed runs can restart the terrain curriculum at low levels; a boundary drop alone does not establish a loss of policy skill. Terrain level is a curriculum index (0–9), not a height in metres or a success rate.')
(ROOT / 'assets/g1-restored-data.js').write_text(
    'window.CLEAR_BODY_CURRICULA = window.CLEAR_BODY_CURRICULA || {};\n'
    'window.CLEAR_BODY_CURRICULA["g1"] = '+json.dumps(result, separators=(',', ':'))+';\n')
print(f'Restored {len(curves)} G1 samples and eight matching checkpoints')
