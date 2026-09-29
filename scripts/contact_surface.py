"""Project observed contact scores onto the physical box surface, not splats.

Textures contain only visible RGB-D returns. Depth and segmentation gates prevent
filling occluded regions. Interpolation is display smoothing of learned scores.
"""
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from scipy.ndimage import map_coordinates

class ContactSurface:
 def __init__(self,server,model,geom,body,prefix,color,resolution=128,offset=.002):
  self.geom=geom;self.color=np.asarray(color);self.faces=[];self.resolution=resolution
  assert int(model.geom_type[geom])==6,'Contact surface export requires a box'
  half=model.geom_size[geom];local_rotation=Rotation.from_quat(model.geom_quat[geom],scalar_first=True)
  for axis in range(3):
   for sign in [-1,1]:
    n=np.eye(3)[axis]*sign;u=np.eye(3)[(axis+1)%3];v=np.cross(n,u)
    rotation=np.column_stack([u,v,n]);center=n*(half[axis]+offset)
    ru=half[(axis+1)%3];rv=half[(axis+2)%3]
    xx,yy=np.meshgrid(np.linspace(-ru,ru,resolution),np.linspace(rv,-rv,resolution))
    local=center+xx[:,:,None]*u+yy[:,:,None]*v
    # ViserImage rotates its XY mesh by Rx(pi). Cancel that rotation so
    # texture row zero lands on the +v samples above, rather than mirroring them.
    handle=server.scene.add_image(prefix+f'/surface-{axis}-{sign}',np.zeros((resolution,resolution,4),np.uint8),2*ru,2*rv,format='png',cast_shadow=False,receive_shadow=False,position=local_rotation.apply(center)+model.geom_pos[geom],wxyz=(local_rotation*Rotation.from_matrix(rotation)*Rotation.from_euler('x',np.pi)).as_quat(scalar_first=True),visible=False)
    self.faces.append((handle,local.reshape(-1,3),n))
 def hide(self):
  for handle,_,_ in self.faces:handle.visible=False
 def update(self,data,cam,intrinsic,depth,mask,heat_image,alpha=195,outline=False):
  h,w=depth.shape;rotation=data.geom_xmat[self.geom].reshape(3,3);camera_rotation=data.cam_xmat[cam].reshape(3,3)
  for handle,local,normal in self.faces:
   world=local@rotation.T+data.geom_xpos[self.geom]
   facing=np.dot(data.cam_xpos[cam]-world.mean(0),rotation@normal)>0
   if not facing:handle.visible=False;continue
   camera=(world-data.cam_xpos[cam])@camera_rotation*np.array([1,-1,-1]);z=camera[:,2];projection=camera@intrinsic.T
   uv=projection[:,:2]/np.maximum(z[:,None],1e-8)
   inside=(z>0)&(uv[:,0]>=0)&(uv[:,0]<w-1)&(uv[:,1]>=0)&(uv[:,1]<h-1)
   coords=np.stack([uv[:,1],uv[:,0]])
   visible=inside&(map_coordinates(mask.astype(float),coords,order=0,mode='constant',cval=0)>.5)&(abs(map_coordinates(depth,coords,order=1,mode='constant',cval=0)-z)<.02)
   heat=map_coordinates(heat_image,coords,order=1,mode='constant',cval=0)
   rgba=np.empty((len(local),4),np.uint8);rgba[:,:3]=self.color;rgba[:,3]=np.round(visible*np.clip(heat,0,1)*alpha).astype(np.uint8)
   if outline:
    ring=(heat>.48)&(heat<.64)&visible;rgba[ring,:3]=(35,39,39);rgba[ring,3]=230
   handle.visible=bool(np.any(rgba[:,3]>2))
   if handle.visible:handle.image=rgba.reshape(self.resolution,self.resolution,4)

def smooth_scores(world,sampled,intensity):
 distance,index=cKDTree(sampled).query(world,k=8)
 weights=np.exp(-distance**2/(2*.025**2))+1e-12
 return np.sum(weights*intensity[index],axis=1)/weights.sum(axis=1)

def paired_palm_field(world, palms, center, rotation, half, radius=.07):
 """Two geometric palm neighborhoods on the box, separate from learned scores.

Project each recorded palm to its closest box face. The display is a contact
neighborhood, not a force estimate or evidence that physical contact occurred.
 """
 local=(np.asarray(palms)-center)@rotation
 projected=np.clip(local,-half,half)
 for i in range(2):
  if np.all(abs(local[i])<=half):
   axis=int(np.argmin(half-abs(local[i])))
   projected[i,axis]=half[axis]*(1 if local[i,axis]>=0 else -1)
 centers=projected@rotation.T+center
 distances=np.linalg.norm(np.asarray(world)[:,None,:]-centers[None,:,:],axis=-1)
 field=np.exp(-distances**2/(2*radius**2))
 return field.max(axis=1),centers
