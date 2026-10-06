"""Project recorded flow geometry and derived contact guides into replay views."""
import numpy as np
from PIL import Image, ImageDraw
from attention_contact_replay import reference_anchors

FLOW=(70,130,230)
GUIDE=(255,169,42)
CONTACT=(220,48,62)
EEF_COLORS=((194,38,64),(234,91,107))

def draw_contact_field(image,camera,rect,item):
    """Soft red display emphasis at a recorded contact, not a probability field."""
    x0,y0,width,height=rect
    c=camera @ np.r_[item['position'],1.]
    layer=Image.new('RGBA',(width,height))
    if c[3]>0:
        x=(c[0]/c[3]+1)*width/2;y=(1-c[1]/c[3])*height/2
        yy,xx=np.mgrid[:height,:width]
        radius=((xx-x)/17.)**2+((yy-y)/17.)**2
        alpha=np.where(radius<16,205*item.get('strength',1.)*np.exp(-.5*radius),0).astype('uint8')
        layer=Image.new('RGBA',(width,height),(*CONTACT,0))
        layer.putalpha(Image.fromarray(alpha))
    image.paste(layer,(x0,y0),layer)
    return layer.getchannel('A')

def draw_query_marker(image,point,kind,size):
    """Teaser-style bullseye and map pin; pin tip is the exact goal."""
    # Draw at 4x resolution for readable small minimap markers.
    n=128;layer=Image.new('RGBA',(n,n));draw=ImageDraw.Draw(layer)
    dark=(26,28,32,255) if kind=='start' else (16,17,20,255)
    light=(243,246,250,255)
    if kind=='start':
        for radius,color in [(61,light),(53,dark),(40,light),(27,dark),(14,light),(6,dark)]:
            draw.ellipse((64-radius,64-radius,64+radius,64+radius),fill=color)
    else:
        neck=76.;radius=37.;angle=np.arcsin(radius/neck)
        arc=np.linspace(-angle,np.pi+angle,64)
        points=[(64,124)]+[(64+radius*np.cos(t),124-neck-radius*np.sin(t)) for t in arc]
        draw.polygon(points,fill=dark)
        draw.line(points+[points[0]],fill=light,width=4)
        draw.ellipse((48,32,80,64),fill=light)
    layer=layer.resize((size,size),Image.Resampling.LANCZOS)
    x,y=point
    y-=size/2 if kind=='start' else size*124/n
    image.paste(layer,(round(x-size/2),round(y)),layer)

def draw_minimap_path(draw,project,path):
    if not path:return
    poses=np.asarray(path['poses'])
    points=[project(p[:2]) for p in poses]
    draw.line(points,fill=FLOW,width=2)
    for x,y in points:
        draw.polygon([(x,y-2),(x+2,y),(x,y+2),(x-2,y)],fill='#fafbf8',outline=FLOW)
    for track in corner_tracks(path,upper=False):
        draw.line([project(p) for p in track],fill='#92b1e6',width=1)
    for pose in [poses[len(poses)//2],poses[-1]]:
        corners=[project(p[:2]) for p in box_vertices(pose,path['size'])[:4]]
        draw.line(corners+[corners[0]],fill=FLOW,width=2)

def guide_anchors(evidence,t,path):
    """Only explicitly recorded Cartesian EEF targets, within recorded pushing."""
    if path is None:return []
    return [(item,stamp) for item,stamp in reference_anchors(evidence,t) if item['object_id']==path['object_id']]

def active_path(paths,t):
    for path in reversed(paths):
        if path['start']<=t<=path['end']:return path
    return paths[0] if paths and t<paths[0]['start'] else None

def box_vertices(pose,size):
    xy=np.array([[-1,-1],[1,-1],[1,1],[-1,1]])*np.asarray(size[:2])/2
    c,s=np.cos(pose[2]),np.sin(pose[2])
    xy=xy @ np.array([[c,s],[-s,c]])+pose[:2]
    return np.r_[np.c_[xy,np.full(4,.03)],np.c_[xy,np.full(4,size[2]+.03)]]

def contact_guide(poses,local):
    points=[]
    for x,y,yaw in poses:
        c,s=np.cos(yaw),np.sin(yaw)
        points.append([x+c*local[0]-s*local[1],y+s*local[0]+c*local[1],local[2]])
    return np.asarray(points)

def corner_tracks(path,upper=True):
    """Corresponding box corners through saved flow poses, including yaw."""
    vertices=np.asarray([box_vertices(p,path['size']) for p in path['poses']])
    return (vertices[:,4:8] if upper else vertices[:,:4]).transpose(1,0,2)

def draw_lanes(image,camera,rect,path,guides,*,ghosts=True,flow=True,traces=()):
    x0,y0,width,height=rect
    layer=Image.new('RGBA',(width,height));draw=ImageDraw.Draw(layer)
    def clip(p):return camera @ np.r_[p,1.]
    def screen(c):return ((c[0]/c[3]+1)*width/2,(1-c[1]/c[3])*height/2)
    def line(a,b,color,width_px):
        a,b=clip(a),clip(b)
        # Clip every segment to the six homogeneous frustum planes.
        for axis in range(3):
            for sign in [-1,1]:
                fa=a[3]+sign*a[axis];fb=b[3]+sign*b[axis]
                if fa<0 and fb<0:return
                if fa<0:a=a+(b-a)*fa/(fa-fb)
                elif fb<0:b=b+(a-b)*fb/(fb-fa)
        if min(a[3],b[3])>1e-8:draw.line([screen(a),screen(b)],fill=color,width=width_px)
    def anchor(p,color):
        c=clip(p)
        if c[3]<=0 or (abs(c[:3])>c[3]).any():return
        x,y=screen(c);r=5 if width>400 else 4
        diamond=[(x,y-r),(x+r,y),(x,y+r),(x-r,y),(x,y-r)]
        draw.line(diamond,fill=(255,255,255,240),width=4)
        draw.line(diamond,fill=(*color,255),width=2)
    def lane(points,color):
        for a,b in zip(points[:-1],points[1:]):line(a,b,(*color,50),12 if width>400 else 8)
        for a,b in zip(points[:-1],points[1:]):line(a,b,(*color,230),3 if width>400 else 2)
        for p in points:anchor(p,color)
    if path:
        poses=np.asarray(path['poses']);size=path['size']
        if ghosts:
            for track in corner_tracks(path):
                for a,b in zip(track[:-1],track[1:]):
                    line(a,b,(*FLOW,95),2)
        # Exactly two generated poses, never averaged candidate boxes.
        for pose in ([poses[len(poses)//2],poses[-1]] if ghosts else []):
            vertices=box_vertices(pose,size)
            faces=[[0,1,2,3],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]
            for face in faces:
                projected=[clip(vertices[i]) for i in face]
                if all(c[3]>.025 and (abs(c[:2])<c[3]*3).all() for c in projected):
                    draw.polygon([screen(c) for c in projected],fill=(*FLOW,16))
            for i,j in [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]:
                line(vertices[i],vertices[j],(*FLOW,180),2)
        if flow:lane(np.c_[poses[:,:2],np.full(len(poses),size[2]/2)],FLOW)
        for points in guides:lane(points,GUIDE)
    for index,points in enumerate(traces):
        color=EEF_COLORS[index%len(EEF_COLORS)]
        for a,b in zip(points[:-1],points[1:]):line(a,b,(*color,48),9 if width>400 else 7)
        for a,b in zip(points[:-1],points[1:]):line(a,b,(*color,235),3 if width>400 else 2)
    image.paste(layer,(x0,y0),layer)
    return layer.getchannel('A')
