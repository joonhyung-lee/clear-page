"""Export only recorded plan geometry, without source identity metadata."""
import argparse
import json
from pathlib import Path
import numpy as np

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--project',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'attention/videos/video-attention.json').read_text())
names=['e03_highmass_g1_clear','e03_highmass_spot_arm_clear','e03_parallel_terrain_g1_clear']
cases={}
for case,name in zip(data['cases'],names,strict=True):
    original=json.loads((a.project/'visualization/replays/exp3'/name/'planner.json').read_text())
    assert original['body_id']==case['body']
    paths=[]
    objects={o['object_id']:o for o in case['frames'][0]['scene']['objects']}
    for path in original['plan']['paths']:
        obj=objects[path['object_id']]
        assert np.allclose(path['poses'][0],obj['pose'],atol=1e-6)
        paths.append(dict(object_id=path['object_id'],poses=path['poses'],size=obj['size']))
    # The saved execution applies a chord decode and a push margin. Recover
    # its unique raw flow proposal rather than relabeling that chord as flow.
    selected=[];selected_index=None
    if paths:
        margins=[e['margin_m'] for e in original['decision_trace'] if e.get('event')=='push_margin']
        assert len(margins)==1
        matches=[]
        for index,proposal in enumerate(original['raw_proposals']):
            if [p['object_id'] for p in proposal['paths']]!=[p['object_id'] for p in paths]:continue
            errors=[]
            for raw,decoded in zip(proposal['paths'],paths,strict=True):
                start=np.asarray(decoded['poses'][0]);end=np.asarray(decoded['poses'][-1])
                direction=end[:2]-start[:2];direction/=np.linalg.norm(direction)
                expected=end.copy();expected[:2]-=margins[0]*direction
                errors.append(np.linalg.norm(expected-raw['poses'][-1]))
            if max(errors)<1e-6:matches.append((index,proposal))
        assert len(matches)==1,(case['id'],matches)
        selected_index,proposal=matches[0]
        episode=json.loads((a.project/'visualization/replays/exp3'/name/'episode.json').read_text())
        for path in proposal['paths']:
            attempt=next(e for e in episode['attempt_log'] if e['object_id']==path['object_id'])
            selected.append(dict(object_id=path['object_id'],poses=path['poses'],size=objects[path['object_id']]['size'],
                start=attempt['start_time_s'],end=attempt['end_time_s']))
    cases[case['id']]=dict(paths=paths,flowPaths=selected,flowProposalIndex=selected_index,route=original.get('route',[]))
    print('PASS',case['id'],'recorded object order',[p['object_id'] for p in paths])
a.output.write_text(json.dumps(dict(cases=cases,scope='Raw flow proposal uniquely matched to the saved execution endpoints after reversing the logged push margin. Execution used chord decoding. Flow paths are generated references, not measured object motion.'),separators=(',',':'))+'\n')
