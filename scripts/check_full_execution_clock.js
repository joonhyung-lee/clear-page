/* Exercise the actual shared clock beyond the old first-push video boundary. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const events = {};
const views = ['optimized', 'baseline'].map(kind => {
 const media = {duration: 40, currentTime: 0, readyState: 4, paused: true,
  play() { this.paused=false; return Promise.resolve(); }, pause() { this.paused=true; }, addEventListener() {}};
 const note = {};
 return {dataset: {executionClock:kind}, media, note, native:null,
  querySelector(selector) { return selector==='iframe.scene-ready'?this.native:selector==='.execution-clock-note'?note:media; },
  addEventListener() {}};
});
const context = vm.createContext({document: {querySelectorAll:()=>views, addEventListener:(type,fn)=>{events[type]=fn;}},
 syncEgoClock:(view,clock)=>{view.egoClock=clock;}});
const source=fs.readFileSync('assets/continuous-layout.js','utf8');
vm.runInContext(source.slice(source.indexOf('// One replay clock')),context);
function clock(time, playing) { events['clear-mpc-clock']({detail:{time,playing,speed:2}}); }
for(const time of [14,20,30,39]) {
 clock(time,true);
 for(const view of views) {
  assert.equal(view.media.currentTime,time); assert.equal(view.media.paused,false);
  assert.equal(view.egoClock.time,time); assert.equal(view.egoClock.playing,true);
  assert.equal(view.note.textContent,`${time.toFixed(1)} s · Recorded motion`);
 }
}
clock(40,false);
for(const view of views) {assert.equal(view.media.paused,true);assert.equal(view.note.textContent,'Recording complete · Final video frame');}
clock(5,false);
for(const view of views) {assert.equal(view.media.currentTime,5);assert.equal(view.egoClock.time,5);}
for(const view of views) view.native={contentWindow:{postMessage:(message)=>{view.command=message;}}};
clock(30,true);
for(const view of views) {assert.equal(view.command.time,30);assert.equal(view.media.paused,true);assert.equal(view.egoClock.time,30);}
console.log('PASS full replay clock: 14–40 s, replay seek, paired Ego and native seek');
