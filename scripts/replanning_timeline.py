"""Causal plan visibility and geometry changes from logged snapshots only."""
import numpy as np

def at_time(data,t):
    visible=[p for p in data['plans'] if p['time']<=t+1e-8]
    if not visible:return dict(current=None,previous=None,changes={},completed=[],fulfilled=[],event=None)
    current=visible[-1];previous=visible[-2] if len(visible)>1 else None
    completed=[a['object_id'] for a in data['attempts'] if a['success'] and a['end_time_s']<=t+1e-8]
    # A later plan may select a previously moved object again. Only attempts
    # dispatched under this plan can fulfill its pending entries.
    fulfilled=[a['object_id'] for a in data['attempts'] if a['success']
               and a['start_time_s']>=current['time']-1e-8 and a['end_time_s']<=t+1e-8]
    now={p['object_id']:p for p in current['paths']};old={} if previous is None else {p['object_id']:p for p in previous['paths']}
    changes={}
    for oid in now.keys()|old.keys():
        if oid not in now:
            since=-np.inf if previous is None else previous['time']
            executed=any(a['object_id']==oid and a['success'] and since<a['end_time_s']<=current['time']+1e-8 for a in data['attempts'])
            changes[oid]='executed' if executed else 'removed'
        elif oid not in old:changes[oid]='added'
        else:
            a=np.asarray(old[oid]['poses']);b=np.asarray(now[oid]['poses'])
            changes[oid]='unchanged' if a.shape==b.shape and np.allclose(a,b,rtol=0,atol=1e-6) else 'changed'
    event=next((e for e in data['events'] if e['start_time_s']<=t<e['end_time_s']),None)
    return dict(current=current,previous=previous,changes=changes,completed=completed,fulfilled=fulfilled,event=event)
