"""Arrange independent recorded environments for a labeled terrain matrix.

A recorded motion is replayed in four directions from the same initial position.
This is an illustrative display transform, not a new multi-agent physics rollout.
Original recordings and measured training curves are not modified.
"""
import copy
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation

PALETTE = {
    'flat': (229,239,245), 'stairs_up': (246,231,217),
    'stairs_down': (244,239,215), 'slope_up': (224,239,226),
    'slope_down': (233,228,243), 'random_rough': (243,227,237),
}
TITLES = {'flat':'Flat','stairs_up':'Stairs up','stairs_down':'Stairs down',
          'slope_up':'Slope up','slope_down':'Slope down','random_rough':'Rough terrain'}


def arrange(record, source_buffers, reference_time, tracking=None):
    buffers=list(source_buffers)
    def array(ref, width):
        return np.frombuffer(buffers[ref['__binary_index']],dtype=ref['dtype']).reshape(-1,width)
    def pack(values):
        values=np.ascontiguousarray(values)
        buffers.append(values.tobytes())
        return {'__binary_index':len(buffers)-1,'dtype':values.dtype.str}
    messages=record['messages']
    first=next(m for _,m in messages if m['type']=='BatchedMeshesMessage')
    positions=array(first['props']['batched_positions'],3)
    origins=np.round(positions[:,:2]/4)*4
    families=[family for family in PALETTE if any(m['type']=='MeshMessage' and m['name'].endswith('/'+family) for _,m in messages)]
    columns=sorted(set(origins[:,1]))
    assert len(columns)==len(families)
    def sample(time):
        result=positions
        for timestamp,message in messages:
            if timestamp<=time+1e-6 and message.get('name')==first['name'] and 'batched_positions' in message.get('updates',{}):
                result=array(message['updates']['batched_positions'],3)
        return result
    initial=sample(reference_time)
    movement=sample(reference_time+6)-initial
    selected=[];angles=[];destinations=[];views=[];metadata=[];margins=[];terrain_slots=[]
    tracks=[array(m['updates']['batched_positions'],3) for t,m in messages
            if reference_time-1e-6<=t<reference_time+8-1e-6 and m.get('name')==first['name'] and 'batched_positions' in m.get('updates',{})]
    extent=np.linalg.norm(np.stack(tracks)[:,:,:2]-initial[:,:2],axis=2).max(axis=0)
    for group,(family,y) in enumerate(zip(families,columns)):
        ids=np.flatnonzero(origins[:,1]==y)
        # Fixed spatial selection, independent of success or reward.
        ids=[min(ids,key=lambda i:(abs(origins[i,0]),origins[i,0]))]*4
        motion_radius=float(extent[ids].max())
        margin=max(3.,motion_radius+.8)
        terrain_slots.append(len(selected))
        for index,agent in enumerate(ids):
            direction=np.pi/4+index*np.pi/2
            heading=np.arctan2(movement[agent,1],movement[agent,0])
            if tracking is not None:
                command=tracking.sample(reference_time)['command_world'][agent]
                heading=np.arctan2(command[1],command[0])
            angle=direction-heading
            center=np.array([group*80,0.,0.])
            selected.append(int(agent));angles.append(angle);destinations.append(center);margins.append(margin)
            metadata.append(dict(terrain=family,sourceAgent=int(agent),displayRotationDegrees=float(np.degrees(angle)),displayCenter=center.tolist(),presentation="Four rotated replays of one recorded agent, aligned to the same initial XY; illustrative, not a joint physics rollout"))
        distance=max(6.5,motion_radius*1.8+2)
        views.append(dict(key=family,title=TITLES[family],count=len(ids),eye=[group*80+distance*.18,-distance*.94,distance*.62],target=[group*80,0,.65]))
    selected=np.array(selected);angles=np.array(angles);destinations=np.array(destinations)
    rotations=Rotation.from_euler('z',angles)
    source_origins=np.c_[initial[selected,:2],np.zeros(len(selected))]
    def transform_positions(ref):
        return pack((rotations.apply(array(ref,3)[selected]-source_origins)+destinations).astype('<f4'))
    def transform_quaternions(ref):
        return pack((rotations*Rotation.from_quat(array(ref,4)[selected],scalar_first=True)).as_quat(scalar_first=True).astype('<f4'))
    # One representative terrain per family; other motions are display transforms.
    terrain=[]
    for _,message in messages:
        if message['type']!='MeshMessage' or not message['name'].startswith('/terrain/'):continue
        props=message['props'];vertices=array(props['vertices'],3);faces=array(props['faces'],3)
        mesh=trimesh.Trimesh(vertices,faces,process=False)
        lo,hi=mesh.bounds
        for slot in terrain_slots:
            agent=selected[slot]
            ox,oy=initial[agent,:2];margin=margins[slot]
            if hi[0]<ox-margin or lo[0]>ox+margin or hi[1]<oy-margin or lo[1]>oy+margin:continue
            clipped=mesh.slice_plane([[ox-margin,0,0],[ox+margin,0,0],[0,oy-margin,0],[0,oy+margin,0]],
                                     [[1,0,0],[-1,0,0],[0,1,0],[0,-1,0]],cap=False)
            if not len(clipped.faces):continue
            rim=np.c_[np.cos(np.linspace(0,2*np.pi,20,endpoint=False)),np.sin(np.linspace(0,2*np.pi,20,endpoint=False)),np.zeros(20)]
            clipped=clipped.slice_plane(np.array([ox,oy,0.])+margin*rim,-rim,cap=False)
            if not len(clipped.faces):continue
            family=metadata[slot]['terrain']
            points=rotations[slot].apply(clipped.vertices-source_origins[slot])+destinations[slot]
            node=copy.deepcopy(message);node['name']=f'/matrix-terrain-{slot}-{len(terrain)}'
            node['props'].update(vertices=pack(points.astype('<f4')),faces=pack(clipped.faces.astype('<u4')),
                color=tuple(min(255,c+7) for c in PALETTE[family]),flat_shading=True,receive_shadow=False)
            terrain.append((0.,node))
            terrain.append((0.,dict(type='SetSceneNodeVisibilityMessage',name=node['name'],visible=True)))
            # Trace actual sharp creases and boundary edges, excluding planar triangulation.
            outlined=trimesh.Trimesh(points,clipped.faces,process=True)
            edges=outlined.face_adjacency_edges[outlined.face_adjacency_angles > .22]
            unique,counts=np.unique(np.sort(outlined.edges,axis=1),axis=0,return_counts=True)
            edges=np.concatenate([edges,unique[counts==1]])
            if family=='random_rough':edges=edges[::max(1,len(edges)//1800)]
            segments=list(outlined.vertices[edges])
            if family.startswith('slope_'):
                low,high=outlined.bounds[:,2]
                for level in np.arange(np.ceil(low/.08)*.08,high,.08):
                    section=outlined.section(plane_origin=[0,0,float(level)],plane_normal=[0,0,1])
                    if section is not None:
                        for line in section.discrete:
                            segments.extend(zip(line[:-1],line[1:]))
            strips=[]
            for a,b in segments:
                delta=b-a;length=np.linalg.norm(delta)
                if length<.035:continue
                side=np.cross(delta,[0,0,1.])
                if np.linalg.norm(side)<1e-5:side=np.cross(delta,[1.,0,0])
                side=side/np.linalg.norm(side)*.009
                strips.append([a-side+[0,0,.006],a+side+[0,0,.006],b+side+[0,0,.006],b-side+[0,0,.006]])
            if strips:
                vertices=np.array(strips).reshape(-1,3)
                faces=(np.arange(len(strips))[:,None,None]*4+np.array([[0,1,2],[0,2,3]])).reshape(-1,3)
                outline=copy.deepcopy(node);outline['name']+='-creases'
                outline['props'].update(vertices=pack(vertices.astype('<f4')),faces=pack(faces.astype('<u4')),color=(104,115,123),side='double',cast_shadow=False)
                terrain.append((0.,outline))
                terrain.append((0.,dict(type='SetSceneNodeVisibilityMessage',name=outline['name'],visible=True)))
    result=copy.deepcopy(record);result['messages']=[]
    for timestamp,message in messages:
        name=message.get('name','')
        if name.startswith(('/terrain/','/terrain-label/')):continue
        message=copy.deepcopy(message)
        if name=='/learning-fill' and message['type']=='AmbientLightMessage':message['props']['intensity']=1.65
        if name=='/learning-key' and message['type']=='DirectionalLightMessage':message['props']['intensity']=2.0
        if name=='/learning-key' and message['type']=='SetPositionMessage':message['position']=[-8.,-12.,16.]
        if message['type']=='BatchedMeshesMessage':
            props=message['props']
            props['batched_positions']=transform_positions(props['batched_positions'])
            props['batched_wxyzs']=transform_quaternions(props['batched_wxyzs'])
            for key,width in [('batched_colors',3),('batched_scales',3),('batched_opacities',1)]:
                ref=props.get(key)
                if ref and len(array(ref,width))==len(positions):props[key]=pack(array(ref,width)[selected])
        elif name.startswith('/agents/') and 'updates' in message:
            updates=message['updates']
            if 'batched_positions' in updates:updates['batched_positions']=transform_positions(updates['batched_positions'])
            if 'batched_wxyzs' in updates:updates['batched_wxyzs']=transform_quaternions(updates['batched_wxyzs'])
        result['messages'].append((timestamp,message))
    if tracking is not None:
        from policy_tracking_overlay import tracking_messages
        result['messages']+=tracking_messages(tracking,reference_time,metadata,source_origins,pack)
    result['messages']=sorted(terrain+result['messages'],key=lambda item:item[0])
    return result,buffers,views,metadata


MATRIX = r'''views=>{
 const m=testViewer.mutable.current,scene=m.scene,gl=scene.__r3f.root.getState().gl;
 const q=testViewer.useSceneTree.get('').wxyz;
 const rotation=m.camera.quaternion.clone().set(q[1],q[2],q[3],q[0]);
 const width=gl.domElement.width,height=gl.domElement.height,columns=2,rows=Math.ceil(views.length/columns),scale=width/960;
 const cameras=views.map((view,index)=>{
  const c=m.camera.clone();c.up.set(0,0,1).applyQuaternion(rotation);
  c.position.fromArray(view.eye).applyQuaternion(rotation);
  c.lookAt(c.position.clone().fromArray(view.target).applyQuaternion(rotation));
  c.aspect=(width/columns*(views.length%2&&index===views.length-1?2:1)-16*scale)/(height/rows-44*scale);c.fov=46;c.updateProjectionMatrix();c.updateMatrixWorld();return c;
 });
 const original=gl.render.bind(gl);
 gl.render=(s,c)=>{
  if(s!==scene){return original(s,c);}
  gl.setScissorTest(false);gl.setViewport(0,0,width,height);gl.clear();gl.setScissorTest(true);
  cameras.forEach((camera,index)=>{
   const x=Math.floor(index%columns*width/columns)+8*scale,y=Math.floor(height-(Math.floor(index/columns)+1)*height/rows)+8*scale;
   const w=Math.floor(width/columns)*(views.length%2&&index===views.length-1?2:1)-16*scale,h=Math.floor(height/rows)-44*scale;
   gl.setViewport(x,y,w,h);gl.setScissor(x,y,w,h);original(s,camera);
  });
  gl.setScissorTest(false);gl.setViewport(0,0,width,height);
 };
}'''


def annotate(picture, views, size, metrics=None):
    import io
    from PIL import Image,ImageDraw,ImageFont
    image=Image.open(io.BytesIO(picture)).convert('RGB')
    draw=ImageDraw.Draw(image);rows=(len(views)+1)//2
    font=ImageFont.truetype('DejaVuSans.ttf',round(size/48))
    small=ImageFont.truetype('DejaVuSans.ttf',round(size/74))
    for index,view in enumerate(views):
        x=index%2*size//2;y=index//2*size//rows
        width=size if len(views)%2 and index==len(views)-1 else size//2
        draw.rectangle((x,y,x+width,y+round(32*size/960)),fill='white')
        draw.text((x+round(14*size/960),y+round(5*size/960)),view['title'],fill='#39434a',font=font)
        text=f"{view['count']} directions"
        draw.text((x+width-round(14*size/960),y+round(8*size/960)),text,fill='#77828a',font=small,anchor='ra')
        if metrics is not None:
            row=metrics[index];scale=size/960
            draw.text((x+round(14*scale),y+round(43*scale)),
                      f"Target {row['target']:.2f}  /  Actual {row['actual']:.2f} m/s",fill='#39434a',font=small)
            draw.text((x+round(14*scale),y+round(59*scale)),
                      f"Velocity error {row['velocityError']:.2f} m/s  ·  Heading error {row['headingErrorDegrees']:.1f}°",fill='#637079',font=small)
    output=io.BytesIO();image.save(output,format='JPEG',quality=95)
    return output.getvalue()
