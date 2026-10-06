/* The clearance example must continue the paper's exact scene and references. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('assets/method-illustration.js','utf8');
const prefix=source.slice(source.indexOf(' const objects='),source.indexOf(' const controls='));
const api=vm.runInNewContext(prefix+';({scene,objects,references,validationState});',{reduced:{matches:true}});
for(const [t,blocked] of [[0,2],[1,1],[2,0]]){
 const state=api.validationState(t);
 assert.equal(state.clear.filter(v=>!v).length,blocked);
 assert.equal((api.scene('2d','validation',t).match(/data-clear="false"/g)||[]).length,blocked);
 assert.deepEqual(state.positions[0],api.objects[0].p);
}
for(const id of [1,2])assert.deepEqual(api.validationState(2).positions[id],api.references[id].at(-1));
assert.deepEqual(api.validationState(1).positions[2],api.objects[2].p,'Second object stays fixed until its turn');
assert.notDeepEqual(api.validationState(.5).positions[1],api.objects[1].p);
assert.deepEqual(api.validationState(0).positions,api.objects.map(o=>o.p),'Replay restores initial scene');
console.log('PASS shared geometry, ordered scene updates, blocked passages and final route clearance');
