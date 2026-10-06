"""Render the real wheel-actuated lower bypass using the relief presentation."""
import argparse,json,subprocess,time
from pathlib import Path
import numpy as np,mujoco,imageio_ffmpeg
from PIL import Image,ImageDraw,ImageFont
from attention_terrain import terrain_color,draw_minimap_terrain,draw_profile,PALETTE,LABELS
from attention_lanes import draw_query_marker
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--preview',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
scene=json.loads((a.source/'scene.json').read_text());route_data=json.loads((a.source/'route.json').read_text());result=json.loads((a.source/'result.json').read_text());route=np.array(route_data['route'])
model=mujoco.MjModel.from_binary_path(str(a.source/'task.mjb'));state=mujoco.MjData(model);poses=np.load(a.source/'task.npz');rb=model.body('base_husky').id
original=model.geom_rgba.copy();semantic=original.copy()
for i in range(model.ngeom):
 name=model.geom(i).name or ''
 if name.startswith('terrain_'):semantic[i,:3]=np.array(terrain_color(scene['terrain'][int(name.split('_')[1])]))/255
 elif name.startswith('wall_'):semantic[i,:3]=[.49,.52,.51]
 elif name=='floor':semantic[i,:3]=[.88,.90,.88]
 elif name.startswith('object_geom_'):semantic[i,:3]=[.23,.43,.35]
