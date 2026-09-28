"""Readable path markers shared by explanatory scene exports."""
import numpy as np

def outlined_anchors(server,name,points,color,size):
    # Concentric flat sprites. The foreground sits slightly toward the camera
    # through a child offset in camera-independent world Z for plan views.
    points=np.asarray(points,dtype=np.float32)
    border=server.scene.add_point_cloud(name+'-outline',points=points,colors=(25,27,26),point_size=size*1.22,point_shape='circle',point_shading='flat',precision='float32')
    fill=server.scene.add_point_cloud(name,points=points+np.array([0,0,.004],np.float32),colors=color,point_size=size,point_shape='circle',point_shading='flat',precision='float32')
    return border,fill

def set_anchors(handles,points):
    points=np.asarray(points,dtype=np.float32);handles[0].points=points;handles[1].points=points+np.array([0,0,.004],np.float32)

def path_anchors(xy,count=4,z=.1):
    xy=np.asarray(xy);length=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
    return np.column_stack([np.interp(np.linspace(0,length[-1],count),length,xy[:,j]) for j in range(2)]+[np.full(count,z)]).astype(np.float32)
