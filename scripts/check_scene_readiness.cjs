/* Exercise the actual embed lifecycle while messages and renderer mounts arrive. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('assets/site.js','utf8');
const lifecycle=source.slice(source.indexOf('function sceneLifecycle()'),source.indexOf('// Classic script loading'));
let tick,events=[],posts=[],nodes={},refs={},playing=true,clicks=0;
const viewer={useSceneTree:{getAll:()=>nodes},mutable:{current:{nodeRefFromName:refs}}};
const root={__reactContainerTest:{memoizedProps:{value:viewer}}};
const button={querySelector:()=>playing,click(){playing=!playing;clicks++}};
const doc={querySelector:s=>s==='#root'?root:s==='canvas'||s==='input'?{}:{closest:()=>button}};
const context={window:{__CLEAR_CHECKPOINT_REPLAY__:true,addEventListener:(name,fn)=>events.push([name,fn])},document:doc,parent:{postMessage:m=>posts.push(m)},setInterval:fn=>(tick=fn,1),clearInterval(){},requestAnimationFrame:fn=>fn()};
vm.runInNewContext(lifecycle+';sceneLifecycle();',context);
nodes={a:{message:{type:'FrameMessage'}},b:{message:{type:'FrameMessage'}},c:{message:{type:'LabelMessage'}}};tick();assert.equal(posts.length,0);assert.equal(clicks,0,'Do not pause on empty frame/label nodes');
nodes={'/agents/2':{message:{name:'/agents/2',type:'BatchedMeshesMessage'}},'/terrain/0':{message:{name:'/terrain/0',type:'MeshMessage'}}};tick();assert.equal(posts.length,0,'Messages without mounted geometry must not expose a white iframe');
refs['/terrain/0']={traverse:fn=>fn({geometry:{attributes:{position:{count:3}}},visible:true})};tick();assert.equal(posts.length,0,'Wait for robot geometry as well as terrain');
refs['/agents/2']={traverse:fn=>fn({geometry:{attributes:{position:{count:0}}},visible:true})};tick();assert.equal(posts.length,0,'An empty GPU geometry is not ready');
nodes['/agents/deferred']={message:{name:'/agents/deferred',type:'BatchedMeshesMessage'}};
nodes['/terrain/hidden']={effectiveVisibility:false,message:{name:'/terrain/hidden',type:'MeshMessage'}};
refs['/agents/2']={traverse:fn=>fn({geometry:{attributes:{position:{count:3}}},visible:true})};tick();assert.equal(posts.length,1);assert.equal(posts[0].type,'clear-scene-ready');assert.equal(clicks,1);
tick();assert.equal(posts.length,1,'Readiness must be announced only once');
console.log('PASS preview retained through empty scene/messages/partial meshes; revealed after robot and terrain mount without waiting for deferred or hidden parts');

// Reduced motion stops initial autoplay after geometry exists, while preserving
// explicit playback and its offscreen pause/resume behavior.
playing=true;clicks=0;events=[];posts=[];
context.window.matchMedia=()=>({matches:true});
vm.runInNewContext(lifecycle+';sceneLifecycle();',context);
const visibility=events.find(([name])=>name==='message')[1];
visibility({source:context.parent,data:{type:'clear-scene-visible',visible:true}});
tick();assert.equal(playing,false,'Reduced motion must pause native autoplay after mounting');
assert.equal(clicks,1);tick();assert.equal(clicks,1,'Initial policy must run only once');
playing=true;tick();assert.equal(playing,true,'Explicit Play must remain available');
visibility({source:context.parent,data:{type:'clear-scene-visible',visible:false}});assert.equal(playing,false);
visibility({source:context.parent,data:{type:'clear-scene-visible',visible:true}});assert.equal(playing,true);
console.log('PASS reduced-motion initialization, explicit Play and offscreen pause/resume');
