"""Render native Viser meshes with causal previous/current plan overlays."""
import argparse,ctypes,json,subprocess,time
from pathlib import Path
import numpy as np,mujoco,imageio_ffmpeg
from OpenGL import GL
from OpenGL.GL.shaders import compileProgram,compileShader
from PIL import Image,ImageDraw,ImageFont
from scipy.spatial.transform import Rotation
from attention_lanes import box_vertices,draw_query_marker
from replanning_timeline import at_time
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--start',type=float,default=0);p.add_argument('--end',type=float);p.add_argument('--speed',type=float,default=2);p.add_argument('--preview',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
d=json.loads((a.source/'timeline.json').read_text());src=np.load(a.source/'geometry.npz');W,H=1280,720;vw=936
ctx=mujoco.GLContext(W,H);ctx.make_current();fbo=GL.glGenFramebuffers(1);GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,fbo)
color_buffer=GL.glGenRenderbuffers(1);GL.glBindRenderbuffer(GL.GL_RENDERBUFFER,color_buffer);GL.glRenderbufferStorage(GL.GL_RENDERBUFFER,GL.GL_RGBA8,W,H);GL.glFramebufferRenderbuffer(GL.GL_FRAMEBUFFER,GL.GL_COLOR_ATTACHMENT0,GL.GL_RENDERBUFFER,color_buffer)
depth=GL.glGenRenderbuffers(1);GL.glBindRenderbuffer(GL.GL_RENDERBUFFER,depth);GL.glRenderbufferStorage(GL.GL_RENDERBUFFER,GL.GL_DEPTH_COMPONENT24,W,H);GL.glFramebufferRenderbuffer(GL.GL_FRAMEBUFFER,GL.GL_DEPTH_ATTACHMENT,GL.GL_RENDERBUFFER,depth);GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0);GL.glReadBuffer(GL.GL_COLOR_ATTACHMENT0)
program=compileProgram(compileShader('''#version 330
layout(location=0) in vec3 vertex;layout(location=1) in vec3 normal;
uniform mat4 mvp;uniform mat4 model;out vec3 n;
void main(){gl_Position=mvp*vec4(vertex,1);n=mat3(model)*normal;}
''',GL.GL_VERTEX_SHADER),compileShader('''#version 330
in vec3 n;uniform vec3 color;out vec4 pixel;
void main(){float s=.72+.28*abs(dot(normalize(n),normalize(vec3(.25,-.35,1.))));pixel=vec4(color*s,1);}
''',GL.GL_FRAGMENT_SHADER));GL.glUseProgram(program);uniforms={n:GL.glGetUniformLocation(program,n) for n in ['mvp','model','color']};GL.glEnable(GL.GL_DEPTH_TEST);GL.glDisable(GL.GL_CULL_FACE)
gpus=[]
for i in range(len(d['meshes'])):
 v=np.c_[src[f'vertices_{i}'],src[f'normals_{i}']].astype('f4');f=src[f'faces_{i}'];vao=GL.glGenVertexArrays(1);GL.glBindVertexArray(vao);vbo=GL.glGenBuffers(1);GL.glBindBuffer(GL.GL_ARRAY_BUFFER,vbo);GL.glBufferData(GL.GL_ARRAY_BUFFER,v.nbytes,v,GL.GL_STATIC_DRAW)
 for k in range(2):GL.glEnableVertexAttribArray(k);GL.glVertexAttribPointer(k,3,GL.GL_FLOAT,False,24,ctypes.c_void_p(k*12))
 ebo=GL.glGenBuffers(1);GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER,ebo);GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER,f.nbytes,f,GL.GL_STATIC_DRAW);gpus.append((vao,vbo,ebo,f.size))
