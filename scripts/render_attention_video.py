"""Render native Viser meshes with synchronized top-down attention and torso RGB.

Both cameras use the same recorded body transforms. EGL renders the numeric
Viser scene offline; this is not a screenshot of the browser UI or new physics.
"""
import argparse
import ctypes
import json
import os
os.environ.setdefault('MUJOCO_GL','egl')
from pathlib import Path
import subprocess
import time
import mujoco
import numpy as np
from OpenGL import GL
from OpenGL.GL.shaders import compileProgram, compileShader
from PIL import Image, ImageDraw, ImageFont, ImageChops
from scipy.spatial.transform import Rotation
import imageio_ffmpeg
from attention_probability import distribution
from attention_contact_replay import contact_display, active_push
from attention_lanes import active_path, draw_lanes, guide_anchors, draw_query_marker, draw_minimap_path, draw_contact_field, CONTACT
from attention_terrain import terrain_color,draw_terrain,draw_minimap_terrain,draw_profile,PALETTE,LABELS

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('scenes',type=Path);p.add_argument('attention',type=Path);p.add_argument('output',type=Path)
p.add_argument('--preview',action='store_true');p.add_argument('--fps',type=int,default=25);p.add_argument('--speed',type=float,default=2)
p.add_argument('--only',nargs='*')
p.add_argument('--preview-time',type=float)
p.add_argument('--terrain-chase',action='store_true',help='Add an optional heading-following third-person inset')
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
data=json.loads(a.attention.read_text())
contact_data=json.loads((a.attention.parent/'contact-evidence.json').read_text())['cases']
plan_data=json.loads((a.attention.parent/'recorded-plans.json').read_text())['cases']
W,H=1280,720
ctx=mujoco.GLContext(W,H);ctx.make_current()
# Surfaceless EGL has no default framebuffer.
fbo=GL.glGenFramebuffers(1);GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,fbo)
color_buffer=GL.glGenRenderbuffers(1);GL.glBindRenderbuffer(GL.GL_RENDERBUFFER,color_buffer)
GL.glRenderbufferStorage(GL.GL_RENDERBUFFER,GL.GL_RGBA8,W,H)
GL.glFramebufferRenderbuffer(GL.GL_FRAMEBUFFER,GL.GL_COLOR_ATTACHMENT0,GL.GL_RENDERBUFFER,color_buffer)
depth_buffer=GL.glGenRenderbuffers(1);GL.glBindRenderbuffer(GL.GL_RENDERBUFFER,depth_buffer)
GL.glRenderbufferStorage(GL.GL_RENDERBUFFER,GL.GL_DEPTH_COMPONENT24,W,H)
GL.glFramebufferRenderbuffer(GL.GL_FRAMEBUFFER,GL.GL_DEPTH_ATTACHMENT,GL.GL_RENDERBUFFER,depth_buffer)
GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0);GL.glReadBuffer(GL.GL_COLOR_ATTACHMENT0)
GL.glDisable(GL.GL_DITHER)
assert GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)==GL.GL_FRAMEBUFFER_COMPLETE
renderer=GL.glGetString(GL.GL_RENDERER).decode()
program=compileProgram(compileShader('''#version 330
layout(location=0) in vec3 vertex; layout(location=1) in vec3 normal;
uniform mat4 mvp; uniform mat4 model; out vec3 n;
void main(){gl_Position=mvp*vec4(vertex,1); n=mat3(model)*normal;}
''',GL.GL_VERTEX_SHADER),compileShader('''#version 330
in vec3 n;uniform vec3 color;out vec4 pixel;
void main(){float shade=.72+.28*abs(dot(normalize(n),normalize(vec3(.25,-.35,1.))));pixel=vec4(color*shade,1);}
''',GL.GL_FRAGMENT_SHADER))
uniforms={key:GL.glGetUniformLocation(program,key) for key in ['mvp','model','color']}
GL.glEnable(GL.GL_DEPTH_TEST);GL.glDisable(GL.GL_CULL_FACE);GL.glUseProgram(program)
font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
fonts={size:ImageFont.truetype(font_path,size) for size in [13,15,17,20,24]}
green=np.array([0,76,38],float)/255
# Fixed full-range scale across all views and recordings. This is attention,
# not a calibrated affordance probability. Tint preserves surface shading.
contrast_low=0.
contrast_high=1.

