"""Render a source-geometry poster for the teaser explanation, without a server."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial.transform import Rotation
from recording_io import read_recording
from render_learning_posters import raster


def render(source, output):
    record,buffers=read_recording(source)
    meshes={};positions={};rotations={};labels={};camera={}
    for t,m in record['messages']:
        if t>0:continue
        name=m.get('name');kind=m['type']
        if kind=='MeshMessage':meshes[name]=m['props']
        elif kind=='SetPositionMessage':positions[name]=m['position']
        elif kind=='SetOrientationMessage':rotations[name]=m['wxyz']
        elif kind=='LabelMessage':labels[name]=m['props']['text']
        elif kind in ['SetCameraPositionMessage','SetCameraLookAtMessage','SetCameraFovMessage']:camera.update(m)
    w,h=1200,950;eye=np.array(camera['position']);target=np.array(camera['look_at'])
    forward=target-eye;forward/=np.linalg.norm(forward)
    right=np.cross(forward,[0,0,1.]);right/=np.linalg.norm(right)
    basis=np.stack([right,np.cross(right,forward),forward],axis=1)
    focal=h/(2*np.tan(camera['fov']/2))
    def project(vertices):
        local=(vertices-eye)@basis
        return np.column_stack([w/2+local[:,0]/local[:,2]*focal,h/2-local[:,1]/local[:,2]*focal,local[:,2]])
    depth=np.full((h,w),np.inf);pixels=np.full((h,w,3),248.,dtype=float)
    light=np.array([.2,-.5,1.]);light/=np.linalg.norm(light)
    for name,p in meshes.items():
        if name.startswith('/order/'):continue
        vertices=np.frombuffer(buffers[p['vertices']['__binary_index']],dtype='<f4').reshape(-1,3)
        faces=np.frombuffer(buffers[p['faces']['__binary_index']],dtype='<u4').reshape(-1,3)
        vertices=Rotation.from_quat(rotations.get(name,[1,0,0,0]),scalar_first=True).apply(vertices)+positions.get(name,[0,0,0])
        triangle=vertices[faces];normal=np.cross(triangle[:,1]-triangle[:,0],triangle[:,2]-triangle[:,0])
        normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-12)
        shades=.77+.23*np.abs(normal@light)
        color=np.array(p['color'],dtype=float);alpha=p.get('opacity',1.)
        # Translucent borders are omitted from the poster to reveal the lanes.
        if alpha<.3:continue
        color=alpha*color+(1-alpha)*248.
        raster(project(vertices),faces,shades,depth,pixels,color)
    image=Image.fromarray(pixels.astype('uint8'));draw=ImageDraw.Draw(image)
    for name,text in labels.items():
        if name.startswith('/order/'):continue
        point=project(np.array([positions[name]]))[0]
        x,y=point[:2];box=draw.textbbox((x,y),text)
        draw.rectangle((box[0]-3,box[1]-2,box[2]+3,box[3]+2),fill='#f8faf7')
        draw.text((x,y),text,fill='#3e5146')
    image.save(output)
    print('Rendered teaser source geometry:',output)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();render(a.source,a.output)