world=d['scene']['world_size'];target=np.r_[np.array(world)/2,0.];eye=target+[0,-7,20];forward=target-eye;forward/=np.linalg.norm(forward);right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,forward);view=np.eye(4);view[:3,:3]=[right,up,-forward];view[:3,3]=-view[:3,:3]@eye
height=max(world[1]+2,(world[0]+2)*H/vw);proj=np.diag([2/(height*vw/H),2/height,-2/100,1]);proj[2,3]=-1;camera=proj@view
fonts={n:ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',n) for n in [13,15,17,20,24]};sizes={o['object_id']:o['size'] for o in d['scene']['objects']};colors={'unchanged':(45,121,95),'changed':(48,116,204),'added':(48,116,204),'removed':(161,168,177),'executed':(187,193,191)}

def screen(xyz):
 q=camera@np.r_[xyz,1];return ((q[0]/q[3]+1)*vw/2,(1-q[1]/q[3])*H/2)

def path_overlay(draw,path,color):
 poses=path['poses'];z=sizes[path['object_id']][2]+.03;points=[screen([*p[:2],z]) for p in poses];draw.line(points,fill=color,width=3)
 for x,y in points:draw.ellipse((x-2,y-2,x+2,y+2),fill=color)
 for pose in [poses[len(poses)//2],poses[-1]]:
  vertices=box_vertices(pose,sizes[path['object_id']])
  for i,j in [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]:draw.line([screen(vertices[i]),screen(vertices[j])],fill=color,width=1)

end=min(a.end if a.end is not None else d['duration'],d['duration']);assert 0<=a.start<end
requested=[a.start,(a.start+end)/2,end] if a.preview else np.minimum(a.start+np.arange(int(np.ceil((end-a.start)/a.speed*25))+1)*a.speed/25,end)
proc=None;out=a.output/'replanning-preview.mp4'
if not a.preview:proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1280x720','-r','25','-i','-','-an','-map_metadata','-1','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(out)],stdin=subprocess.PIPE)
audit=[];start=time.monotonic()
try:
 for index,t in enumerate(requested):
  j=min(np.searchsorted(src['time'],t,side='right'),len(src['time'])-1);i=max(0,j-1);u=np.clip((t-src['time'][i])/max(src['time'][j]-src['time'][i],1e-9),0,1)
  pos=(1-u)*src['positions'][i]+u*src['positions'][j];q0=src['quaternions'][i];q1=src['quaternions'][j];q1=np.where((q0*q1).sum(-1,keepdims=True)<0,-q1,q1);q=(1-u)*q0+u*q1;q/=np.linalg.norm(q,axis=-1,keepdims=True);rot=Rotation.from_quat(q,scalar_first=True).as_matrix();mat=np.tile(np.eye(4),(len(pos),1,1));mat[:,:3,:3]=rot;mat[:,:3,3]=pos
  GL.glViewport(0,0,W,H);GL.glClearColor(.98,.985,.975,1);GL.glClear(GL.GL_COLOR_BUFFER_BIT|GL.GL_DEPTH_BUFFER_BIT);GL.glViewport(0,0,vw,H)
  for mesh,gpu in zip(d['meshes'],gpus,strict=True):
   model=mat[mesh['body']];GL.glUniformMatrix4fv(uniforms['mvp'],1,True,np.asarray(camera@model,dtype='f4'));GL.glUniformMatrix4fv(uniforms['model'],1,True,np.asarray(model,dtype='f4'));GL.glUniform3fv(uniforms['color'],1,np.asarray(mesh['color'],dtype='f4')/255);GL.glBindVertexArray(gpu[0]);GL.glDrawElements(GL.GL_TRIANGLES,gpu[3],GL.GL_UNSIGNED_INT,None)
  rgb=np.frombuffer(GL.glReadPixels(0,0,W,H,GL.GL_RGB,GL.GL_UNSIGNED_BYTE),dtype='u1').reshape(H,W,3)[::-1].copy();image=Image.fromarray(rgb);draw=ImageDraw.Draw(image);state=at_time(d,float(t));current=state['current'];previous=state['previous']
  if current:
   if previous and t-current['time']<8:
    for path in previous['paths']:
     if state['changes'][path['object_id']] in ['changed','removed']:path_overlay(draw,path,colors['removed'])
   for path in current['paths']:
    if path['object_id'] not in state['completed']:path_overlay(draw,path,colors[state['changes'][path['object_id']]])
  if state['event']:
   oid=state['event']['object_id'];body=d['object_bodies'][str(oid)];x,y=screen(pos[body]+[0,0,.8]);draw.ellipse((x-23,y-23,x+23,y+23),outline='#d18540',width=4)
  for obj in d['scene']['objects']:
   body=d['object_bodies'][str(obj['object_id'])];x,y=screen(pos[body]+[0,0,obj['size'][2]/2+.18]);draw.text((x-4,y-8),str(obj['object_id']),font=fonts[13],fill='#263b36')
  for kind in ['start','goal']:draw_query_marker(image,screen([*d['scene'][kind][:2],.04]),kind,23 if kind=='start' else 30)
  draw=ImageDraw.Draw(image);draw.rectangle((0,0,1280,64),fill='#fafbf8');draw.text((24,18),d['title'],font=fonts[24],fill='#24332e');draw.text((950,22),f'{t:.1f} s',font=fonts[20],fill='#24332e')
  draw.rectangle((vw,64,W,H),fill='#fafbf8');draw.text((958,85),'Recorded plan',font=fonts[20],fill='#24332e')
  if current:
   draw.text((958,119),f"Update {current['call']} · {current['time']:.1f} s",font=fonts[15],fill='#61716a')
   active=[oid for oid in current['order'] if oid not in state['completed']]
   for row,oid in enumerate(active):
    y=160+row*42;status=state['changes'][oid];draw.ellipse((958,y+4,970,y+16),fill=colors[status]);draw.text((980,y),f'Object {oid}',font=fonts[17],fill='#24332e');draw.text((1090,y+2),status,font=fonts[13],fill='#61716a')
   if previous and t-current['time']<8:
    removed=[str(oid) for oid,status in state['changes'].items() if status=='removed'];executed=[str(oid) for oid,status in state['changes'].items() if status=='executed']
    if removed:draw.text((958,440),'Removed: '+', '.join(removed),font=fonts[17],fill='#65717d')
    if executed:draw.text((958,469),'Completed: '+', '.join(executed),font=fonts[17],fill='#61716a')
  if state['event']:draw.text((958,520),'External object moved',font=fonts[17],fill='#a96b30')
  for y,text,color in [(567,'Updated plan','#3074cc'),(594,'Unchanged geometry','#2d795f'),(621,'Previous plan','#a1a8b1')]:draw.line((958,y+9,982,y+9),fill=color,width=3);draw.text((992,y),text,font=fonts[15],fill='#61716a')
  draw.rectangle((0,658,vw,720),fill='#fafbf8');x=lambda stamp:24+(vw-48)*(stamp-a.start)/(end-a.start)
  draw.line((24,686,vw-24,686),fill='#d9e0dc',width=4)
  for event in d['events']:
   lo=max(a.start,event['motion_start_s']);hi=min(end,event['motion_end_s'])
   if lo<hi:draw.line((x(lo),686,x(hi),686),fill='#d18540',width=7)
  for plan in d['plans']:
   if a.start<=plan['time']<=end:draw.line((x(plan['time']),675,x(plan['time']),697),fill='#3074cc',width=2)
  draw.ellipse((x(t)-5,681,x(t)+5,691),fill='#24332e');draw.text((24,701),'Recorded execution time',font=fonts[13],fill='#61716a')
  draw.text((958,674),'Archived renderer preview',font=fonts[15],fill='#61716a')
  if a.preview or index in [0,len(requested)//2,len(requested)-1]:image.save(a.output/f'frame-{index:04d}.png')
  if proc:proc.stdin.write(image.tobytes())
  audit.append(dict(time=float(t),planCall=None if current is None else current['call'],changes=state['changes'],eventObject=None if state['event'] is None else state['event']['object_id']))
  if index%100==0:print(index,'/',len(requested),'elapsed',round(time.monotonic()-start,1),flush=True)
 if proc:proc.stdin.close();assert proc.wait()==0
finally:
 if proc and proc.poll() is None:proc.terminate();proc.wait()
 for vao,vbo,ebo,_ in gpus:GL.glDeleteVertexArrays(1,[vao]);GL.glDeleteBuffers(2,[vbo,ebo])
 GL.glDeleteProgram(program);GL.glDeleteRenderbuffers(2,[color_buffer,depth]);GL.glDeleteFramebuffers(1,[fbo]);ctx.free()
(a.output/'render-audit.json').write_text(json.dumps(dict(scope=d['scope'],recordingSHA256=d['recordingSHA256'],episodeSHA256=d['episodeSHA256'],frames=audit),separators=(',',':'))+'\n')
print('PASS native Viser replanning preview',flush=True)
