/* Exercise the real control renderer without a GPU or trajectory panels. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('assets/mpc-process.js','utf8');
const render=source.slice(source.indexOf(' function render()'),source.indexOf(' function syncContext('));
const attributes={},elements=new Map();
const root={
 dataset:new Proxy({}, {set(target,key,value){attributes['data-'+key.replace(/[A-Z]/g,c=>'-'+c.toLowerCase())]=value;target[key]=value;return true;}}),
 setAttribute:(key,value)=>attributes[key]=value,
 querySelector:key=>{if(!elements.has(key))elements.set(key,{style:{}});return elements.get(key);}
};
const state={root,data:{},play:{},slider:{},panels:[],playing:false,elapsed:0,playEnd:15,mode:'3d',syncContext(){}};
vm.createContext(state);vm.runInContext(render,state);
for(const end of [15,40]){
 state.playEnd=end;state.elapsed=end/2;vm.runInContext('render()',state);
 assert.equal(attributes['data-play-limit'],String(end),'Playback window must retain its DOM attribute');
 assert.equal(state.slider.value,.5);
 assert.equal(attributes['data-elapsed'],(end/2).toFixed(3));
 assert.equal(parseFloat(elements.get('.mpc-time-pin').style.left),14/end*100);
}
console.log('PASS real MPC control renderer: 15/40 s windows, slider, elapsed time and completion pin');
