"""Publish a complete, internally consistent run with Availability enabled."""
import argparse,hashlib,json,math,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def export(run):
    protocol=json.loads((run/'protocol.json').read_text())
    config=protocol['config'];weight=config['model']['availability_weight']
    complete=json.loads((run/'complete.json').read_text())
    if weight<=0 or complete['step']!=config['steps']:raise ValueError('Availability-enabled training must be complete')
    if hashlib.sha256((run/'last.pt').read_bytes()).hexdigest()!=complete['checkpoint_sha256']:raise ValueError('Completion checkpoint hash mismatch')
    metrics=['loss','selection','order','kl','flow','affordance','availability']
    rows=[]
    for line in (run/'training.jsonl').read_text().splitlines():
        row=json.loads(line)
        if 'loss' not in row:continue
        values={key:row[key] for key in ['step',*metrics]}
        if not all(math.isfinite(v) for v in values.values()):raise ValueError('Nonfinite recorded value')
        total=row['selection']+row['order']+.001*row['kl']+row['flow']+row['affordance']+weight*row['availability']
        if not math.isclose(total,row['loss'],abs_tol=3e-6,rel_tol=3e-6):raise ValueError(f'Components disagree at step {row["step"]}')
        if rows and values['step']<=rows[-1]['step']:raise ValueError('Duplicate or unordered steps')
        rows.append(values)
    if not rows or rows[-1]['step']!=config['steps']:raise ValueError('Last training row missing')
    target=ROOT/'assets/training-loss-data.js'
    backup=ROOT/'.git/training-before-availability';backup.mkdir(exist_ok=True)
    if not (backup/target.name).exists():shutil.copyfile(target,backup/target.name)
    payload=dict(samples=rows,maxStep=rows[-1]['step'],window=21,weights=dict(kl=.001,flow=1,affordance=1,availability=weight),complete=True,
                 source=dict(trainingLogSHA256=hashlib.sha256((run/'training.jsonl').read_bytes()).hexdigest(),protocolSHA256=hashlib.sha256((run/'protocol.json').read_bytes()).hexdigest(),checkpointSHA256=complete['checkpoint_sha256']))
    staged=target.with_suffix('.js.tmp');staged.write_text('window.CLEAR_TRAINING_LOSSES='+json.dumps(payload,separators=(',',':'),allow_nan=False)+';\n');staged.replace(target)
    (ROOT/'.git/training-loss-sources.json').write_text(json.dumps(dict(input=str(run/'training.jsonl'),publishedSamples=len(rows),lastStep=rows[-1]['step'],**payload['source']),indent=2)+'\n')
    print(f'Published {len(rows)} rows, six components, Availability weight {weight}',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();export(a.run)