model.vis.headlight.ambient[:]=.45;model.vis.headlight.diffuse[:]=.5;model.vis.headlight.specular[:]=0
model.vis.global_.offwidth=1280;model.vis.global_.offheight=720
main=mujoco.Renderer(model,height=720,width=880);ego=mujoco.Renderer(model,height=264,width=352);options=mujoco.MjvOption();options.geomgroup[:]=[1,1,1,0,0,0]
fonts={n:ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',n) for n in [13,15,17,20]}
times=poses['time'];duration=float(times[-1]);centers=[]
for q in poses['qpos']:state.qpos[:]=q;mujoco.mj_forward(model,state);centers.append(state.xpos[rb].copy())
centers=np.array(centers);follow=centers.copy()
for i in range(1,len(follow)):
 alpha=1-np.exp(-(times[i]-times[i-1])/.35);follow[i]=follow[i-1]+alpha*(follow[i]-follow[i-1])

def restore(t):
 j=min(np.searchsorted(times,t,side='right'),len(times)-1);i=max(0,j-1);u=np.clip((t-times[i])/max(times[j]-times[i],1e-9),0,1)
 state.qpos[:]=(1-u)*poses['qpos'][i]+u*poses['qpos'][j]
 for joint in range(model.njnt):
  if model.jnt_type[joint]!=mujoco.mjtJoint.mjJNT_FREE:continue
  k=model.jnt_qposadr[joint]+3;q0=poses['qpos'][i,k:k+4];q1=poses['qpos'][j,k:k+4]
  if q0@q1<0:q1=-q1
  q=(1-u)*q0+u*q1;state.qpos[k:k+4]=q/np.linalg.norm(q)
 mujoco.mj_forward(model,state)

def render(renderer,eye,target,colors):
 model.geom_rgba[:]=colors
 cam=mujoco.MjvCamera();cam.lookat[:]=target;cam.distance=np.linalg.norm(target-eye);f=target-eye;f/=np.linalg.norm(f)
 cam.azimuth=np.degrees(np.arctan2(f[1],f[0]));cam.elevation=np.degrees(np.arctan2(f[2],np.linalg.norm(f[:2])))
 renderer.update_scene(state,camera=cam,scene_option=options)
 s=np.cross(f,[0,0,1]);s/=np.linalg.norm(s);up=np.cross(s,f)
 for c in renderer.scene.camera:c.pos[:]=eye;c.forward[:]=f;c.up[:]=up
 c=renderer.scene.camera[0];near=c.frustum_near;top=c.frustum_top;bottom=c.frustum_bottom
 aspect=880/720 if renderer is main else 4/3
 right=(top-bottom)*aspect/2
 projection=np.array([[near/right,0,0,0],[0,2*near/(top-bottom),(top+bottom)/(top-bottom),0],[0,0,-1,-2*near],[0,0,-1,0]])
 view=np.eye(4);view[:3,:3]=[s,up,-f];view[:3,3]=-view[:3,:3]@eye
 return renderer.render(),projection@view

def draw_path(image,matrix,points,color,width):
 layer=Image.new('RGBA',(880,720));draw=ImageDraw.Draw(layer)
 for p,q in zip(points[:-1],points[1:]):
  v=[matrix @ np.r_[xy[:2],.025,1] for xy in [p,q]]
  if min(x[3] for x in v)<=0:continue
  screen=[((x[0]/x[3]+1)*440,(1-x[1]/x[3])*360) for x in v]
  draw.line(screen,fill=color,width=width)
 image.paste(layer,(0,0),layer)

fps=25;speed=2;requested=[0,duration/2,duration] if a.preview else np.minimum(np.arange(int(np.ceil(duration/speed*fps))+1)*speed/fps,duration)
output=a.output/'mixed-terrain-husky-flat-bypass.mp4';proc=None
if not a.preview:proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1280x720','-r',str(fps),'-i','-','-an','-map_metadata','-1','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],stdin=subprocess.PIPE)
audit=[];started=time.monotonic()
try:
 for index,t in enumerate(requested):
  restore(t);center=np.array([np.interp(t,times,follow[:,k]) for k in range(3)]);wide=1-np.clip((t/speed-1.5)/1.5,0,1);wide=wide*wide*(3-2*wide)
  center=(1-wide)*center+wide*np.r_[np.array(scene['world_size'])/2,0]
  image=Image.new('RGB',(1280,720),(250,251,248));rgb,vp=render(main,center+[0,-(5+8*wide),8+11*wide],center,semantic);image.paste(Image.fromarray(rgb),(0,0))
  current=np.searchsorted(times,t,side='right');draw_path(image,vp,route,(74,124,202,170),5);draw_path(image,vp,centers[:current:3],(31,87,73,235),3)
  for kind in ['start','goal']:
   c=vp @ np.r_[scene[kind][:2],.03,1];q=c[:3]/c[3]
   if c[3]>0 and (abs(q[:2])<1).all():draw_query_marker(image,((q[0]+1)*440,(1-q[1])*360),kind,27 if kind=='start' else 35)
  rotation=state.xmat[rb].reshape(3,3);eye=state.xpos[rb]+rotation @ np.array([.38,0,.56]);target=eye+rotation @ np.array([1.,0,-.16]);rgb,_=render(ego,eye,target,original);image.paste(Image.fromarray(rgb),(904,52))
  draw=ImageDraw.Draw(image);draw.rounded_rectangle((18,12,620,54),radius=7,fill=(250,251,248));draw.text((32,22),'Mixed terrain  /  Husky · Flat bypass',font=fonts[20],fill='#24332e')
  draw.text((907,23),'Ego RGB',font=fonts[20],fill='#24332e');draw.rectangle((900,48,1260,320),outline='#b9c8be',width=2)
  panel=Image.new('RGB',(880,720),(250,251,248));draw_profile(ImageDraw.Draw(panel),scene['terrain'],state.xpos[rb],scene['world_size'],fonts);image.paste(panel.crop((288,422,563,705)),(938,350))
  draw=ImageDraw.Draw(image);draw.rounded_rectangle((18,422,278,704),radius=7,fill=(250,251,248),outline='#b9c8be');draw.text((34,434),'Minimap',font=fonts[17],fill='#24332e')
  scale=222/max(scene['world_size'])
  def mini(p):return (44+p[0]*scale,686-p[1]*scale)
  for l,b,r,u in scene['walls']:draw.rectangle([mini([l,u]),mini([r,b])],fill='#a5aaa8')
  draw_minimap_terrain(draw,mini,scene['terrain'],np.zeros(len(scene['terrain'])))
  for obj in scene['objects']:
   x,y=mini(obj['pose']);draw.rectangle((x-4,y-4,x+4,y+4),fill='#236143');draw.text((x+5,y-6),str(obj['object_id']),font=fonts[13],fill='#24332e')
  draw.line([mini(p) for p in route],fill='#4a7cca',width=2)
  if current>1:draw.line([mini(p) for p in centers[:current:3]],fill='#1f5749',width=2)
  x,y=mini(state.xpos[rb]);draw.ellipse((x-4,y-4,x+4,y+4),fill='#243b52')
  for kind in ['start','goal']:draw_query_marker(image,mini(scene[kind]),kind,19 if kind=='start' else 25)
  draw=ImageDraw.Draw(image);draw.rounded_rectangle((575,628,860,704),radius=7,fill=(250,251,248),outline='#b9c8be')
  for y,label,color in [(644,'Planned route','#4a7cca'),(674,'Recorded path','#1f5749')]:draw.line((592,y+8,626,y+8),fill=color,width=3);draw.text((639,y),label,font=fonts[15],fill='#24332e')
  for x,kind in zip([916,1020,1120],['ramp','stair_tread','flat']):draw.rectangle((x,675,x+14,689),fill=PALETTE[kind],outline='#526667');draw.text((x+20,672),LABELS[kind],font=fonts[13],fill='#24332e')
  if a.preview or index in [0,len(requested)//2,len(requested)-1]:image.save(a.output/f'mixed-terrain-husky-frame-{index:04d}.png')
  if proc:proc.stdin.write(image.tobytes())
  audit.append(dict(time=float(t),position=state.xpos[rb].tolist(),wheels=[float(state.qpos[model.jnt_qposadr[model.joint(n+'_wheel').id]]) for n in ['front_left','front_right','rear_left','rear_right']]))
  if index%100==0:print(index,'/',len(requested),round(time.monotonic()-started,1),'s',flush=True)
 if proc:proc.stdin.close();assert proc.wait()==0
finally:
 if proc and proc.poll() is None:proc.terminate();proc.wait()
 main.close();ego.close()
metadata=dict(file=output.name,frames=len(requested),fps=fps,speed=speed,sourceDuration=duration,scene=scene,route=route_data,physics={k:result[k] for k in ['status','task_success','dynamics','simulated_seconds','final_goal_distance','maximum_wall_penetration','maximum_object_displacement','forbidden_object_contact','controller_config','controller_hash','simulator']},attention='No attention inferred for this designed-route execution.',audit=audit)
(a.output/'mixed-terrain-husky-manifest.json').write_text(json.dumps(metadata,separators=(',',':'))+'\n')
print('PASS Husky flat bypass render',flush=True)
