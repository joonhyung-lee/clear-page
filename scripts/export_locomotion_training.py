"""Export numeric training evidence along the exact ancestry of deployed checkpoints."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import torch
import yaml
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

p=argparse.ArgumentParser()
p.add_argument('--archive',type=Path,required=True)
p.add_argument('--provenance',type=Path,required=True)
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
sources=json.loads(a.provenance.read_text())
tags={'value':'Loss/value','policy':'Loss/surrogate','entropy':'Loss/entropy','reward':'Train/mean_reward','terrain':'Curriculum/terrain_levels/mean','tracking':'Metrics/twist/error_vel_xy','arm':'Curriculum/arm_stow/mean'}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def config(run):return yaml.load((run/'params/agent.yaml').read_text(),Loader=yaml.BaseLoader)

def ancestry(run, end, seen=None):
    seen=set() if seen is None else seen
    assert run not in seen
    seen.add(run)
    cfg=config(run)
    seed=run.parent/cfg.get('load_run','')/cfg.get('load_checkpoint','')
    start=0;older=[]
    if cfg.get('resume')=='true' and seed.is_file():
        start=int(torch.load(seed,map_location='cpu',weights_only=False)['iter'])
        parent=seed.parent
        if not (parent/'params/agent.yaml').exists():
            digest=sha(seed)
            matches=[f.parent for f in a.archive.glob(f'*/*/model_{start}.pt') if f!=seed and (f.parent/'params/agent.yaml').exists() and sha(f)==digest]
            parent=matches[0] if matches else None
        if parent is not None:
            older=ancestry(parent,start-1,seen)
    return older+[(run,start,end)]

public={};audit={}
for body,source in sources.items():
    checkpoint=Path(source['matches'][0]);assert sha(checkpoint)==source['sha256']==sha(Path(source['checkpoint']))
    end=int(checkpoint.stem.split('_')[-1]);lineage=ancestry(checkpoint.parent,end)
    if body=='g1':
        phases=[dict(label='Terrain adaptation',start=0,end=17099),dict(label='Action rate regularization',start=17100,end=end)]
    else:
        phases=[dict(label='Mixed terrain',start=0,end=6999),dict(label='Torso control',start=7000,end=min(end,13199 if body=='spot_arm' else end))]
        if body=='spot_arm':phases.append(dict(label='Arm pose curriculum',start=13200,end=end))
    raw={};run_audit=[]
    for run,start,stop in lineage:
        if stop<start:continue
        ea=EventAccumulator(str(run),size_guidance={'scalars':0});ea.Reload()
        available=ea.Tags()['scalars']
        for key,tag in tags.items():
            if tag not in available:continue
            for event in ea.Scalars(tag):
                if start<=event.step<=stop:
                    row=raw.setdefault(event.step,{'step':event.step})
                    row[key]=event.value if math.isfinite(event.value) else None
        run_audit.append(dict(run=str(run),start=start,end=stop,events=[dict(path=str(f),sha256=sha(f)) for f in run.glob('events.out*')]))
    assert raw and max(raw)==end,(body,end,max(raw))
    # Preserve exact recorded points, checkpoint/stage endpoints and a light 25-step sampling.
    important={min(raw),end,*[v for phase in phases for v in [phase['start'],phase['end']]]}
    rows=[]
    for step,row in sorted(raw.items()):
        if step%25 and step not in important:continue
        phase=next(i for i,x in enumerate(phases) if x['start']<=step<=x['end'])
        rows.append([step,phase,*[row.get(key) for key in tags]])
    public[body]=dict(columns=['step','phase',*tags],samples=rows,phases=phases,checkpointIteration=end,sampleStride=25)
    audit[body]=dict(checkpoint=source['checkpoint'],sha256=source['sha256'],lineage=run_audit,sourceIterations=len(raw),publishedSamples=len(rows))
    print(body,len(raw),'iterations ->',len(rows),'display samples',flush=True)
    (root/f'assets/locomotion-training-{body}.js').write_text('window.CLEAR_LOCOMOTION_DATA=window.CLEAR_LOCOMOTION_DATA||{};window.CLEAR_LOCOMOTION_DATA['+json.dumps(body)+']='+json.dumps(public[body],separators=(',',':'),allow_nan=False)+';\n')
(root/'.git/locomotion-training-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
