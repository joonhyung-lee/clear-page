import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from types import SimpleNamespace
import numpy as np
from scipy.spatial.transform import Rotation
from contact_surface import ContactSurface
class Scene:
 def add_image(self,name,image,*args,**kwargs):return SimpleNamespace(name=name,**kwargs)
model=SimpleNamespace(geom_type=[6],geom_size=np.array([[.5,.5,.5]]),geom_quat=np.array([[1.,0,0,0]]),geom_pos=np.zeros((1,3)))
surface=ContactSurface(SimpleNamespace(scene=Scene()),model,0,0,'/test',(146,187,145),resolution=3)
errors=[]
for handle,samples,normal in surface.faces:
 # Three.js plane top-left (-w/2, +h/2) is rotated by ViserImage's internal Rx(pi).
 display_rotation=Rotation.from_quat(handle.wxyz,scalar_first=True)*Rotation.from_euler('x',np.pi)
 displayed_top_left=display_rotation.apply([-.5,.5,0])+handle.position
 errors.append(float(np.linalg.norm(displayed_top_left-samples[0])))
print('Texture top-left versus sampled surface point, metres:',errors)
assert max(errors)<1e-10,'Viser image transform mirrors each sampled contact field vertically'

# Check actual serialized textures using the shipped image-plane convention.
import io
from pathlib import Path
from PIL import Image
import numpy as np
from scipy.spatial.transform import Rotation
from recording_io import read_recording
from contact_surface import paired_palm_field
for folder in [str(Path(__file__).resolve().parents[1]/'assets/recordings')]:
 r,buffers=read_recording(Path(folder)/'mpc-stock-optimized.viser')
 def arr(x):return np.frombuffer(buffers[x['__binary_index']],dtype=x['dtype'])
 for time in [2,15,45]:
  state={}
  for t,m in r['messages']:
   if t>time+1e-7:break
   name=m.get('name','');s=state.setdefault(name,{});s.update(m.get('props',{}));s.update(m.get('updates',{}))
   for k in ['position','wxyz','visible']:
    if k in m:s[k]=m[k]
  palms=arr(state['/tracking/palm-centers']['points']).reshape(-1,3);body=state['/tracking/body-31'];rotation=Rotation.from_quat(body.get('wxyz',[1,0,0,0]),scalar_first=True);center=np.array(body['position']);_,targets=paired_palm_field(np.zeros((1,3)),palms,center,rotation.as_matrix(),np.full(3,.5))
  points=[]
  for name,s in state.items():
   if '/palm-contact-field/surface-' not in name or not s.get('visible',True):continue
   rgba=np.asarray(Image.open(io.BytesIO(s['_data'])));rows,cols=np.where(rgba[:,:,3]>155)
   local=np.column_stack([-s['render_width']/2+cols/(rgba.shape[1]-1)*s['render_width'],s['render_height']/2-rows/(rgba.shape[0]-1)*s['render_height'],np.zeros(len(rows))])
   face=Rotation.from_quat(s.get('wxyz',[1,0,0,0]),scalar_first=True)*Rotation.from_euler('x',np.pi)
   points.extend(rotation.apply(face.apply(local)+s['position'])+center)
  error=np.linalg.norm(np.asarray(points)[:,None,:]-targets[None,:,:],axis=2).min(axis=0)
  print(folder,time,'nearest rendered high-score region to each palm projection (m):',error)
  assert max(error)<.035
