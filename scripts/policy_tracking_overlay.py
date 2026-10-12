"""Measured target/actual velocity and heading bases for checkpoint evaluations."""
import copy
import numpy as np
from scipy.spatial.transform import Rotation

class TrackingReplay:
    def __init__(self, path):
        with np.load(path) as data:
            self.data={key:data[key].copy() for key in data.files}
        self.dt=float(self.data['dt'])
        self.frames=self.data['heading'].shape[1]
        self.duration=self.frames*self.dt

    def sample(self, time):
        stage=min(int((time+1e-6)/self.duration),len(self.data['heading'])-1)
        frame=min(int((time-stage*self.duration+1e-6)/self.dt),self.frames-1)
        frame=max(0,frame)
        return {key:value[stage,frame] for key,value in self.data.items() if key!='dt'}

    def metrics(self, time, layout):
        sample=self.sample(time);result=[]
        for entry in layout[::4]:
            agent=entry['sourceAgent'];target=sample['command_world'][agent,:2];actual=sample['velocity_world'][agent,:2]
            heading=float(sample['heading'][agent]);target_heading=np.arctan2(target[1],target[0])
            error=np.arctan2(np.sin(heading-target_heading),np.cos(heading-target_heading))
            result.append(dict(target=float(np.linalg.norm(target)),actual=float(np.linalg.norm(actual)),
                               velocityError=float(np.linalg.norm(actual-target)),headingErrorDegrees=float(np.degrees(abs(error)))))
        return result


def tracking_messages(tracking, start, layout, source_origins, pack):
    selected=np.array([entry['sourceAgent'] for entry in layout])
    angles=np.radians([entry['displayRotationDegrees'] for entry in layout])
    rotations=Rotation.from_euler('z',angles)
    destinations=np.array([entry['displayCenter'] for entry in layout])
    messages=[]
    for slot in range(len(layout)):
        name=f'/heading-basis-{slot}'
        messages.extend([(0.,dict(type='FrameMessage',name=name,props=dict(show_axes=True,
            axes_length=.32,axes_radius=.012,origin_radius=.019,origin_color=[240,240,240],scale=1.))),
            (0.,dict(type='SetSceneNodeVisibilityMessage',name=name,visible=True))])
    def arrow_points(origins,vectors):
        points=[]
        for origin,vector in zip(origins,vectors):
            vector=vector.copy();vector[2]=0.
            speed=np.linalg.norm(vector)
            tip=origin+vector*1.4
            direction=vector/max(speed,1e-8);side=np.array([-direction[1],direction[0],0.])
            head=min(.10,speed*.5)
            points.extend([[origin,tip],[tip,tip-direction*head+side*head*.55],[tip,tip-direction*head-side*head*.55]])
        return np.array(points,dtype='<f4')
    for frame in range(tracking.frames):
        time=start+frame*tracking.dt;sample=tracking.sample(time)
        roots=rotations.apply(sample['root_position'][selected]-source_origins)+destinations
        anchors=roots+np.array([0.,0.,.92])
        heading=sample['heading'][selected]+angles
        for slot,(position,yaw) in enumerate(zip(anchors,heading)):
            name=f'/heading-basis-{slot}'
            messages.extend([(time,dict(type='SetPositionMessage',name=name,position=position.tolist())),
                             (time,dict(type='SetOrientationMessage',name=name,wxyz=Rotation.from_euler('z',yaw).as_quat(scalar_first=True).tolist()))])
        for kind,key,color,offset in [('target','command_world',[217,135,39],.06),('actual','velocity_world',[20,164,184],-.06)]:
            name=f'/tracking-{kind}';points=arrow_points(anchors+[0,0,offset],rotations.apply(sample[key][selected]))
            colors=np.broadcast_to(np.array(color,dtype='u1'),points.shape).copy()
            props=dict(points=pack(points),colors=pack(colors),line_width=4.,scale=1.)
            if frame==0:
                messages.extend([(0.,dict(type='LineSegmentsMessage',name=name,props=copy.deepcopy(props))),
                                 (0.,dict(type='SetSceneNodeVisibilityMessage',name=name,visible=True))])
            messages.append((time,dict(type='SceneNodeUpdateMessage',name=name,updates={k:v for k,v in props.items() if k in ['points','colors']})))
    return messages
