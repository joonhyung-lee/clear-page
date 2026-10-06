/* Run the real plot player with the published recordings and controlled clocks. */
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
async function check(reduce){
 const observers=[],frames=new Map(),events=[],docEvents={},controls={};let id=0;
 for(const key of ['[data-spot-play]','[data-spot-replay]','input','[data-spot-time]','.spot-loading'])controls[key]={value:0};
 const buttons=['2d','3d'].map(view=>({dataset:{spotView:view},setAttribute(){}}));
 const panels=['optimized','baseline'].map(key=>{
  const ctx=new Proxy({},{get:(o,k)=>o[k]||(()=>{})});
  const canvas={dataset:{},clientWidth:300,getContext:()=>ctx,addEventListener(){},setPointerCapture(){}};
  const text={};return {dataset:{spotProcess:key},canvas,text,querySelector:s=>s==='canvas'?canvas:text};
 });
 const root={dataset:{},querySelector:s=>controls[s],querySelectorAll:s=>s==='[data-spot-process]'?panels:buttons,dispatchEvent:e=>events.push(e.detail)};
 const sandbox={console,document:{hidden:false,querySelector:()=>root,addEventListener:(name,fn)=>docEvents[name]=fn},reduced:{matches:reduce,addEventListener(){}},CustomEvent:class{constructor(type,props){Object.assign(this,props);}},IntersectionObserver:class{constructor(fn){observers.push(fn);}observe(){}},requestAnimationFrame:fn=>{frames.set(++id,fn);return id;},cancelAnimationFrame:i=>frames.delete(i)};
 sandbox.window=sandbox;const context=vm.createContext(sandbox);
 sandbox.loadScript=async path=>vm.runInContext(fs.readFileSync(path,'utf8'),context);
 vm.runInContext(fs.readFileSync('assets/spot-eef.js','utf8'),context);
 const tick=t=>{const calls=[...frames.values()];frames.clear();calls.forEach(fn=>fn(t));};
 observers[0]([{isIntersecting:true}]);await new Promise(setImmediate);
 assert.equal(controls['.spot-loading'].hidden,true);assert.equal(root.dataset.elapsed,'0.0000');
 assert.equal(frames.size,reduce?0:1);assert.equal(events.at(-1).group,'spot');
 if(reduce)controls['[data-spot-play]'].onclick();
 tick(100);tick(1100);assert.equal(root.dataset.elapsed,'2.0000');
 controls['[data-spot-play]'].onclick();
 const data=context.CLEAR_SPOT_EEF,end=Math.max(...Object.values(data).map(r=>r.duration));
 // Exact saved timestamps survive seeking and both presentation modes.
 for(const panel of panels){const rows=data[panel.dataset.spotProcess].observed;
  for(const row of [rows[0],rows[100],rows.at(-1)]){
   controls.input.value=row[0]/end;controls.input.oninput();
   assert.deepEqual(JSON.parse(panel.canvas.dataset.eef),Array.from(row.slice(1,4)));
   assert.deepEqual(JSON.parse(panel.canvas.dataset.object),Array.from(row.slice(4,7)));
   const saved=root.dataset.elapsed;buttons[0].onclick();assert.equal(panel.canvas.height,560);buttons[1].onclick();assert.equal(root.dataset.elapsed,saved);assert.equal(panel.canvas.height,420);
  }
 }
 controls.input.value=1;controls.input.oninput();
 assert.equal(+panels[1].canvas.dataset.time,data.baseline.duration);assert.equal(+panels[0].canvas.dataset.time,data.optimized.duration);
 assert.match(panels[1].text.textContent,/Toppled/);
 assert.equal(panels[0].canvas.dataset.coordinateBounds,panels[1].canvas.dataset.coordinateBounds);
 controls['[data-spot-replay]'].onclick();tick(2000);tick(3000);assert.equal(root.dataset.elapsed,'2.0000');
 observers[0]([{isIntersecting:false}]);tick(12000);assert.equal(root.dataset.elapsed,'2.0000');assert.equal(events.at(-1).playing,false);
 observers[0]([{isIntersecting:true}]);tick(13000);tick(14000);assert.equal(root.dataset.elapsed,'4.0000');
 sandbox.document.hidden=true;docEvents.visibilitychange();tick(20000);assert.equal(root.dataset.elapsed,'4.0000');
 sandbox.document.hidden=false;docEvents.visibilitychange();tick(21000);tick(22000);assert.equal(root.dataset.elapsed,'6.0000');
 console.log('PASS Spot recorded EEF: source seeks, 2D/3D clock, endpoint clamp, viewport pause/resume; reduced motion='+reduce);
}
(async()=>{await check(false);await check(true);})().catch(e=>{console.error(e);process.exitCode=1;});
