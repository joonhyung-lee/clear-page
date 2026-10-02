/* Camera translation must follow the body while preserving a user's orbit. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Vector{
 constructor(x=0,y=0,z=0){this.set(x,y,z);}
 set(x,y,z){Object.assign(this,{x,y,z});return this;}
 clone(){return new Vector(this.x,this.y,this.z);}
 add(v){return this.set(this.x+v.x,this.y+v.y,this.z+v.z);}
 sub(v){return this.set(this.x-v.x,this.y-v.y,this.z-v.z);}
 dot(v){return this.x*v.x+this.y*v.y+this.z*v.z;}
 addScaledVector(v,s){return this.add(v.clone().set(v.x*s,v.y*s,v.z*s));}
 applyQuaternion(q){
  const {x,y,z}=this,ix=q.w*x+q.y*z-q.z*y,iy=q.w*y+q.z*x-q.x*z,iz=q.w*z+q.x*y-q.y*x,iw=-q.x*x-q.y*y-q.z*z;
  return this.set(ix*q.w-iw*q.x-iy*q.z+iz*q.y,iy*q.w-iw*q.y-iz*q.x+ix*q.z,iz*q.w-iw*q.z-ix*q.y+iy*q.x);
 }
 copy(v){return this.set(v.x,v.y,v.z);}
 toArray(){return [this.x,this.y,this.z];}
}
const rootQ={x:-Math.SQRT1_2,y:0,z:0,w:Math.SQRT1_2};
const close=(v,w)=>assert(v.toArray().every((x,i)=>Math.abs(x-w.toArray()[i])<1e-9));
const callbacks=[];let base=new Vector(-3,0,.76),eye=new Vector(),at=new Vector();
const camera={position:new Vector(),quaternion:{clone:()=>({set(x,y,z,w){return {x,y,z,w};}})},up:new Vector(),updateProjectionMatrix(){}};
const cameraControl={getPosition:v=>v.copy(eye),getTarget:v=>v.copy(at),updateCameraUp(){},setLookAt:(x,y,z,a,b,c)=>{eye.set(x,y,z);at.set(a,b,c);}};
const viewer={mutable:{current:{camera,cameraControl,nodeRefFromName:{'/body-1':{updateWorldMatrix(){},getWorldPosition:v=>v.copy(base).applyQuaternion(rootQ)}}}},useSceneTree:{get:()=>({wxyz:[rootQ.w,rootQ.x,rootQ.y,rootQ.z]})}};
const root={__reactContainerTest:{memoizedProps:{value:viewer}}};
const sandbox={window:{__CLEAR_BODY_CHASE__:true,addEventListener(){}},document:{querySelector:s=>s==='#root'?root:null},requestAnimationFrame:fn=>callbacks.push(fn),setInterval(){},parent:{}};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync('assets/playback-bridge.js','utf8'),sandbox);sandbox.window.CLEAR_PLAYBACK_BRIDGE();
callbacks.shift()();close(eye,new Vector(-5.6,-1.8,2.4).applyQuaternion(rootQ));close(at,new Vector(-2.4,0,.7).applyQuaternion(rootQ));
// A user pans/rotates/zooms, then the body advances and changes height.
eye.add(new Vector(1,2,.2));at.add(new Vector(.2,.3,0));const oldEye=eye.clone(),oldAt=at.clone();
base.add(new Vector(2,-1,.1));callbacks.shift()();
for(const [actual,expected]of [[eye,oldEye.clone().add(new Vector(2,-1,0).applyQuaternion(rootQ))],[at,oldAt.clone().add(new Vector(2,-1,0).applyQuaternion(rootQ))]])assert(actual.toArray().every((v,i)=>Math.abs(v-expected.toArray()[i])<1e-9));
// Backward timeline seek follows the base immediately without camera drift.
base.add(new Vector(-2,1,0));callbacks.shift()();close(eye,oldEye);
viewer.mutable.current.resetCameraPose();callbacks.shift()();
close(eye,new Vector(-5.6,-1.8,2.4).applyQuaternion(rootQ));
console.log('PASS native body chase, constant horizontal offset, preserved user camera, backward seek');
