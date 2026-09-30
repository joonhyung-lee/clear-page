/* Run the real bridge timer against accumulated native checkpoint messages. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const queue=[],viewer={mutable:{current:{messageQueue:queue}}};
const root={__reactContainerTest:{memoizedProps:{value:viewer}}};
let tick;
const button={querySelector:()=>true};
const context={window:{__CLEAR_CHECKPOINT_REPLAY__:true,addEventListener(){}},
 document:{querySelector:s=>s==='#root'?root:s==='input'?{value:'4'}:{closest:()=>button}},
 parent:{postMessage(){}},setInterval:fn=>(tick=fn,1),clearInterval(){}};
vm.runInNewContext(fs.readFileSync('assets/playback-bridge.js','utf8'),context);
context.window.CLEAR_PLAYBACK_BRIDGE();
for(let i=0;i<10000;i++)queue.push({type:'SceneNodeUpdateMessage',name:'/agents/2',updates:{batched_positions:[i]}});
queue.push({type:'SceneNodeUpdateMessage',name:'/agents/2',updates:{batched_wxyzs:[1,0,0,0]}});
const camera={type:'SetCameraPositionMessage',position:[0,1,2]};queue.push(camera);
tick();assert.equal(queue.length,2,'Normal playback must coalesce superseded agent poses, not just explicit seeks');
assert.strictEqual(queue[0],camera);assert.equal(queue[1].updates.batched_positions[0],9999);
assert.deepEqual(Array.from(queue[1].updates.batched_wxyzs),[1,0,0,0]);
// A rewind recreates the batch. An old playhead's pose cannot overwrite it.
const reset={type:'BatchedMeshesMessage',name:'/agents/2',props:{batched_positions:[0]}};
queue.push(reset);tick();assert.equal(queue.length,2);assert.strictEqual(queue[1],reset);
context.window.__CLEAR_CHECKPOINT_REPLAY__=false;
queue.push({type:'SceneNodeUpdateMessage',name:'/agents/2',updates:{batched_positions:[2]}});
tick();assert.equal(queue.length,3,'Other recording types must retain their native queue');
console.log('PASS live checkpoint queue: latest pose, merged fields, rewind reset and other-scene isolation');
