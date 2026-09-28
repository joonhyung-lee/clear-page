"""Export actual palm tracking and direct joint MPC replays with ego contact scores.

Private inputs never enter the published manifest. Contact probabilities are
recomputed on segmented, replayed ego RGB-D using the supplied learned checkpoint.
They are a visualization, not a claim of archived controller telemetry.
"""
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path
import imageio_ffmpeg
import mujoco
import numpy as np
import torch
import viser
from PIL import Image
from contact_surface import ContactSurface, smooth_scores
from scene_annotations import outlined_anchors
from clear.mj_util.contact_net import ContactNet, push_frame, K_PTS
from clear.mj_util.pointcloud import intrinsics
from replay_geometry import mesh, add

p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('optimized',type=Path);p.add_argument('contact_checkpoint',type=Path);args=p.parse_args()
root=Path(__file__).resolve().parents[1];manifest=[];torch.set_num_threads(2)
net=ContactNet();net.load_state_dict(torch.load(args.contact_checkpoint,map_location='cpu',weights_only=False)['state_dict']);net.eval()
width,height=480,360
for key,folder in [('mpc-baseline',args.baseline),('mpc-optimized',args.optimized)]:
 ours=key=='mpc-optimized';tint=np.array((146,187,145) if ours else (207,154,151),dtype=np.uint8)
 a=dict(np.load(folder/'task.npz',allow_pickle=False));roll=dict(np.load(folder/'task.rollouts.npz',allow_pickle=False));meta=json.loads(str(roll['metadata']));cfg=json.loads((folder/'config.json').read_text())
 assert meta['executed'] and not meta['fixed_palms'] and bool(meta['contact_palms'])==ours
 assert meta['selector']==('laqdpp' if ours else 'topk') and np.isfinite(roll['eef_world']).all()
 assert hashlib.sha256(args.contact_checkpoint.read_bytes()).hexdigest()==cfg['contact_checkpoint_sha256']
 if ours:assert cfg['contact_palm_controller']['high_level_actor_used'] is False
 oid=int(roll['object_id'][0]);ids=np.flatnonzero(roll['object_id']==oid);start=float(roll['time_s'][ids[0]]);end=float(roll['valid_until_s'][ids[-1]])
 # Ten hertz is the recorded physical state cadence. Both panels retain time.
 times=np.arange(start,end-1e-6,.1);indices=np.searchsorted(a['time'],times-1e-6);assert np.max(abs(a['time'][indices]-times))<1e-5
 references=json.loads(str(a['reference_paths']));ref=np.array(next(x['poses'] for x in references if x['object_id']==oid))[:,:2]
 lengths=np.r_[0,np.cumsum(np.linalg.norm(np.diff(ref,axis=0),axis=1))]
 anchors=np.column_stack([np.interp(np.linspace(0,lengths[-1],5),lengths,ref[:,j]) for j in range(2)]+[np.full(5,1.32)])
 m=mujoco.MjModel.from_binary_path(str(folder/'task.mjb'));data=mujoco.MjData(m)
 target=mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_BODY,'object/box' if oid==0 else 'object_'+str(oid)+'/box')
 geoms=np.flatnonzero(m.geom_bodyid==target);assert len(geoms)
 cam=mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_CAMERA,'ego');kinv=np.linalg.inv(intrinsics(m,cam,width,height))
 yy,xx=np.mgrid[:height,:width];pixels=np.stack([xx,yy,np.ones_like(xx)],axis=-1).reshape(-1,3)
 renderer=mujoco.Renderer(m,height=height,width=width);opt=mujoco.MjvOption();opt.geomgroup[5]=1;opt.sitegroup[:]=0
 server=viser.ViserServer(host='127.0.0.1',port=8101,verbose=False);server.gui.configure_theme(show_logo=False,show_share_button=False);server.scene.world_axes.visible=False
 server.initial_camera.position=(2.25,-2.7,2.5);server.initial_camera.look_at=(0,.7,.75);server.initial_camera.fov=.85
 anchor=server.scene.add_frame('/tracking',show_axes=False)
 bodies={i:server.scene.add_frame(f'/tracking/body-{i}',show_axes=False) for i in range(m.nbody)}
 for i in range(m.ngeom):
  if m.geom_group[i]==3:continue
  rgba=m.geom_rgba[i].copy();mat=m.geom_matid[i]
  if mat>=0:rgba=m.mat_rgba[mat]
  if rgba[3]<=0:continue
  h=add(server,f'/tracking/body-{m.geom_bodyid[i]}/geom-{i}',mesh(m,i),m.geom_pos[i],m.geom_quat[i],tuple((rgba[:3]*255).astype(int)))
  if m.geom_bodyid[i]==0 and int(m.geom_type[i])!=0:h.opacity=.20
 outlined_anchors(server,'/tracking/waypoint-anchors',anchors,tuple(tint),.065)
 ref3=np.column_stack([ref,np.full(len(ref),1.32)]).astype(np.float32)
 server.scene.add_line_segments('/tracking/reference-path',points=np.stack([ref3[:-1],ref3[1:]],axis=1),colors=tuple(tint),line_width=5)
 surface=ContactSurface(server,m,int(geoms[0]),target,f'/tracking/body-{target}/contact-field',tint)
 paths=[];shape=roll['eef_world'].shape;segments=(shape[2]-1)*2
 for n in range(shape[1]):paths.append(server.scene.add_line_segments(f'/tracking/candidate-{n}',points=np.zeros((segments,2,3),np.float32),colors=tuple(tint),line_width=1))
 chosen=server.scene.add_line_segments('/tracking/applied-candidate',points=np.zeros((segments,2,3),np.float32),colors=tuple(tint),line_width=4)
 temp=Path(tempfile.mktemp(suffix='.mp4',prefix='clear-ego-'))
 proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{width}x{height}','-framerate','10','-i','-','-an','-map_metadata','-1','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(temp)],stdin=subprocess.PIPE)
 visible_frames=0;projections=[]
 def ego_contact():
  renderer.update_scene(data,camera='ego',scene_option=opt);rgb=renderer.render().copy()
  renderer.enable_depth_rendering();renderer.update_scene(data,camera='ego',scene_option=opt);depth=renderer.render().copy();renderer.disable_depth_rendering()
  renderer.enable_segmentation_rendering();renderer.update_scene(data,camera='ego',scene_option=opt);seg=renderer.render().copy();renderer.disable_segmentation_rendering()
  mask=np.isin(seg[:,:,0],geoms)&(seg[:,:,1]==int(mujoco.mjtObj.mjOBJ_GEOM))&np.isfinite(depth)&(depth>1e-4)&(depth<12)
  flat=np.flatnonzero(mask.ravel())
  if len(flat)<12:surface.hide();return rgb,False
  local=(pixels[flat]@kinv.T)*depth.ravel()[flat,None];local*=np.array([1,-1,-1])
  world=local @ data.cam_xmat[cam].reshape(3,3).T+data.cam_xpos[cam]
  nearest=int(np.argmin(np.linalg.norm(ref-data.xpos[target,:2],axis=1)));direction=ref[min(nearest+1,len(ref)-1)]-data.xpos[target,:2]
  if np.linalg.norm(direction)<1e-5:direction=ref[-1]-ref[-2]
  selected=np.random.default_rng(0).choice(len(world),K_PTS,replace=len(world)<K_PTS)
  pts=torch.tensor(world[selected],dtype=torch.float32)[None];colors=torch.tensor(rgb.reshape(-1,3)[flat[selected]]/255.,dtype=torch.float32)[None]
  loc,*_=push_frame(pts,torch.tensor(direction,dtype=torch.float32)[None])
  with torch.no_grad():logits,_,_=net(loc,colors,torch.tensor([cfg['contact_height']],dtype=torch.float32));prob=logits.softmax(-1)[0].numpy()
  # Display relative score per frame. No unobserved object surfaces are filled.
  intensity=prob/prob.max();heat=smooth_scores(world,world[selected],intensity)
  heat_image=np.zeros((height,width));heat_image.ravel()[flat]=heat
  alpha=(.76*heat)[:,None];out=rgb.copy().reshape(-1,3);out[flat]=np.round((1-alpha)*out[flat]+alpha*tint).astype(np.uint8)
  surface.update(data,cam,np.linalg.inv(kinv),depth,mask,heat_image)
  return out.reshape(height,width,3),True
 def update(k):
  data.qpos[:]=a['qpos'][k];mujoco.mj_forward(m,data);anchor.position=(-float(data.qpos[0]),-float(data.qpos[1]),0)
  for i,h in bodies.items():h.position=data.xpos[i].copy();h.wxyz=data.xquat[i].copy()
  t=float(a['time'][k]);j=int(np.searchsorted(roll['time_s'],t+1e-7,side='right')-1)
  valid=j>=0 and t<float(roll['valid_until_s'][j])-1e-7 and roll['object_id'][j]==oid
  for h in paths:h.visible=bool(valid)
  chosen.visible=bool(valid)
  if valid:
   elite=set(roll['elite_indices'][j].tolist())
   for n,h in enumerate(paths):
    p=roll['eef_world'][j,n];h.points=np.stack([p[:-1],p[1:]],axis=2).reshape(-1,2,3).astype(np.float32)
    c=tint if n in elite else np.round(.42*tint+.58*245).astype(np.uint8)
    h.colors=np.broadcast_to(c,(segments,2,3)).copy();h.line_width=2 if n in elite else 1
   chosen.points=paths[int(roll['applied_candidate'][j])].points.copy()
  return ego_contact()
 try:
  recording=None
  for frame,k in enumerate(indices):
   if recording is not None:recording.insert_sleep(.1)
   rgb,visible=update(k);visible_frames+=int(visible)
   if frame==0:
    recording=server.get_scene_serializer();Image.fromarray(rgb).save(root/'assets/media'/f'{key}-ego.png')
   proc.stdin.write(rgb.tobytes())
   if frame%50==0:print(key,frame,'/',len(indices),flush=True)
  recording.insert_sleep(.1)
  (root/'assets/recordings'/f'{key}.viser').write_bytes(recording.serialize())
 finally:
  proc.stdin.close();code=proc.wait();renderer.close();server.stop()
 assert code==0;temp.replace(root/'assets/media'/f'{key}-ego.mp4')
 manifest.append({'scene':key,'controller':'Cartesian palm tracking' if ours else 'Direct joint CEM port','selector':meta['selector'],'searchCandidates':24,'executionPreviewRows':0 if ours else 1,'elites':roll['elite_indices'].shape[1],'horizon':meta['horizon_s'],'step':meta['step_s'],'seed':cfg['seed'],'duration':round(len(times)/10,2),'recordedPopulations':len(ids),'displayAnchors':5,'contactField':'Learned contact scores recomputed on segmented replayed ego RGB-D, normalized by the maximum score in each frame. Not archived controller telemetry.','contactVisibleFrames':visible_frames,'frames':len(times),'scope':'First object interaction from an archived development comparison. Controllers differ in their action representation and selection. This is not an isolated selector ablation.'})
 print(key,'complete',len(times)/10,'seconds',visible_frames,'contact frames',flush=True)
(root/'assets/mpc-comparison.json').write_text(json.dumps(manifest,indent=2)+'\n')
