/* Drive the actual page synchronization code with deterministic media clocks. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
class Media {
 constructor(){this._time=0;this.duration=40;this.readyState=4;this.paused=true;this.playbackRate=1;this.seeking=false;this.preload='none';this.handlers={};this.seeks=0;}
 get currentTime(){return this._time;}
 set currentTime(v){this._time=v;this.seeks++;}
 addEventListener(n,fn){(this.handlers[n]??=[]).push(fn);}
 emit(n){for(const f of this.handlers[n]||[])f();}
 play(){this.paused=false;return Promise.resolve();}
 pause(){this.paused=true;}
 tick(dt){if(!this.paused)this._time+=dt*this.playbackRate;}
}
function setup(){
 const main=new Media(),ego=new Media();let native=false,now=0;const handlers={},raf=[];
 const frame={contentWindow:{}};const inset={querySelector:()=>ego};
 const viewer={dataset:{},querySelector:s=>s==='.ego-inset'?inset:s==='.ego-inset video'?ego:s.startsWith('iframe')?(native?frame:null):main};
 const window={CLEAR_ASSET_REVISIONS:{'assets/media/test-ego.mp4':'1'},addEventListener:(n,f)=>(handlers[n]??=[]).push(f)};
 const context=vm.createContext({window,document:{querySelectorAll:()=>[viewer]},clearAssetURL:x=>x,
  performance:{now:()=>now*1000},requestAnimationFrame:f=>{raf.push(f);return raf.length;},cancelAnimationFrame:()=>{},console});
 const source=fs.readFileSync('assets/site.js','utf8');
 vm.runInContext(source.slice(source.indexOf('// One RGB inset')),context);
 vm.runInContext(source.slice(source.indexOf('// Source-window validation'),source.indexOf('// Detail views accompany')),context);
 context.attachEgoVideo(viewer,'test');
 return {main,ego,viewer,sync:(clock,mode)=>context.syncEgoClock(viewer,clock,mode),setNative:()=>{native=true;main.pause();main.emit('pause');},
  message:data=>{for(const fn of handlers.message||[])fn({data,source:frame.contentWindow});},
  tick:dt=>{now+=dt;main.tick(dt);ego.tick(dt);const todo=raf.splice(0);for(const fn of todo)fn(now*1000);}};
}
let failed=0;
for(const [name,test] of [
 ['native replay plays continuously instead of seeking each update',()=>{
  const s=setup();s.setNative();
  for(let i=0;i<100;i++){s.message({type:'clear-playback-time',time:i*.1,playing:true});s.tick(.1);}
  assert.equal(s.ego.paused,false,'Ego remains paused during native playback');
  assert.ok(s.ego.seeks<=2,`${s.ego.seeks} hard seeks in ten seconds`);
 }],
 ['video playback inherits speed without repeated seeking',()=>{
  const s=setup();s.main.playbackRate=2;s.main.play();s.main.emit('play');s.main.emit('ratechange');
  for(let i=0;i<100;i++){s.tick(.1);s.main.emit('timeupdate');}
  assert.ok(Math.abs(s.ego.playbackRate-2)<.1,'Ego does not inherit playback speed');
  assert.ok(s.ego.seeks<=2,`${s.ego.seeks} hard seeks at 2x`);
 }],
 ['native loop and pause resume keep the same clock',()=>{
  const s=setup();s.setNative();
  s.message({type:'clear-playback-time',time:13.9,playing:true});s.tick(.1);
  s.message({type:'clear-playback-time',time:0,playing:true});
  assert.ok(s.ego.currentTime<.05);s.tick(.1);
  s.message({type:'clear-playback-time',time:.1,playing:false});assert.equal(s.ego.paused,true);
  s.tick(2);s.message({type:'clear-playback-time',time:.1,playing:true});s.tick(.1);
  assert.ok(s.ego.currentTime>.1&&s.ego.currentTime<.25);
 }],
 ['buffering pauses Ego until the main decoder resumes',()=>{
  const s=setup();s.main.play();s.main.emit('playing');s.tick(.2);
  s.main.emit('waiting');assert.equal(s.ego.paused,true);
  s.main.emit('playing');assert.equal(s.ego.paused,false);
 }],
 ['external timeline remains authoritative over media events',()=>{
  const s=setup();s.viewer.dataset.executionClock='optimized';
  s.sync({time:3,playing:true,rate:2},'external');
  s.main.currentTime=1;s.main.emit('timeupdate');s.main.emit('pause');
  assert.equal(s.viewer._egoClockMode,'external');assert.equal(s.ego.paused,false);
  assert.equal(s.ego.currentTime,3);
 }],
 ['late Ego decoding adopts the paused external timeline',()=>{
  const s=setup();s.viewer.dataset.executionClock='optimized';s.ego.readyState=0;
  s.sync({time:8,playing:false,rate:2},'external');
  assert.equal(s.ego.preload,'auto','Paused seek does not load Ego');
  s.ego.readyState=4;s.ego.emit('loadeddata');
  assert.equal(s.ego.currentTime,8);assert.equal(s.ego.paused,true);
 }],
 ['explicit seek and pause stay synchronized',()=>{
  const s=setup();s.main.currentTime=8;s.main.emit('seeking');s.main.emit('seeked');
  assert.ok(Math.abs(s.ego.currentTime-8)<.05);s.main.pause();s.main.emit('pause');assert.equal(s.ego.paused,true);
 }],
]){try{test();console.log('PASS',name);}catch(e){failed++;console.error('FAIL',name,':',e.message);}}
process.exitCode=failed?1:0;
