/* Replay the browser check's 24 -> 16 second seek through the actual bridge. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('scripts/check_learning_replay.py','utf8');
const predicate=source.match(/PLAYING_AFTER_SEEK = r'''([\s\S]*?)'''/)[1];
let tick,commit,playing=false;
const input={value:'24.0'},events=new Map(),parent={postMessage(){}};
const button={querySelector:()=>playing,click:()=>{playing=!playing;}};
const slider={__reactFiberNative:{memoizedProps:{step:.0001,onChange(time){commit=()=>{input.value=String(time);playing=false;};}}}};
const context={parent,window:{addEventListener:(type,fn)=>events.set(type,fn)},
 document:{querySelector(selector){
  if(selector==='input')return input;
  if(selector==='[role=slider]')return slider;
  if(selector==='.tabler-icon-player-pause-filled')return playing?{}:null;
  return {closest:()=>button};
 }},setInterval:fn=>(tick=fn,1),clearInterval(){}};
vm.createContext(context);vm.runInContext(fs.readFileSync('assets/playback-bridge.js','utf8'),context);
context.window.CLEAR_PLAYBACK_BRIDGE();
const ready=vm.runInContext('('+predicate+')',context);
events.get('message')({source:parent,data:{type:'clear-playback-command',time:16,playing:true}});
assert.equal(ready(),false,'The old 24-second playhead must not satisfy a pending 16-second seek');
tick();assert.equal(ready(),false,'Seek completion must wait for the native state commit');
commit();assert.equal(ready(),false,'A paused 16-second seek is not playing yet');
tick();assert.equal(playing,true);assert.equal(ready(),false,'Play must actually advance');
input.value='16.2';assert.equal(!!ready(),true);
playing=false;assert.equal(!!ready(),false,'A stopped timeline must not satisfy the playback check');
console.log('PASS asynchronous replay wait rejects stale playhead, pending seek and paused state');
