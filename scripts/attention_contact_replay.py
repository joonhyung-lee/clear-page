"""Push-scoped visual contact envelopes; original physical samples stay intact."""
import numpy as np


def active_push(evidence,t):
    return next((w for w in evidence['pushWindows'] if w['start']<=t<w['end']),None)


class ContactReplay:
    """Causal attack/release on opacity, reset at every recorded push boundary."""
    attack=.045
    release=.12

    def __init__(self,evidence):
        self.windows=[]
        self.evidence=evidence
        for window in evidence['pushWindows']:
            rows=[row for row in evidence['frames'] if window['start']<=row['time']<window['end']]
            links=sorted({c['link'] for row in rows for c in row['contacts'] if c['object_id']==window['object_id']})
            tracks=[]
            for link in links:
                alpha=0.;target=0.;previous=window['start'];last=None
                times=[];levels=[];targets=[];items=[];last_times=[];last_time=None
                for row in rows:
                    t=row['time'];tau=self.attack if target else self.release
                    alpha=target+(alpha-target)*np.exp(-(t-previous)/tau)
                    current=next((c for c in row['contacts'] if c['object_id']==window['object_id'] and c['link']==link),None)
                    target=float(current is not None)
                    if current is not None:last=current;last_time=t
                    times.append(t);levels.append(alpha);targets.append(target);items.append(last);last_times.append(last_time)
                    previous=t
                tracks.append((np.asarray(times),levels,targets,items,last_times))
            self.windows.append((window,tracks))

    def at(self,t):
        result=[]
        for window,tracks in self.windows:
            if not window['start']<=t<window['end']:continue
            for times,levels,targets,items,last_times in tracks:
                i=int(np.searchsorted(times,t+1e-8,side='right')-1)
                if i<0 or items[i] is None:continue
                target=targets[i];tau=self.attack if target else self.release
                alpha=target+(levels[i]-target)*np.exp(-(t-times[i])/tau)
                if alpha>.02:
                    result.append(dict(items[i],strength=float(alpha),last_contact_time=last_times[i]))
        return result

    def reference_at(self,t):
        window=active_push(self.evidence,t)
        if window is None:return []
        latest={}
        for item in self.evidence.get('eefTargets',[]):
            if item['object_id']==window['object_id'] and window['start']<=item['time']<=t<min(item['until'],window['end']):
                if item['site'] not in self.evidence['eefSites']:raise ValueError('EEF target site mismatch')
                latest[item['site']]=(item,item['time'])
        return list(latest.values())


_cache={}
def contact_display(evidence,t):
    key=id(evidence)
    if key not in _cache:_cache[key]=(evidence,ContactReplay(evidence))
    return _cache[key][1].at(t)

def reference_anchors(evidence,t):
    key=id(evidence)
    if key not in _cache:_cache[key]=(evidence,ContactReplay(evidence))
    return _cache[key][1].reference_at(t)
