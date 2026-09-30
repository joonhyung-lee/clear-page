"""Verify physical separation, policy dimensions and saved initialization identity."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from bare_spot import get_spec

p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
m=get_spec().compile()
assert (m.nq,m.nv)==(19,18)
assert all('arm' not in m.body(i).name for i in range(m.nbody))
assert all('arm' not in m.geom(i).name for i in range(m.ngeom))
plan=json.loads((a.run/'plan.json').read_text());assert plan['body']=='spot'
assert [s['name'] for s in plan['stages']]==['locomotion','terrain']
initial=torch.load(a.run/'locomotion/update_000000.pt',map_location='cpu',weights_only=False)
assert initial['infos']['curriculum']['body']=='spot'
assert initial['infos']['curriculum']['before_first_optimizer_update']
assert not initial['optimizer_state_dict']['state']
contract=json.loads((a.run/'locomotion/body.json').read_text())
assert contract['observations']==48 and contract['actuators']==12 and contract['armJoints']==0
replays=json.loads((a.run/'web-replays-spot.json').read_text())
for r in replays.values():
 assert r['body']=='spot'
 archive=a.run/'web-replays'/r['scene']
 g=np.load(archive/'spot-geometry.npz')
 assert all('arm' not in name for name in g['body_names'])
 audit=json.loads((archive/'spot-audit.json').read_text())
 assert audit['physicalBody']=='spot' and audit['arm'] is None
print('PASS bare Spot has no arm physics or visual geoms, 48 observations / 12 actuators, pristine update zero, matching native replay geometry')
