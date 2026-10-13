"""Change recorded material colors only; retain geometry, poses, and clocks."""
import colorsys
import copy
import re
import numpy as np
from design_tokens import rgb

OBJECT_FAMILIES = ('blue', 'purple', 'mint', 'red', 'gray', 'green')
TERRAIN_FAMILIES = {'flat':'gray','stairs_up':'blue','stairs_down':'mint',
                    'slope_up':'green','slope_down':'purple','random_rough':'red'}

def mapped_color(values, name=''):
    values = tuple(int(v) for v in values)
    if len(values) != 3: return values
    h, s, v = colorsys.rgb_to_hsv(*(x/255 for x in values))
    if v < .08 or (s < .03 and v > .97): return values
    if s < .12:
        shade = min((100,200,300,400,500,600,700,800,900),
                    key=lambda k: abs(max(rgb('gray',k))/255-v))
        return rgb('gray',shade)
    lower = name.lower()
    if re.search(r'body-\d|robot.*mesh|/visual-',lower):
        return rgb('gray',300 if v>.6 else 700)
    for terrain,family in TERRAIN_FAMILIES.items():
        if terrain in lower: return rgb(family,100)
    match = re.search(r'(?:object|force)[-_/](\d+)',lower)
    if any(word in lower for word in ('target','goal','actual','highlight','capability','accessibility')):
        family = 'green'
    elif match:
        family = OBJECT_FAMILIES[int(match[1])%len(OBJECT_FAMILIES)]
    else:
        hue = h*360
        family = ('red' if hue<55 or hue>=335 else 'green' if hue<160 else
                  'mint' if hue<200 else 'blue' if hue<270 else 'purple')
    shade = 100 if s<.22 and v>.8 else 200 if s<.38 and v>.75 else 400 if v>.7 else 600
    return rgb(family,shade)

def restyle(record, buffers):
    record = copy.deepcopy(record); buffers = list(buffers); cache = {}
    for _,message in record['messages']:
        name = message.get('name','')
        if message['type'] in ('AmbientLightMessage','DirectionalLightMessage','PointLightMessage'):
            continue
        for field in ('props','updates'):
            props = message.get(field,{})
            for key in ('color','colors','batched_colors'):
                value = props.get(key)
                if isinstance(value,(list,tuple)) and len(value)==3 and all(isinstance(v,(int,float)) for v in value):
                    props[key] = mapped_color(value,name)
                elif isinstance(value,dict) and '__binary_index' in value:
                    cache_key=(value['__binary_index'],name)
                    if cache_key not in cache:
                        old=np.frombuffer(buffers[value['__binary_index']],dtype=value['dtype'])
                        if old.size%3:continue
                        unit=1 if old.dtype.kind=='f' and old.max(initial=0)<=1 else 255
                        data=old.reshape(-1,3);unique,inverse=np.unique(data,axis=0,return_inverse=True)
                        # Promote byte colors before scaling to avoid uint8 wraparound.
                        new=np.array([mapped_color(row.astype(float)*255/unit,name) for row in unique])*unit/255
                        output=np.ascontiguousarray(new[inverse].astype(old.dtype))
                        cache[cache_key]=dict(value,__binary_index=len(buffers));buffers.append(output.tobytes())
                    props[key]=dict(cache[cache_key])
    return record,buffers
