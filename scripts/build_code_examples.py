"""Render two distinct evidence views from existing recorded data, without inference."""
import json
from pathlib import Path
from html import escape
ROOT=Path(__file__).resolve().parents[1]

def read(name):
    s=(ROOT/'assets'/name).read_text()
    return json.loads(s[s.index('{'):].rstrip().removesuffix(';'))

def draw(scene, selected, paths, title, subtitle):
    w,h=scene['world_size']
    points=[(0,0),(w,h)] + [pose[:2] for path in paths for pose in path['poses']]
    points += [(l,b) for l,b,r,t in scene['walls']] + [(r,t) for l,b,r,t in scene['walls']]
    xmin,xmax=min(p[0] for p in points),max(p[0] for p in points)
    ymin,ymax=min(p[1] for p in points),max(p[1] for p in points)
    scale=min(610/(xmax-xmin),390/(ymax-ymin))
    ox=(720-(xmax-xmin)*scale)/2-xmin*scale;oy=465+ymin*scale
    xy=lambda p:(ox+p[0]*scale,oy-p[1]*scale)
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 510" role="img" aria-label="{escape(title)}"><rect width="720" height="510" fill="#f7f9f3"/><g font-family="Arial" fill="#35462f"><text x="24" y="30" font-size="19">{escape(title)}</text><text x="24" y="53" font-size="14">{escape(subtitle)}</text>']
    for t in scene.get('terrain',[]):
        l,b,r,top=t['bounds'];x,y=xy((l,top));out.append(f'<rect x="{x}" y="{y}" width="{(r-l)*scale}" height="{(top-b)*scale}" fill="#e7eadb" stroke="#b9c6b4"/>')
    for l,b,r,top in scene['walls']:
        x,y=xy((l,top));out.append(f'<rect x="{x}" y="{y}" width="{(r-l)*scale}" height="{(top-b)*scale}" fill="#b8c0b0"/>')
    for o in scene['objects']:
        i=o['object_id'];x,y=xy(o['pose']);a,b=o['size'][:2];color='#4f7543' if i in selected else '#9da994'
        out.append(f'<rect x="{x-a*scale/2}" y="{y-b*scale/2}" width="{a*scale}" height="{b*scale}" fill="{color}" stroke="#334c2c" stroke-width="2"/><text x="{x+17}" y="{y-12}" font-size="15">Object {i}</text>')
    for path in paths:
        points=[xy(p) for p in path['poses']];line=' '.join(f'{x},{y}' for x,y in points)
        out.append(f'<polyline points="{line}" fill="none" stroke="#b36b4b" stroke-width="3" stroke-dasharray="6 3"/>')
        for j,(x,y) in enumerate(points):
            out.append(f'<circle cx="{x}" cy="{y}" r="3" fill="#fff" stroke="#b36b4b"><title>Object {path["object"]}, waypoint {j}</title></circle>')
    for label,point in [('Start',scene['start']),('Goal',scene['goal'])]:
        x,y=xy(point);out.append(f'<circle cx="{x}" cy="{y}" r="6" fill="white" stroke="#354f2d" stroke-width="2"/><text x="{x+10}" y="{y+4}" font-size="15">{label}</text>')
    out.append('</g></svg>');return ''.join(out)

def build():
    sample=next(s for s in read('learning-samples.js')['ordering'] if s['id']==16)
    selected=[o['object_id'] for o,r in zip(sample['scene']['objects'],sample['rank']) if r>=0]
    (ROOT/'assets/code-example-ordering.svg').write_text(draw(sample['scene'],selected,[],
        'Object participation','G1 · recorded training sample · reference order: Object 1 → Object 2'))
    trace=read('maze-method-trace.js');run=trace['referenceFlow'][0]
    assert run['refinement']==[{'object':0,'refined':False}]
    (ROOT/'assets/code-example-validation.svg').write_text(draw(trace['scene'],[0],run['states'][-1],
        'Clearance check: rejected','Object 0 · saved generated path · no valid refined path'))
    attention=json.loads((ROOT/'attention/attention.json').read_text())
    frames=[]
    for frame in attention['cases'][0]['frames']:
        rows=[query for layer in frame['encoder'] for head in layer for query in head]
        weights=[sum(row[k] for row in rows)/len(rows) for k in range(len(frame['keys']))]
        assert abs(sum(weights)-1)<1e-5
        frames.append(dict(scene=frame['scene'],keys=frame['keys'],weights=weights,time=frame['time']))
    teaser=read('teaser-flow-data.js')
    payload=dict(attention=frames,ordering={k:sample[k] for k in ['scene','rank','selection','mu','sigma','rollout']},
                 grid=read('flow-learning-data.js'),teaser={k:teaser[k] for k in ['scene','conditionedOrder','referenceFlow','diagnostics']})
    (ROOT/'assets/code-example-data.js').write_text('window.CLEAR_CODE_EXAMPLES='+json.dumps(payload,separators=(',',':')).replace('<','\\u003c')+';\n')
    return sample

if __name__=='__main__':build()
