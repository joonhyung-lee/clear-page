"""Render archived body-specific terrain replays without transferring another body's motion."""
import argparse,json,subprocess,time
from pathlib import Path
import numpy as np
import mujoco,imageio_ffmpeg
from PIL import Image,ImageDraw,ImageFont
from attention_terrain import PALETTE
from attention_lanes import draw_query_marker

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--preview',action='store_true');p.add_argument('--bodies',nargs='+',default=['spot','husky'])
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';fonts={n:ImageFont.truetype(font,n) for n in [13,17,20]}
for body in a.bodies:
    folder=a.source/('spot__stair_once' if body=='spot' else 'husky__ramp')
    model=mujoco.MjModel.from_binary_path(str(folder/(body+'.mjb')));state=mujoco.MjData(model)
    poses=np.load(folder/(body+'.npz'));result=json.loads((folder/'result.json').read_text())
    # Archive lighting stacks multiple lights plus the headlight and clips pastel surfaces.
    model.light_ambient[:]=0;model.light_diffuse[:]=0;model.light_specular[:]=0
    model.vis.headlight.ambient[:]=.4;model.vis.headlight.diffuse[:]=.5;model.vis.headlight.specular[:]=0
    recorded=poses['time'];duration=float(recorded[-1]);fps=25;speed=2
    original=model.geom_rgba.copy();original_mat=model.geom_matid.copy();semantic=original.copy()
    for i in range(model.ngeom):
        if model.geom_bodyid[i]!=0:continue
        name=model.geom(i).name
        color=PALETTE['ramp'] if 'ramp' in name else PALETTE['stair_tread'] if 'stair' in name or 'fixed_step' in name else PALETTE['flat'] if 'cell' in name or 'support' in name else (227,230,226)
        semantic[i,:3]=np.asarray(color)/255
    options=mujoco.MjvOption();options.geomgroup[:]=[1,1,1,0,0,0]
    main=mujoco.Renderer(model,height=720,width=880);small=mujoco.Renderer(model,height=264,width=352)
    def set_state(t):
        j=min(np.searchsorted(recorded,t,side='right'),len(recorded)-1);i=max(0,j-1)
        u=np.clip((t-recorded[i])/max(recorded[j]-recorded[i],1e-9),0,1)
        state.qpos[:]=(1-u)*poses['qpos'][i]+u*poses['qpos'][j]
        # Quaternion coordinates need shortest-arc interpolation, never scalar averaging.
        for joint in range(model.njnt):
            typ=model.jnt_type[joint];adr=model.jnt_qposadr[joint]
            if typ not in [mujoco.mjtJoint.mjJNT_FREE,mujoco.mjtJoint.mjJNT_BALL]:continue
            start=adr+3 if typ==mujoco.mjtJoint.mjJNT_FREE else adr
            q0=poses['qpos'][i,start:start+4];q1=poses['qpos'][j,start:start+4]
            if q0@q1<0:q1=-q1
            q=(1-u)*q0+u*q1;state.qpos[start:start+4]=q/np.linalg.norm(q)
        if model.nmocap:
            state.mocap_pos[:]=(1-u)*poses['mocap_pos'][i]+u*poses['mocap_pos'][j]
            q0=poses['mocap_quat'][i];q1=poses['mocap_quat'][j]
            q1=np.where((q0*q1).sum(-1,keepdims=True)<0,-q1,q1)
            q=(1-u)*q0+u*q1;state.mocap_quat[:]=q/np.linalg.norm(q,axis=-1,keepdims=True)
        mujoco.mj_forward(model,state)
    centers=[];yaws=[]
    for t in recorded:
        set_state(t);centers.append(state.xpos[1].copy());r=state.xmat[1].reshape(3,3);yaws.append(np.arctan2(r[1,0],r[0,0]))
    centers=np.asarray(centers);raw_centers=centers.copy();yaws=np.unwrap(yaws)
    assert np.ptp(centers[:,:2],axis=0).max()>1, 'Replay has no body displacement'
    if body=='spot':assert not any('arm' in (model.body(i).name or '').lower() for i in range(model.nbody))
    for i in range(1,len(centers)):
        alpha=1-np.exp(-(recorded[i]-recorded[i-1])/.18)
        centers[i]=centers[i-1]+alpha*(centers[i]-centers[i-1]);yaws[i]=yaws[i-1]+alpha*(yaws[i]-yaws[i-1])
    def render(renderer,eye,target,semantic_colors):
        model.geom_rgba[:]=semantic if semantic_colors else original
        model.geom_matid[:]=original_mat
        if semantic_colors:model.geom_matid[model.geom_bodyid==0]=-1
        camera=mujoco.MjvCamera();camera.lookat[:]=target;camera.distance=np.linalg.norm(target-eye)
        direction=target-eye
        camera.azimuth=np.degrees(np.arctan2(direction[1],direction[0]))
        camera.elevation=np.degrees(np.arctan2(direction[2],np.linalg.norm(direction[:2])))
        renderer.update_scene(state,camera=camera,scene_option=options)
        forward=target-eye;forward/=np.linalg.norm(forward)
        right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward)
        for cam in renderer.scene.camera:
            cam.pos[:]=eye;cam.forward[:]=forward;cam.up[:]=up
        return renderer.render()
    times=[0,duration/2,duration] if a.preview else np.minimum(np.arange(int(np.ceil(duration/speed*fps))+1)*speed/fps,duration)
    output=a.output/f'terrain-{body}-topdown-heading-ego.mp4';proc=None
    if not a.preview:
        proc=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1280x720','-r',str(fps),'-i','-','-an','-map_metadata','-1','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],stdin=subprocess.PIPE)
    started=time.monotonic();audit=[]
    try:
        for index,t in enumerate(times):
            set_state(t);center=np.array([np.interp(t,recorded,centers[:,k]) for k in range(3)])
            yaw=np.interp(t,recorded,yaws);heading=np.array([np.cos(yaw),np.sin(yaw),0.])
            wide=1-np.clip((t/speed-1.5)/1.5,0,1);wide=wide*wide*(3-2*wide)
            target=(1-wide)*center+wide*np.array([6.,6.,.2]);eye=target+np.array([0,-4-6*wide,7+8*wide])
            image=Image.new('RGB',(1280,720),(250,251,248));image.paste(Image.fromarray(render(main,eye,target,True)),(0,0))
            chase_eye=center-3.0*heading+[0,0,1.8];chase_target=center+.8*heading+[0,0,.1]
            image.paste(Image.fromarray(render(small,chase_eye,chase_target,True)),(904,52))
            rotation=state.xmat[1].reshape(3,3);ego_eye=state.xpos[1]+rotation @ np.array([.4,0,.15 if body=='spot' else .55]);ego_target=ego_eye+rotation @ np.array([1.,0,-.15])
            image.paste(Image.fromarray(render(small,ego_eye,ego_target,False)),(904,372))
            draw=ImageDraw.Draw(image);draw.rounded_rectangle((18,12,620,54),radius=7,fill=(250,251,248))
            draw.text((32,22),'Terrain replay  /  '+('Spot · Stairs' if body=='spot' else 'Husky · Ramp route'),font=fonts[20],fill='#24332e')
            for y,title in [(23,'Third-person · Heading'),(343,'Ego RGB')]:draw.text((907,y),title,font=fonts[20],fill='#24332e')
            for y in [48,368]:draw.rectangle((900,y,1260,y+272),outline='#b9c8be',width=2)
            draw.rounded_rectangle((18,422,278,704),radius=7,fill=(250,251,248),outline='#b9c8be');draw.text((34,434),'Minimap',font=fonts[17],fill='#24332e')
            def mini(p):return (36+p[0]*18.5,686-p[1]*18.5)
            for i in range(model.ngeom):
                if model.geom_bodyid[i] or model.geom_type[i]!=mujoco.mjtGeom.mjGEOM_BOX:continue
                xy=state.geom_xpos[i,:2];half=model.geom_size[i,:2]
                draw.rectangle([mini(xy+[-half[0],half[1]]),mini(xy+[half[0],-half[1]])],fill=tuple((semantic[i,:3]*255).astype(int)),outline='#a1aaa8')
            x,y=mini(state.xpos[1]);direction=heading[:2]*7;side=np.array([-heading[1],heading[0]])*4
            tip=mini(state.xpos[1,:2]+heading[:2]*.35)
            draw.polygon([tip,(x-side[0],y+side[1]),(x+side[0],y-side[1])],fill='#243b52')
            draw_query_marker(image,mini(raw_centers[0]),'start',19)
            path=result['planned_path'];goal=path[-1];draw_query_marker(image,mini([goal[1]+.5,goal[0]+.5]),'goal',25)
            draw=ImageDraw.Draw(image)
            for x,kind,label in [(910,'ramp','Ramp'),(1020,'stair_tread','Step'),(1120,'flat','Platform')]:
                draw.rectangle((x,675,x+14,689),fill=PALETTE[kind],outline='#526667');draw.text((x+20,672),label,font=fonts[13],fill='#24332e')
            if a.preview or index in [0,len(times)//2,len(times)-1]:image.save(a.output/f'terrain-{body}-frame-{index:04d}.png')
            if proc:proc.stdin.write(image.tobytes())
            audit.append(dict(time=float(t),bodyPosition=state.xpos[1].tolist(),heading=heading.tolist(),chaseEye=chase_eye.tolist(),chaseTarget=chase_target.tolist()))
            if index%100==0:print(body,index,'/',len(times),'elapsed',round(time.monotonic()-started,1),flush=True)
        if proc:proc.stdin.close();assert proc.wait()==0
    finally:
        if proc and proc.poll() is None:proc.terminate();proc.wait()
        main.close();small.close()
    metadata=dict(body=body,file=output.name,source=folder.name,sourceDuration=duration,frames=len(times),fps=fps,speed=speed,scene='Separate archived terrain scene, not the G1 parallel-terrain scene.',dynamics=result['provenance']['dynamics'],attention='No attention weights recorded for these observations; no attention layer is synthesized.',camera='Recorded base heading with 180 ms causal smoothing, synchronized native-pose ego RGB.',wheelMotion='Native replay transforms only; no invented wheel rotation.',audit=audit)
    (a.output/f'terrain-{body}-manifest.json').write_text(json.dumps(metadata,separators=(',',':'))+'\n')
    print('PASS',body,round(time.monotonic()-started,1),'s',flush=True)
