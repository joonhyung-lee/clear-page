/* Recorded pose interpolation and swept footprint clearance. */
((root) => {
 function footprint(p,size){const c=Math.cos(p[2]),s=Math.sin(p[2]),a=size[0]/2,b=size[1]/2;return [[-a,-b],[a,-b],[a,b],[-a,b]].map(([x,y])=>[p[0]+x*c-y*s,p[1]+x*s+y*c]);}
 function overlap(p,size,wall){
  const box=footprint(p,size),c=Math.cos(p[2]),s=Math.sin(p[2]),rect=[[wall[0],wall[1]],[wall[2],wall[1]],[wall[2],wall[3]],[wall[0],wall[3]]];
  return [[1,0],[0,1],[c,s],[-s,c]].every(([x,y])=>{const u=box.map(p=>p[0]*x+p[1]*y),v=rect.map(p=>p[0]*x+p[1]*y);return Math.max(...u)>Math.min(...v)&&Math.max(...v)>Math.min(...u);});
 }
 function sample(flow,t){
  t=Math.max(0,Math.min(1,t));const hi=flow.times.findIndex(v=>v>=t);
  if(hi<=0)return flow.states[hi<0?flow.states.length-1:0];if(flow.times[hi]===t)return flow.states[hi];
  const lo=hi-1,a=(t-flow.times[lo])/(flow.times[hi]-flow.times[lo]);
  return flow.states[lo].map((path,i)=>({object:path.object,poses:path.poses.map((p,j)=>p.map((v,k)=>{const d=flow.states[hi][i].poses[j][k]-v;return v+a*(k===2?Math.atan2(Math.sin(d),Math.cos(d)):d);} ))}));
 }
 function blocked(a,b,size,walls){
  const turn=Math.atan2(Math.sin(b[2]-a[2]),Math.cos(b[2]-a[2])),steps=Math.max(2,Math.ceil(Math.hypot(b[0]-a[0],b[1]-a[1])/.05),Math.ceil(Math.abs(turn)/.05));
  for(let j=0;j<=steps;j++){const f=j/steps,p=[a[0]+f*(b[0]-a[0]),a[1]+f*(b[1]-a[1]),a[2]+f*turn];if(walls.some(w=>overlap(p,size,w)))return true;}return false;
 }
 root.CLEAR_FAILURE_GEOMETRY={footprint,overlap,sample,blocked};
})(typeof window==='undefined'?globalThis:window);
