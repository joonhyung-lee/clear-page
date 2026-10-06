"""Display continuity and push-only contact replay regression."""
import json
from pathlib import Path
from attention_contact_replay import contact_display,reference_anchors,active_push

cases=json.loads((Path(__file__).resolve().parents[1]/'attention/videos/contact-evidence.json').read_text())['cases']
case=cases['sample-54']
def left(t):
    return next((c['strength'] for c in contact_display(case,t) if c['link']=='left_wrist_yaw_link'),0.)
a,b=left(22.66),left(22.74)
outside=[]
for name,evidence in cases.items():
    for row in evidence['frames']:
        for item in contact_display(evidence,row['time']):
            if not any(w['object_id']==item['object_id'] and w['start']<=row['time']<w['end'] for w in evidence['pushWindows']):
                outside.append((name,row['time'],item['link']))
print('Left contact opacity across 80 ms:',a,'->',b)
print('Visible contacts outside pushing:',len(outside),'first:',outside[:3])
assert not outside,'Contact highlight leaks into release/retreat'
assert 0<b<a and a-b<.65,'Contact highlight hard-switches off during a short gap'
for name,evidence in cases.items():
    for window in evidence['pushWindows']:
        assert not contact_display(evidence,window['end'])
        assert not reference_anchors(evidence,window['end'])
        assert active_push(evidence,window['end']) is None
        assert not reference_anchors(evidence,window['end']-.01), 'Invented EEF target'
        assert not reference_anchors(evidence,window['start']), 'Invented EEF target'
# Only an explicit, same-site, valid recorded target can produce a guide.
fixture=dict(case,eefTargets=[dict(time=22.5,until=23.,site='left_palm',object_id=1,position=[3.,3.,.8])])
assert not reference_anchors(fixture,22.4)
assert reference_anchors(fixture,22.6)==[(fixture['eefTargets'][0],22.5)]
assert not reference_anchors(fixture,23.)
print('PASS exact push boundaries, recorded-only EEF references and causal display fade')
