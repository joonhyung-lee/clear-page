"""Arrange independent recorded environments for a labeled terrain matrix.

A recorded motion is replayed in four directions from the same initial position.
This is an illustrative display transform, not a new multi-agent physics rollout.
Original recordings and measured training curves are not modified.
"""
import copy
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation
from scipy.spatial import ConvexHull
from design_tokens import rgb, font_path

PALETTE = {
    'flat': rgb('gray',100), 'stairs_up': rgb('blue',100),
    'stairs_down': rgb('mint',100), 'slope_up': rgb('green',100),
    'slope_down': rgb('purple',100), 'random_rough': rgb('red',100),
}
# The archived generator names pyramid shape; outward replays traverse the opposite grade.
DISPLAY_TERRAIN={'stairs_up':'stairs_down','stairs_down':'stairs_up','slope_up':'slope_down','slope_down':'slope_up'}

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
        # Fixed terrain row across checkpoints: hardest recorded G1 row, central row for Spot.
        ids=[max(ids,key=lambda i:origins[i,0]) if len(families)==6 else min(ids,key=lambda i:(abs(origins[i,0]),origins[i,0]))]*4
        motion_radius=float(extent[ids].max())
        margin=4.
        terrain_slots.append(len(selected))
        for index,agent in enumerate(ids):
            direction=np.pi/4+index*np.pi/2
            heading=np.arctan2(movement[agent,1],movement[agent,0])
            if tracking is not None:
                command=tracking.sample(reference_time)['command_world'][agent]
                heading=np.arctan2(command[1],command[0])
            angle=direction-heading
            center=np.array([group*1000,0.,0.])
            selected.append(int(agent));angles.append(angle);destinations.append(center);margins.append(margin)
            metadata.append(dict(terrain=DISPLAY_TERRAIN.get(family,family),sourceTerrain=family,sourceAgent=int(agent),displayRotationDegrees=float(np.degrees(angle)),displayCenter=center.tolist(),presentation="Four rotated replays of one recorded agent, aligned to the same initial XY; illustrative, not a joint physics rollout"))
        distance=max(6.5,motion_radius*1.8+2)
        views.append(dict(key=DISPLAY_TERRAIN.get(family,family),title=TITLES[DISPLAY_TERRAIN.get(family,family)],count=len(ids),eye=[group*1000+distance*.18,-distance*.94,distance*.62],target=[group*1000,0,.65]))
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
            family=metadata[slot]['terrain']
            points=rotations[slot].apply(clipped.vertices-source_origins[slot])+destinations[slot]
            node=copy.deepcopy(message);node['name']=f'/matrix-terrain-{slot}-{len(terrain)}'
            node['props'].update(vertices=pack(points.astype('<f4')),faces=pack(clipped.faces.astype('<u4')),
                color=tuple(min(255,c+7) for c in PALETTE[family]),flat_shading=True,receive_shadow=False)
            if family.startswith('slope_'):
                view=views[slot//4]
                tone='green' if family=='slope_up' else 'purple'
                view['gradientColors']=[rgb(tone,50),rgb(tone,300)]
                view.setdefault('gradientNodes',[]).append(node['name'])
                top=clipped.vertices[np.unique(clipped.faces[clipped.face_normals[:,2]>.3])]
                if len(top):view.setdefault('gradientHeights',[]).extend([float(top[:,2].min()),float(top[:,2].max())])
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
                local=rotations[slot].inv().apply(np.array([a,b])-destinations[slot])
                if any(np.all(np.abs(local[:,axis]-sign*margin)<.025) for axis in [0,1] for sign in [-1,1]):continue
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
    # Visual continuation outside the recorded 8 m tile: a flat apron hides
    # finite mesh edges. It does not alter the recorded physics or robot poses.
    for group,view in enumerate(views):
        slot=group*4;family=metadata[slot]['terrain'];edge=4.;far=200.
        rectangles=[(-far,-far,-edge,far),(edge,-far,far,far),(-edge,-far,edge,-edge),(-edge,edge,edge,far)]
        quads=np.array([[[x0,y0,0.],[x1,y0,0.],[x1,y1,0.],[x0,y1,0.]] for x0,y0,x1,y1 in rectangles]).reshape(-1,3)
        points=rotations[slot].apply(quads)+destinations[slot]
        faces=(np.arange(4)[:,None,None]*4+np.array([[0,1,2],[0,2,3]])).reshape(-1,3)
        apron=copy.deepcopy(next(m for _,m in terrain if m['type']=='MeshMessage'))
        apron['name']=f'/terrain-continuation-{group}'
        apron['props'].update(vertices=pack(points.astype('<f4')),faces=pack(faces.astype('<u4')),
            color=tuple(min(255,c+7) for c in PALETTE[family]),side='double',cast_shadow=False,receive_shadow=False)
        if family.startswith('slope_'):view.setdefault('gradientNodes',[]).append(apron['name'])
        terrain.extend([(0.,apron),(0.,dict(type='SetSceneNodeVisibilityMessage',name=apron['name'],visible=True))])
        points=[]
        for slot in range(group*4,group*4+4):
            motion=rotations[slot].apply(np.stack(tracks)[:,selected[slot]]-source_origins[slot])+destinations[slot]
            points.extend([motion-[0,0,.9],motion+[0,0,1.1]])
        motion_points=np.concatenate(points)
        view['fitPoints']=motion_points[ConvexHull(motion_points).vertices].tolist()
    result=copy.deepcopy(record);result['messages']=[]
    for timestamp,message in messages:
        name=message.get('name','')
        if name.startswith(('/terrain/','/terrain-label/')) or message['type'] in ('LabelMessage','Gui3DMessage'):continue
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
 // Interpolated vertex colors preserve the recorded surface and contour meshes.
 const linear=v=>{v/=255;return v<=.04045?v/12.92:Math.pow((v+.055)/1.055,2.4);};
 for(const view of views){
  if(!view.gradientNodes?.length)continue;
  const lo=Math.min(...view.gradientHeights),hi=Math.max(...view.gradientHeights);
  const palette=view.gradientColors;
  for(const name of view.gradientNodes){
   m.nodeRefFromName[name]?.traverse(object=>{
    if(!object.isMesh||!object.geometry?.attributes.position)return;
    object.geometry=object.geometry.clone();
    const position=object.geometry.attributes.position,color=position.clone();
    for(let i=0;i<position.count;i++){
     const t=Math.max(0,Math.min(1,(position.getZ(i)-lo)/Math.max(hi-lo,.001)));
     color.setXYZ(i,...palette[0].map((v,k)=>linear(v+(palette[1][k]-v)*t)));
    }
    object.geometry.setAttribute('color',color);
    const tint=material=>{material=material.clone();material.color.setRGB(1,1,1);material.vertexColors=true;material.needsUpdate=true;return material;};
    object.material=Array.isArray(object.material)?object.material.map(tint):tint(object.material);
   });
  }
 }
 const cameras=views.map((view,index)=>{
  const c=m.camera.clone();c.up.set(0,0,1).applyQuaternion(rotation);
  c.position.fromArray(view.eye).applyQuaternion(rotation);
  c.lookAt(c.position.clone().fromArray(view.target).applyQuaternion(rotation));
  c.aspect=(width/columns-16*scale)/(height/rows-44*scale);c.fov=46;
  // Frame robot motion closely; the surrounding ground continues beyond the view.
  if(view.fitPoints){
   const at=c.position.clone().fromArray(view.target).applyQuaternion(rotation);
   const direction=c.position.clone().sub(at).normalize();
   const inverse=c.quaternion.clone().invert(),tan=Math.tan(c.fov*Math.PI/360);
   const local=view.fitPoints.map(xyz=>c.position.clone().fromArray(xyz).applyQuaternion(rotation).sub(at).applyQuaternion(inverse));
   const shift=c.position.clone().set(
    (Math.min(...local.map(p=>p.x))+Math.max(...local.map(p=>p.x)))/2,
    (Math.min(...local.map(p=>p.y))+Math.max(...local.map(p=>p.y)))/2,0).applyQuaternion(c.quaternion);
   at.add(shift);
   let distance=0;
   for(const xyz of view.fitPoints){
    const point=c.position.clone().fromArray(xyz).applyQuaternion(rotation).sub(at).applyQuaternion(inverse);
    distance=Math.max(distance,point.z+Math.abs(point.x)/(tan*c.aspect)*1.18,point.z+Math.abs(point.y)/tan*1.18);
   }
   c.position.copy(at).addScaledVector(direction,distance);c.lookAt(at);
  }
  c.updateProjectionMatrix();c.updateMatrixWorld();return c;
 });
 const original=gl.render.bind(gl);
 gl.render=(s,c)=>{
  if(s!==scene){return original(s,c);}
  gl.setScissorTest(false);gl.setViewport(0,0,width,height);gl.clear();gl.setScissorTest(true);
  cameras.forEach((camera,index)=>{
   const x=(views.length%2&&index===views.length-1?width/4:Math.floor(index%columns*width/columns))+8*scale,y=Math.floor(height-(Math.floor(index/columns)+1)*height/rows)+8*scale;
   const w=Math.floor(width/columns)-16*scale,h=Math.floor(height/rows)-44*scale;
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
    font=ImageFont.truetype(font_path(),round(size/48))
    small=ImageFont.truetype(font_path(mono=True),round(size/74))
    for index,view in enumerate(views):
        x=index%2*size//2;y=index//2*image.height//rows
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
