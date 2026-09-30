/* Recorded geometry and route. Selection comes from the reference plan. */
window.clearOrderingMap=function(canvas,sample,progress,focus=null){
 const ctx=canvas.getContext('2d'),scene=sample.scene,W=560,H=420;
 const frames=sample.queryOnly?[[0,scene.start[0],scene.start[1],scene.start[2]||0,scene.objects.map(o=>o.pose),0]]:sample.rollout;
 if(canvas.height!==H)canvas.height=H;
 const time=frames[0][0]+progress*(frames.at(-1)[0]-frames[0][0]);let k=frames.findIndex(f=>f[0]>=time);if(k<0)k=frames.length-1;
 const a=frames[Math.max(0,k-1)],b=frames[k],u=(time-a[0])/(b[0]-a[0]||1),mix=(x,y)=>x+(y-x)*u;
 const margin=38,scale=Math.min((W-2*margin)/scene.world_size[0],(H-2*margin)/scene.world_size[1]);
 const ox=(W-scene.world_size[0]*scale)/2,oy=(H+scene.world_size[1]*scale)/2,xy=p=>[ox+p[0]*scale,oy-p[1]*scale];
 ctx.clearRect(0,0,W,H);ctx.fillStyle='#fafbf8';ctx.fillRect(0,0,W,H);ctx.font=Math.max(13,10.5*W/(canvas.clientWidth||W))+'px Arial';
 const line=(points,color,width=2,dash=[])=>{if(!points.length)return;ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();ctx.setLineDash([]);};
 const circle=(p,r,fill,stroke='#47604b')=>{ctx.beginPath();ctx.arc(...p,r,0,2*Math.PI);ctx.fillStyle=fill;ctx.fill();ctx.strokeStyle=stroke;ctx.lineWidth=1.8;ctx.stroke();};
 const label=(text,p,color='#3f5545')=>{ctx.font=Math.max(13,10.5*W/(canvas.clientWidth||W))+'px Arial';const width=ctx.measureText(text).width;ctx.fillStyle='#fafbf8ed';ctx.fillRect(p[0]-3,p[1]-13,width+6,18);ctx.fillStyle=color;ctx.fillText(text,...p);};
 for(const t of scene.terrain){const[l,b,r,t0]=t.bounds;ctx.fillStyle='#ecebe0';ctx.fillRect(ox+l*scale,oy-t0*scale,(r-l)*scale,(t0-b)*scale);}
 for(const[l,b,r,t]of scene.walls){ctx.fillStyle='#bdc3bd';ctx.fillRect(ox+l*scale,oy-t*scale,(r-l)*scale,(t-b)*scale);}
 const route=sample.queryOnly?[]:frames.map(f=>xy(f.slice(1,3)));line(route,'#91a692',2.3,[5,4]);if(!sample.queryOnly)line([...route.slice(0,k),xy([mix(a[1],b[1]),mix(a[2],b[2])])],'#3c6347',3);
 for(let j=20;j<route.length;j+=35){const prev=route[j-3],p=route[j],angle=Math.atan2(p[1]-prev[1],p[0]-prev[0]);line([[p[0]-6*Math.cos(angle-.5),p[1]-6*Math.sin(angle-.5)],p,[p[0]-6*Math.cos(angle+.5),p[1]-6*Math.sin(angle+.5)]],'#829a83',1.6);}
 const order=sample.rank.map((rank,i)=>({rank,i})).filter(o=>o.rank>=0).sort((a,b)=>a.rank-b.rank),palette=['#c4936a','#83a47e','#8e9faf'];
 let active=null;
 for(const o of order){
  const moving=[];for(let j=1;j<frames.length;j++)if(Math.hypot(frames[j][4][o.i][0]-frames[j-1][4][o.i][0],frames[j][4][o.i][1]-frames[j-1][4][o.i][1])>.005)moving.push(j);
  if(moving.length&&time<=frames[moving.at(-1)][0]){active=o.i;break;}
 }
 for(const p of sample.paths){const rank=sample.rank[p.object],color=palette[rank%palette.length],points=p.poses.map(xy);line(points,color,2,[3,3]);const end=points.at(-1),prev=points.at(-2)||points[0],angle=Math.atan2(end[1]-prev[1],end[0]-prev[0]);line([[end[0]-7*Math.cos(angle-.5),end[1]-7*Math.sin(angle-.5)],end,[end[0]-7*Math.cos(angle+.5),end[1]-7*Math.sin(angle+.5)]],color,2);}
 const hits=[];
 scene.objects.forEach((obj,i)=>{
  const rank=sample.rank[i],selected=rank>=0,color=selected?palette[rank%palette.length]:'#d1d5ce',initial=xy(obj.pose),pos=xy([mix(a[4][i][0],b[4][i][0]),mix(a[4][i][1],b[4][i][1])]);
  const yaw=a[4][i][2]+u*Math.atan2(Math.sin(b[4][i][2]-a[4][i][2]),Math.cos(b[4][i][2]-a[4][i][2])),w=obj.size[0]*scale,h=obj.size[1]*scale;
  if(selected){ctx.save();ctx.translate(...initial);ctx.rotate(-obj.pose[2]);ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.setLineDash([3,3]);ctx.strokeRect(-w/2,-h/2,w,h);ctx.restore();}
  ctx.save();ctx.translate(...pos);ctx.rotate(-yaw);ctx.fillStyle=color;ctx.strokeStyle=focus===i?'#253f30':selected?'#698060':'#a9b0a5';ctx.lineWidth=focus===i||active===i?3:1.2;ctx.fillRect(-w/2,-h/2,w,h);ctx.strokeRect(-w/2,-h/2,w,h);ctx.restore();
  if(selected){circle([pos[0],pos[1]-h/2-13],9,'#fff',color);ctx.fillStyle='#4c6148';ctx.font=Math.max(11,9*W/(canvas.clientWidth||W))+'px Arial';ctx.textAlign='center';ctx.fillText(String(rank+1),pos[0],pos[1]-h/2-9);ctx.textAlign='left';}
  label('Object '+obj.object_id,[pos[0]-w/2,pos[1]+h/2+17],selected?'#4d6649':'#899185');hits.push({i,x:pos[0],y:pos[1]});
 });
 const start=xy(scene.start),goal=xy(scene.goal);circle(start,5,'#45694f');circle(goal,6,'#fff');
 label('Start',[start[0]-16,start[1]-13]);label('Goal',[goal[0]-12,goal[1]-14]);
 const robot=xy([mix(a[1],b[1]),mix(a[2],b[2])]);circle(robot,5,'#fff','#2e533b');
 canvas.dataset.selected=order.map(o=>scene.objects[o.i].object_id).join(',');canvas.dataset.active=active===null?'':String(active);canvas.dataset.time=time.toFixed(3);canvas._objectHits=hits;
 canvas.setAttribute('aria-label',(sample.queryOnly?'Top-down unexecuted scene query. Predicted object paths. ':'Top-down recorded route from start to goal. ')+(order.length?'Selected objects in order: '+order.map(o=>scene.objects[o.i].object_id).join(', '):(sample.queryOnly?'No interaction sampled.':'No object interaction in the recorded plan.')));
 return{time,active};
};