def strength(value):
    return np.clip(value/contrast_high,0,1)

def heat(value):
    alpha=.85*np.sqrt(strength(value))
    return (1-alpha)*np.array([.90,.90,.90])+alpha*green

def overlay(color,value=None):
    gray=np.full(3,.28+.68*np.dot(color,[.2126,.7152,.0722]))
    if value is None:return gray
    alpha=.85*np.sqrt(strength(value))
    return (1-alpha)*gray+alpha*green

def look_at(eye,target,up):
    f=np.asarray(target)-eye;f=f/np.linalg.norm(f);s=np.cross(f,up);s/=np.linalg.norm(s);u=np.cross(s,f)
    out=np.eye(4);out[:3,:3]=np.array([s,u,-f]);out[:3,3]=-out[:3,:3]@eye;return out

def projection(aspect,ortho=None,fov=60):
    near,far=.025,100.
    if ortho:
        top=ortho/2;right=top*aspect;out=np.eye(4);out[0,0]=1/right;out[1,1]=1/top;out[2,2]=-2/(far-near);out[2,3]=-(far+near)/(far-near);return out
    f=1/np.tan(np.deg2rad(fov)/2);return np.array([[f/aspect,0,0,0],[0,f,0,0],[0,0,-(far+near)/(far-near),-2*far*near/(far-near)],[0,0,-1,0]])

def upload(vertices,normals,faces):
    vao=GL.glGenVertexArrays(1);GL.glBindVertexArray(vao)
    vbo=GL.glGenBuffers(1);GL.glBindBuffer(GL.GL_ARRAY_BUFFER,vbo)
    v=np.column_stack([vertices,normals]).astype('f4');GL.glBufferData(GL.GL_ARRAY_BUFFER,v.nbytes,v,GL.GL_STATIC_DRAW)
    for index in range(2):GL.glEnableVertexAttribArray(index);GL.glVertexAttribPointer(index,3,GL.GL_FLOAT,False,24,ctypes.c_void_p(index*12))
    ebo=GL.glGenBuffers(1);GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER,ebo);GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER,faces.nbytes,faces,GL.GL_STATIC_DRAW)
    return vao,vbo,ebo,faces.size

def pose_at(source,t):
    times=source['time'];j=min(int(np.searchsorted(times,t,side='right')),len(times)-1);i=max(0,j-1)
    f=float(np.clip((t-times[i])/max(times[j]-times[i],1e-9),0,1))
    positions=(1-f)*source['positions'][i]+f*source['positions'][j]
    q0,q1=source['quaternions'][i],source['quaternions'][j]
    # Shortest-arc normalized interpolation preserves every saved pose at its timestamp.
    q1=np.where((q0*q1).sum(-1,keepdims=True)<0,-q1,q1);q=(1-f)*q0+f*q1;q/=np.linalg.norm(q,axis=-1,keepdims=True)
    rotations=Rotation.from_quat(q,scalar_first=True).as_matrix()
    matrices=np.tile(np.eye(4),(len(q),1,1));matrices[:,:3,:3]=rotations;matrices[:,:3,3]=positions
    return positions,rotations,matrices

