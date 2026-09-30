"""Capture actual optimization checkpoints from the unchanged CLEAR training runner.

This is a new CPU training lineage, separate from published historical losses.
Keep all weights and source paths in a private output directory.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('project',type=Path)
p.add_argument('config',type=Path)
p.add_argument('output',type=Path)
p.add_argument('--steps',type=int,nargs='+',default=[20,100,500,1000])
a=p.parse_args()
project=a.project.resolve();config=json.loads(a.config.read_text());output=a.output.resolve()
assert config['device']=='cpu' and config['arm']=='A'
assert sorted(set(a.steps))==a.steps
output.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(project));os.chdir(project)
spec=importlib.util.spec_from_file_location('clear_original_training',project/'scripts/leap2026/train_joint_matching.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
import torch
run=output/'run';manifest=output/'checkpoints.json'
records=json.loads(manifest.read_text()) if manifest.exists() else []
for step in a.steps:
    target=output/f'step-{step}.pt'
    if target.exists():
        ck=torch.load(target,map_location='cpu',weights_only=False)
        assert ck['step']==step
        continue
    last=run/'last.pt'
    current=torch.load(last,map_location='cpu',weights_only=False)['step'] if last.exists() else 0
    if current>step:raise ValueError(f'Historical step {step} was not preserved')
    if current<step:module.train(config,run,stop_after=step)
    ck=torch.load(last,map_location='cpu',weights_only=False)
    assert ck['step']==step
    shutil.copy2(last,target)
    records.append(dict(step=step,file=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                        protocolSHA256=ck['protocol_sha256'],wallSeconds=ck['wall_seconds']))
    manifest.write_text(json.dumps(records,indent=2)+'\n')
    print('CAPTURED',step,flush=True)
