/* Exercise the actual diagnostic player with its published recorded states. */
const fs=require('fs'),vm=require('vm'),assert=require('assert');
async function check(reduced){
 const observers=[],frames=new Map();let id=0;
 const make=flow=>{
  const controls={input:{value:0},'[data-failure-play]':{},'[data-failure-replay]':{},'.failure-controls output':{},'.failure-stage':{}};
  const commands=[];const ctx=new Proxy({},{get:(o,k)=>o[k]||((...args)=>{if(k==='fillRect'&&args[0]===0&&args[1]===0)commands.length=0;commands.push({op:k,args,style:{...o}});})});
  const article={querySelector:s=>controls[s]};
  const canvas={dataset:{},clientWidth:480,clientHeight:360,hasAttribute:()=>flow,closest:()=>article,getContext:()=>ctx};
  return {canvas,controls,commands};
 };
 const flow=make(true),planning=make(false);
 const sandbox={console,Math,JSON,devicePixelRatio:1,matchMedia:()=>({matches:reduced}),document:{hidden:false,querySelectorAll:()=>[flow.canvas,planning.canvas],addEventListener:()=>{}},ResizeObserver:class{observe(){}},IntersectionObserver:class{constructor(fn){this.fn=fn;observers.push(this);}observe(){}},requestAnimationFrame:fn=>{frames.set(++id,fn);return id;},cancelAnimationFrame:i=>frames.delete(i)};
 sandbox.window=sandbox;const context=vm.createContext(sandbox);
 sandbox.loadScript=async path=>vm.runInContext(fs.readFileSync(path,'utf8'),context);
 vm.runInContext(fs.readFileSync('assets/failure-map.js','utf8'),context);
 for(const observer of observers)observer.fn([{isIntersecting:true}]);
 await new Promise(setImmediate);
 const capture=name=>{if(process.env.CLEAR_CANVAS_REVIEW_DIR&&!reduced){fs.mkdirSync(process.env.CLEAR_CANVAS_REVIEW_DIR,{recursive:true});fs.writeFileSync(process.env.CLEAR_CANVAS_REVIEW_DIR+'/'+name+'.json',JSON.stringify({flow:flow.commands,planning:planning.commands}));}};
 const tick=t=>{const queue=[...frames.values()];frames.clear();queue.forEach(fn=>fn(t));};
 capture('initial');assert.equal(flow.canvas.dataset.flowTime,'0.000');
 assert.equal(planning.canvas.dataset.source,'archived-planning-decisions');
 if(reduced){assert.equal(frames.size,0);flow.controls['[data-failure-play]'].onclick();planning.controls['[data-failure-play]'].onclick();}
 tick(100);tick(4100);
 capture('midpoint');assert.equal(flow.canvas.dataset.flowTime,'0.500');
 assert.match(planning.controls['.failure-stage'].textContent,/Candidate 3/);
 const halfway=flow.canvas.dataset.overlapSegments;
 tick(8100);capture('final');assert.equal(flow.canvas.dataset.flowTime,'1.000');
 assert.match(flow.controls['.failure-stage'].textContent,/Clearance failed/);
 tick(16100);assert.match(planning.controls['.failure-stage'].textContent,/No valid plan/);
 assert(JSON.parse(flow.canvas.dataset.overlapSegments).length>0);
 assert.notEqual(halfway,flow.canvas.dataset.overlapSegments);
 assert.equal(frames.size,0,'Animation stops at the failed endpoint');
 const f=context.CLEAR_TEASER_FLOW.referenceFlow[0],g=context.CLEAR_FAILURE_GEOMETRY;
 for(let i=0;i<f.times.length;i++)assert.deepEqual(g.sample(f,f.times[i]),f.states[i],'All integration checkpoints must match the saved poses');
 assert(g.overlap([0,0,Math.PI/4],[2,2],[-.1,-.1,.1,.1]));
 assert(!g.overlap([5,5,0],[1,1],[-1,-1,1,1]));
 flow.controls.input.value=.25;flow.controls.input.oninput();assert.equal(flow.canvas.dataset.flowTime,'0.250');
 flow.controls['[data-failure-replay]'].onclick();assert.equal(flow.canvas.dataset.flowTime,'0.000');
 observers[0].fn([{isIntersecting:false}]);tick(16000);assert.equal(flow.canvas.dataset.flowTime,'0.000');
 observers[0].fn([{isIntersecting:true}]);tick(17000);tick(18000);assert.equal(flow.canvas.dataset.flowTime,'0.125','Offscreen duration must not advance the animation');
 console.log('PASS recorded flow interpolation, swept clearance, timeline, end state, replay, offscreen pause; reduced motion='+reduced);
}
(async()=>{await check(false);await check(true);})().catch(e=>{console.error(e);process.exitCode=1;});