manifest=[]
try:
 for case in data['cases']:
    if a.only and case['id'] not in a.only:continue
    folder=a.scenes/case['id'];meta=json.loads((folder/'scene.json').read_text());source=np.load(folder/'geometry.npz')
    evidence=contact_data[case['id']];contact_times=np.array([f['time'] for f in evidence['frames']]);target_times=np.array([f['time'] for f in evidence['targets']])
    marker_counts=dict(target=0,contact=0)
    flow_paths=plan_data[case['id']]['flowPaths']
    tiles=meta['scene']['terrain']
    eef_positions=np.asarray([frame['eef'] for frame in evidence['frames']])
    push_starts={path['start']:next((frame['time'] for frame in evidence['frames']
        if path['start']<=frame['time']<=path['end'] and any(c['object_id']==path['object_id'] for c in frame['contacts'])),None) for path in flow_paths}
    object_bodies={oid:meta['bodies'].index(name) for name,oid in meta['objectBodies'].items()}
    follow=source['positions'][:,1,:2].copy()
    chase_positions=source['positions'][:,1].copy()
    body_rotations=Rotation.from_quat(source['quaternions'][:,1],scalar_first=True).as_matrix()
    chase_yaw=np.unwrap(np.arctan2(body_rotations[:,1,0],body_rotations[:,0,0]))
    for i in range(1,len(chase_positions)):
        blend=1-np.exp(-(source['time'][i]-source['time'][i-1])/.18)
        chase_positions[i]=chase_positions[i-1]+blend*(chase_positions[i]-chase_positions[i-1])
        chase_yaw[i]=chase_yaw[i-1]+blend*(chase_yaw[i]-chase_yaw[i-1])
    for i,time_s in enumerate(source['time']):
        path=active_path(flow_paths,time_s)
        if path:
            points=np.r_[follow[i][None],np.asarray(path['poses'])[:,:2]]
            follow[i]=(points.min(0)+points.max(0))/2
    for i in range(1,len(follow)):
        blend=1-np.exp(-(source['time'][i]-source['time'][i-1])/.7)
        follow[i]=follow[i-1]+blend*(follow[i]-follow[i-1])
    uploaded=[upload(source[f'vertices_{i}'],source[f'normals_{i}'],source[f'faces_{i}']) for i in range(len(meta['meshes']))]
    frames=[f for f in case['frames'] if f['label']!='Planning input'];att_times=np.array([f['time'] for f in frames])
    duration=min(meta['duration'],frames[-1]['time']);prefix={'sample-54':'attention-g1','sample-55':'attention-spot-arm','sample-53':'attention-terrain-g1'}[case['id']]
    output=a.output/(prefix+'-topdown-ego.mp4');start=time.monotonic()
    frame_audit=[]
    requested=[0.,duration/2,duration] if a.preview else np.minimum(np.arange(int(np.ceil(duration/a.speed*a.fps))+1)*a.speed/a.fps,duration)
    if a.preview and a.preview_time is not None:requested=[min(a.preview_time,duration)]
    proc=None
    if not a.preview:
        proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{W}x{H}','-framerate',str(a.fps),'-i','-','-an','-map_metadata','-1','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(output)],stdin=subprocess.PIPE)
    try:
      for index,t in enumerate(requested):
        pos,rot,matrices=pose_at(source,t)
        ai=max(0,int(np.searchsorted(att_times,t+1e-8,side='right')-1));af=frames[ai]
        weights=np.asarray(af['encoder']).mean((0,1,2))
        labels,probabilities,display_units,spatial_probability=distribution(weights,af['keys'])
        terrain_keys=[i for i,k in enumerate(af['keys']) if k['kind']=='terrain']
        terrain_probabilities=spatial_probability[terrain_keys]
        mesh_terrain={i:tiles[int(af['keys'][i]['source_id'].split(':')[1])] for i in terrain_keys}
        flow_path=active_path(flow_paths,t)
        push_window=active_push(evidence,t)
        GL.glDisable(GL.GL_SCISSOR_TEST);GL.glViewport(0,0,W,H);GL.glClearColor(.98,.985,.975,1);GL.glClear(GL.GL_COLOR_BUFFER_BIT|GL.GL_DEPTH_BUFFER_BIT)
        world=meta['scene']['world_size'];center=np.array([np.interp(t,source['time'],follow[:,k]) for k in range(2)])
        center=np.clip(center,[2.8,2.8],np.array(world)-2.8);middle=np.r_[center,0.]
        view_height=6.4
        if flow_path:
            points=np.r_[pos[1,:2][None],np.asarray(flow_path['poses'])[:,:2]]
            extent=abs(points-center).max(0)
            view_height=max(view_height,2*extent[1]+1.7,(2*extent[0]+1.7)*H/880)
        overview=0.
        if tiles:
            # 1.5 s overview + 1.5 s smooth transition at the 2x replay clock.
            u=np.clip((t/a.speed-1.5)/1.5,0,1);overview=1-u*u*(3-2*u)
        camera_middle=(1-overview)*middle+overview*np.r_[np.asarray(world)/2,0.]
        camera_height=(1-overview)*view_height+overview*(max(world)+4.)
        follow_eye=np.array([0,-15.,19.]) if tiles else np.array([0,0,25.])
        eye_offset=(1-overview)*follow_eye+overview*np.array([0,-15.,19.])
        top=projection(880/H,camera_height)@look_at(camera_middle+eye_offset,camera_middle,[0,1,0])
        body=meta['egoBody'];eye=pos[body]+rot[body]@meta['egoOffset']
        pitch=np.deg2rad(20 if case['body']=='g1' else 12)
        forward=rot[body] @ np.array([np.cos(pitch),0,-np.sin(pitch)])
        up=rot[body] @ np.array([np.sin(pitch),0,np.cos(pitch)])
        ego=projection(4/3,fov=90)@look_at(eye,eye+forward,up)
        chase=None;chase_eye=None;chase_target=None
        views=[((0,0,880,H),top,True),((904,404,352,264),ego,False),((904,84,352,264),ego,True)]
        if tiles and overview==0 and a.terrain_chase:
            center3=np.array([np.interp(t,source['time'],chase_positions[:,k]) for k in range(3)])
            yaw=np.interp(t,source['time'],chase_yaw);heading=np.array([np.cos(yaw),np.sin(yaw),0.])
            chase_eye=center3-3.4*heading+np.array([0,0,2.25])
            chase_target=center3+1.1*heading+np.array([0,0,.15])
            chase=projection(4/3,fov=55)@look_at(chase_eye,chase_target,[0,0,1])
            views.append(((566,399,292,219),chase,False))
        for viewport,camera,attention in views:
            GL.glEnable(GL.GL_SCISSOR_TEST);GL.glScissor(*viewport);GL.glViewport(*viewport);GL.glClear(GL.GL_COLOR_BUFFER_BIT|GL.GL_DEPTH_BUFFER_BIT)
            for mesh,gpu in zip(meta['meshes'],uploaded,strict=True):
                model=matrices[mesh['body']];color=np.array(mesh['color'])/255
                if attention:
                    if viewport[0]==0 and mesh['key'] in mesh_terrain:
                        color=np.asarray(terrain_color(mesh_terrain[mesh['key']]))/255
                    else:color=overlay(color,spatial_probability[mesh['key']] if mesh['key'] is not None else None)
                elif viewport[0]==566:
                    color=np.asarray(terrain_color(mesh_terrain[mesh['key']]))/255 if mesh['key'] in mesh_terrain else overlay(color) if mesh['body']==0 else color
                GL.glUniformMatrix4fv(uniforms['model'],1,True,np.asarray(model,dtype='f4'))
                GL.glUniformMatrix4fv(uniforms['mvp'],1,True,np.asarray(camera@model,dtype='f4'))
                GL.glUniform3fv(uniforms['color'],1,np.asarray(color,dtype='f4'))
                GL.glBindVertexArray(gpu[0]);GL.glDrawElements(GL.GL_TRIANGLES,gpu[3],GL.GL_UNSIGNED_INT,None)
        GL.glDisable(GL.GL_SCISSOR_TEST);GL.glPixelStorei(GL.GL_PACK_ALIGNMENT,1)
        rgb=np.frombuffer(GL.glReadPixels(0,0,W,H,GL.GL_RGB,GL.GL_UNSIGNED_BYTE),dtype='u1').reshape(H,W,3)[::-1].copy()
        image=Image.fromarray(rgb);draw=ImageDraw.Draw(image)
        ci=max(0,int(np.searchsorted(contact_times,t+1e-8,side='right')-1))
        current_contacts=contact_display(evidence,t)
        ti=int(np.searchsorted(target_times,t+1e-8,side='right')-1)
        targets=[]
        if push_window and ti>=0 and t<evidence['targets'][ti]['until']+1e-8:
            if evidence['targets'][ti]['object_id']==push_window['object_id']:targets=[evidence['targets'][ti]]
        guides=[]
        if push_window:
            for item,_ in guide_anchors(evidence,t,push_window):
                history=[row['position'] for row in evidence['eefTargets']
                    if row['site']==item['site'] and row['object_id']==item['object_id'] and push_window['start']<=row['time']<=item['time']]
                guides.append(np.asarray(history))
        traces=[];ego_traces=[]
        push_start=push_starts.get(flow_path['start']) if flow_path else None
        if push_window and push_start is not None and t>=push_start:
            push_start=max(push_start,push_window['start'])
            for history,destination in [(push_start,traces),(max(push_start,t-4.),ego_traces)]:
                begin=int(np.searchsorted(contact_times,history,side='left'))
                values=eef_positions[begin:ci+1]
                if len(values)>1:
                    samples=np.unique(np.linspace(0,len(values)-1,min(len(values),240)).astype(int))
                    destination.extend(values[samples,hand] for hand in range(values.shape[1]))
        frame_audit.append(dict(time=float(t),overview=float(overview),camera=top.tolist(),chaseEye=chase_eye.tolist() if chase is not None else None,chaseTarget=chase_target.tolist() if chase is not None else None,eefTargetGuides=len(guides),eefTraces=len(traces),contacts=len(current_contacts),contactTargets=len(targets),pushing=push_window is not None))
        draw_terrain(image,top,(0,0,880,H),tiles,terrain_probabilities)
        draw_lanes(image,top,(0,0,880,H),flow_path,guides,traces=traces)
        ego_mask=draw_lanes(image,ego,(904,372,352,264),flow_path,guides,ghosts=False,flow=False,traces=ego_traces)
        mask_draw=ImageDraw.Draw(ego_mask)
        # The query markers belong to the map, not the body-mounted cameras.
        main=image.crop((0,0,880,H))
        for kind in ['start','goal']:
            c=top @ np.r_[meta['scene'][kind][:2],.04,1.]
            q=c[:3]/c[3]
            if (abs(q[:2])<=1).all():
                draw_query_marker(main,((q[0]+1)*440,(1-q[1])*H/2),kind,32 if kind=='start' else 42)
        image.paste(main,(0,0))
        draw=ImageDraw.Draw(image)
        # Compact legends replace prose; contact markers only affect Ego attention.
        draw.rounded_rectangle((18,12,620,54),radius=7,fill=(250,251,248))
        draw.text((32,22),'CLEAR attention  /  '+case['title'],font=fonts[20],fill='#24332e')
        draw.rectangle((900,48,1260,320),outline='#d3dcd5',width=3)
        draw.text((907,23),'Ego RGB',font=fonts[20],fill='#24332e')
        draw.text((907,338),'Ego attention',font=fonts[20],fill='#24332e')
        draw.rectangle((900,368,1260,640),outline='#d3dcd5',width=3)
        legend_top=704-(len(labels)*31+68)
        draw.rounded_rectangle((573,legend_top,861,704),radius=7,fill=(250,251,248),outline='#b9c8be',width=2)
        draw.text((587,legend_top+12),'P(attn | objects, terrain)',font=fonts[15],fill='#24332e')
        for row,(label,value,units) in enumerate(zip(labels,probabilities,display_units,strict=True)):
            y=legend_top+41+row*31
            draw.text((590,y),label,font=fonts[15],fill='#24332e')
            draw.rectangle((690,y+5,767,y+12),fill='#dfe5df')
            if value>0:draw.rectangle((690,y+5,690+77*value,y+12),fill='#176843')
            draw.text((790,y),f'{units/1000:.3f}',font=fonts[15],fill='#174d32')
        draw.text((724,681),'Σ p = 1.000',font=fonts[13],fill='#56655c')
        # Restore the locator, including object IDs for correspondence to rows.
        draw.rounded_rectangle((18,422,278,704),radius=7,fill=(250,251,248),outline='#b9c8be',width=2)
        draw.text((34,434),'Minimap',font=fonts[17],fill='#24332e')
        scale=222/max(world)
        def mini(p):return (36+p[0]*scale,686-p[1]*scale)
        for wall in meta['scene']['walls']:
            l,b,r,u=wall;draw.rectangle([mini([l,u]),mini([r,b])],fill='#a5aaa8')
        draw_minimap_terrain(draw,mini,tiles,terrain_probabilities)
        for name,oid in meta['objectBodies'].items():
            x,y=mini(pos[meta['bodies'].index(name),:2]);draw.rectangle((x-3,y-3,x+3,y+3),fill='#236143')
            draw.text((x+5,y-6),str(oid),font=fonts[13],fill='#24332e')
        draw_minimap_path(draw,mini,flow_path)
        x,y=mini(pos[1,:2]);draw.ellipse((x-4,y-4,x+4,y+4),fill='#243b52')
        # Ground footprint of the actual oblique/top-down camera, clipped to map.
        inverse=np.linalg.inv(top);ground=[]
        for x,y in [(-1,-1),(1,-1),(1,1),(-1,1)]:
            a0=inverse @ np.array([x,y,-1,1.]);b0=inverse @ np.array([x,y,1,1.]);a0=a0[:3]/a0[3];b0=b0[:3]/b0[3]
            ground.append((a0+(b0-a0)*(-a0[2]/(b0[2]-a0[2])))[:2])
        lower=np.maximum(np.min(ground,axis=0),0);upper=np.minimum(np.max(ground,axis=0),world)
        draw.rectangle([mini([lower[0],upper[1]]),mini([upper[0],lower[1]])],outline='#6e91ab')
        for kind in ['start','goal']:
            draw_query_marker(image,mini(meta['scene'][kind]),kind,19 if kind=='start' else 25)
        draw=ImageDraw.Draw(image)
        # Project physically recorded/reconstructed points; never fabricate a
        # marker when a contact or logged MPC reference is absent.
        for kind,points in [('target',targets),('contact',current_contacts)]:
            for item in points:
                c=ego @ np.r_[item['position'],1.]
                if c[3]<=0:continue
                q=c[:3]/c[3]
                bounds=(.93,.91) if kind=='target' else (1.4,1.55)
                if not (-bounds[0]<q[0]<bounds[0] and -bounds[1]<q[1]<bounds[1] and -1<q[2]<1):continue
                x=904+(q[0]+1)*176;y=372+(1-q[1])*132
                if kind=='target':
                    mx,my=x-904,y-372
                    mask_draw.ellipse((mx-12,my-12,mx+12,my+12),fill=255)
                    draw.ellipse((x-12,y-12,x+12,y+12),outline='#ffffff',width=5)
                    draw.ellipse((x-12,y-12,x+12,y+12),outline='#ffab30',width=3)
                else:
                    contact_mask=draw_contact_field(image,ego,(904,372,352,264),item)
                    ego_mask=ImageChops.lighter(ego_mask,contact_mask)
                    mask_draw=ImageDraw.Draw(ego_mask)
                    draw=ImageDraw.Draw(image)
                marker_counts[kind]+=1
        if tiles:
            if overview==0:draw_profile(draw,tiles,pos[1,:2],world,fonts)
            if chase is not None:
                # Map overlays must not paint over the independent chase view.
                image.paste(Image.fromarray(rgb[102:321,566:858]),(566,102))
                draw=ImageDraw.Draw(image)
                draw.rectangle((562,76,862,100),fill=(250,251,248))
                draw.rectangle((563,101,860,323),outline='#b9c8be',width=2)
                draw.text((573,79),'Third-person · Heading',font=fonts[15],fill='#24332e')
            draw.rounded_rectangle((900,654,1260,709),radius=6,fill=(250,251,248),outline='#b9c8be')
            for x,kind in zip([918,1022,1116],['ramp','stair_tread','flat']):
                draw.rectangle((x,675,x+14,689),fill=PALETTE[kind],outline='#526667')
                draw.text((x+21,672),LABELS[kind],font=fonts[13],fill='#24332e')
        else:
            draw.rounded_rectangle((900,654,1260,709),radius=6,fill=(250,251,248),outline='#b9c8be')
            draw.line((910,681,924,681),fill='#4682e6',width=3)
            draw.text((930,672),'Flow',font=fonts[13],fill='#24332e')
            draw.line((976,681,990,681),fill=CONTACT,width=3)
            draw.text((996,672),'EEF',font=fonts[13],fill='#24332e')
            if evidence['targets']:
                draw.ellipse((1036,676,1046,686),outline='#ffa92a',width=2)
                draw.text((1052,672),'Target',font=fonts[13],fill='#24332e')
            for radius,color in [(9,'#f8e1e4'),(6,'#f1b2bd'),(3,'#dc303e')]:
                draw.ellipse((1130-radius,681-radius,1130+radius,681+radius),fill=color)
            draw.text((1148,672),'Contact',font=fonts[13],fill='#24332e')
        if a.preview or index in [0,len(requested)//2,len(requested)-1]:
            image.save(a.output/f'{prefix}-frame-{index:04d}.png')
            ego_mask.save(a.output/f'{prefix}-mask-{index:04d}.png')
            assert np.array_equal(np.asarray(image)[52:316,904:1256],rgb[52:316,904:1256]), 'Overlays changed Ego RGB'
        if proc:proc.stdin.write(image.tobytes())
        if index%100==0:print(prefix,index,'/',len(requested),'elapsed',round(time.monotonic()-start,1),flush=True)
      if proc:proc.stdin.close();assert proc.wait()==0
    finally:
      if proc and proc.poll() is None:proc.terminate();proc.wait()
      for vao,vbo,ebo,_ in uploaded:GL.glDeleteVertexArrays(1,[vao]);GL.glDeleteBuffers(2,[vbo,ebo])
    (a.output/f'{prefix}-render-audit.json').write_text(json.dumps(dict(frames=frame_audit),separators=(',',':'))+'\n')
    manifest.append(dict(file=output.name,body=case['body'],sourceRecording=meta['sourceRecording'],width=W,height=H,fps=a.fps,speed=a.speed,sourceDuration=duration,frames=len(requested),attentionObservations=len(frames),
        geometry='Unchanged native Viser mesh triangles and saved body transforms, rendered offline through EGL.',
        camera='Synchronized body-mounted replay camera, 90 degree vertical field of view, tilted down 20 degrees for G1 and 12 degrees for Spot to include hand contact points; not separately recorded sensor RGB.',
        interpolation='Shortest-arc normalized quaternion and linear position interpolation between saved native states. No physics rerun.',
        attention='Real shared-encoder weights recomputed on recorded observations. Latest available sample is held, never interpolated.',
        overlay='Green conditional-attention probability per object and per terrain token. The legend alone aggregates terrain mass. Semantic pastel terrain colors are independent of attention in main/minimap; ego attention remains grayscale plus per-token green. Contact fields are display emphasis.',
        contrast=dict(low=contrast_low,high=contrast_high,mapping='Fixed square-root display transfer over probabilities 0 to 1; tint opacity 0.85 * sqrt(p). Same mapping for every token, no per-frame rescaling or modification of numeric probabilities.',green=green.tolist()),
        topdown=dict(height=6.4,follow='Smooth framing of robot and active generated object path; zoom expands to retain both ghosts.',context='Larger titled minimap, generated flow lane, waypoint anchors and exactly two ghost poses for the active object in both map views. Start bullseye and goal pin use fixed query coordinates; minimap always includes both. No prose annotations.'),
        terrain=dict(chase=('Rear third-person camera follows recorded base heading, with 180 ms causal position and yaw smoothing. Starts after the map overview.' if a.terrain_chase else None),palette=PALETTE,labels=LABELS,tokenCount=len(tiles),overviewSeconds=3. if tiles else 0.,overviewHoldSeconds=1.5 if tiles else 0.,cues='Exact terrain bounds, true riser corners, three ramp height contours and uphill arrows. Persistent oblique terrain camera and metric cross-sections of all terrain bands, with the nearest band highlighted. No invented stair subdivisions.',minimap='Fixed whole-scene map with persistent semantic terrain colors, boundaries and uphill arrows.'),
        trajectories=dict(flowProposalIndex=plan_data[case['id']]['flowProposalIndex'],ghostsPerActiveObject=2,ghostViews=['topdown','minimap'],egoLayers=(['eef_target'] if evidence.get('eefTargets') else [])+['eef','contact'],eefSites=evidence['eefSites'],eefSource=evidence['eefSource'],pushWindows=evidence['pushWindows'],eefDisplay='Separate recorded EEF site traces from first physical contact through current replay time, restricted to the exact saved push window. Top-down retains push history; ego shows the last 4 seconds. All motion overlays stop at push end, before release and retreat. At most 240 original samples per trace, no position averaging.',ghosts='Middle and final poses from the raw flow proposal matched to this execution. Corresponding corners are connected through every saved flow pose with its original yaw, in main and minimap only. Not averaged candidates.',eefTargetSource=evidence['eefTargetSource'],eefTargetCount=len(evidence.get('eefTargets',[])),contactGuide='Only explicitly logged Cartesian EEF targets in the same named site frame may form a comparison guide. No EEF targets exist in these recordings, so inferred guides are omitted. Spot contact-target rings are kept separate from EEF targets. Raw flow is a blue object path.'),
        legend=dict(normalization='Conditional attention: each object weight and summed terrain weights divided by their total. Not a selection probability from the planner. Exact probabilities sum to 1; displayed decimals use largest-remainder rounding to also sum to 1.000.',color='Each terrain surface uses its own token mass divided by total object-plus-terrain mass; the legend shows the sum. Main/minimap base colors encode type, green contour opacity encodes token attention.'),
        contacts=dict(targetSource=evidence['targetSource'],actualSource=evidence['contactSource'],projectedMarkers=marker_counts,rendering='Contact display opacity follows original binary contact samples with a causal 45 ms attack and 120 ms release. Brief afterglow uses the last observed centroid. This is visual persistence, not a sustained physical-contact assertion. All contact fields, guides and EEF traces are gated by the saved push window; target rings require a still-valid logged reference.',opacityAttackSeconds=.045,opacityReleaseSeconds=.12,style='Soft red Gaussian display field centered on the projected recorded contact centroid. Falloff is visual emphasis, not contact probability, pressure or measured contact area. No contact point anchors or transverse strips.'),
        egoBody=meta['egoBody'],egoOffset=meta['egoOffset'],renderer=renderer))
    print('PASS',prefix,'complete',round(time.monotonic()-start,1),'s',flush=True)
finally:
    GL.glDeleteProgram(program)
    GL.glDeleteRenderbuffers(2,[color_buffer,depth_buffer]);GL.glDeleteFramebuffers(1,[fbo]);ctx.free()
manifest_path=a.output/('preview-manifest.json' if a.preview else 'video-manifest.json')
if a.only and manifest_path.exists():
    previous=json.loads(manifest_path.read_text());replacements={row['file']:row for row in manifest}
    manifest=[replacements.pop(row['file'],row) for row in previous]+list(replacements.values())
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
