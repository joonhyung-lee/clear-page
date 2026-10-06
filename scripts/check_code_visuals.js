/* Exercise actual native feature/selection focus messages without a renderer. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const names=['/features/embodiment','/features/objects','/features/scene','/selection/participation','/selection/order'];
const nodes=new Map(names.map(k=>[k,{visibility:true}]));const listeners={},changes=[];
const viewer={useSceneTree:{get:k=>nodes.get(k)},sceneTreeActions:{updateNodeAttributes:(name,update)=>{Object.assign(nodes.get(name),update);changes.push(name);}}};
const root={__reactContainerTest:{memoizedProps:{value:viewer}}};let tick;const parent={};
const context={parent,Set,document:{querySelector:()=>root},setInterval:fn=>(tick=fn,1),clearInterval:()=>{},window:{addEventListener:(type,fn)=>listeners[type]=fn}};
vm.createContext(context);vm.runInContext(fs.readFileSync('assets/code-layer-bridge.js','utf8'),context);context.window.CLEAR_CODE_LAYER_BRIDGE();tick();
assert(nodes.get('/features/embodiment').visibility);assert(!nodes.get('/features/objects').visibility);
listeners.message({source:parent,data:{type:'clear-code-focus',focus:'objects',stage:'order'}});
assert(!nodes.get('/features/embodiment').visibility);assert(nodes.get('/features/objects').visibility);assert(nodes.get('/selection/order').visibility);
listeners.message({source:parent,data:{type:'clear-code-focus',focus:'scene',stage:'context'}});
assert(nodes.get('/features/scene').visibility);assert(!nodes.get('/selection/order').visibility);assert(!nodes.get('/selection/participation').visibility);
const count=changes.length;listeners.message({source:{},data:{type:'clear-code-focus',focus:'objects'}});assert.strictEqual(changes.length,count);
listeners.message({source:parent,data:{type:'clear-scene-visible',visible:false}});tick();assert.strictEqual(changes.length,count);
console.log('PASS native component focus, participation/order overlays and parent validation without moving scene geometry');
// User controls must start a pending native scene even with auto-start disabled.
{
 class Element {
  constructor(){this.listeners={};this.value='0';this.textContent='';this.dataset={};}
  addEventListener(type,fn){this.listeners[type]=fn;}
  fire(type){this.listeners[type]?.();}
 }
 const play=new Element(),replay=new Element(),slider=new Element(),output=new Element(),jump=new Element();jump.dataset.replayJump='4';
 const figure=new Element();figure.dataset.nativeExample='generation';
 const viewer=new Element();let frame=null,loading=false,launches=0;
 const sent=[];const launch={click(){launches++;loading=true;}};
 viewer.querySelector=selector=>selector==='.launch'?launch:selector==='iframe,.viewer-status'?(frame||loading):selector==='iframe'||selector==='iframe.scene-ready'?frame:null;
 figure.querySelector=selector=>({'.viewer':viewer,'input[type=range]':slider,'[data-native-play]':play,output,'[data-native-replay]':replay})[selector]||null;
 figure.querySelectorAll=selector=>selector==='[data-replay-jump]'?[jump]:[];
 const sandbox={window:{CLEAR_CODE_NATIVE:{execution:{duration:122.5}},addEventListener:()=>{}},document:{querySelectorAll:()=>[figure]},observeAutomaticScene:()=>{}};
 vm.createContext(sandbox);vm.runInContext(fs.readFileSync('assets/code-visuals.js','utf8'),sandbox);
 replay.fire('click');assert.strictEqual(launches,1);
 slider.value='3';slider.fire('input');assert.strictEqual(launches,1,'Do not restart a loading scene');
 frame={contentWindow:{postMessage:m=>sent.push(m)}};loading=false;viewer.fire('scene-settled');
 let command=sent.filter(m=>m.type==='clear-playback-command').at(-1);assert.strictEqual(command.time,3);assert.strictEqual(command.playing,false);
 jump.fire('click');command=sent.at(-1);assert.strictEqual(command.time,4);assert.strictEqual(command.playing,false);
 replay.fire('click');command=sent.at(-1);assert.strictEqual(command.time,0);assert.strictEqual(command.playing,true);assert.strictEqual(launches,1);
 console.log('PASS Replay starts 3D, loading preserves latest seek, and repeated controls reuse the native scene');
}
