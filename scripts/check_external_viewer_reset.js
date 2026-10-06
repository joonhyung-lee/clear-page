/* The actual viewer reset must hand back to the row clock after DOM cleanup. */
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('assets/site.js','utf8');
const functionSource=source.slice(source.indexOf('function wireViewer('),source.indexOf("document.querySelectorAll('.viewer:not(.focus-viewer)')"));
for(const external of [false,true]){
 const listeners={},events=[];let frame={remove(){frame=null;}};
 const launch={textContent:'Inspect in 3D',addEventListener(){},focus(){}},video={hidden:true},ego={readyState:4,currentTime:9};
 const viewer={dataset:external?{executionClock:'optimized'}:{},querySelector:s=>s==='.launch'?launch:s==='video, img.preview-image'?video:s==='.ego-inset video'?ego:frame,
  querySelectorAll:()=>frame?[frame]:[],addEventListener:(n,fn)=>listeners[n]=fn,removeAttribute(){},
  dispatchEvent:e=>{events.push({frame,ego:ego.currentTime,hidden:video.hidden});if(external){video.currentTime=9;video.paused=true;ego.currentTime=9;}}};
 const context=vm.createContext({clearTimeout(){},CustomEvent:class{constructor(type,props){Object.assign(this,props);}},IntersectionObserver:class{observe(){}},document:{addEventListener(){}},window:{addEventListener(){}}});
 vm.runInContext(functionSource,context);
 const reset=context.wireViewer(viewer);reset();
 assert.equal(frame,null);assert.equal(events.length,1);assert.equal(events[0].frame,null,'Clock must be notified after removing native frame');assert.equal(events[0].hidden,false);
 assert.equal(ego.currentTime,external?9:0,'External clock owns the Ego playhead');
 if(external){assert.equal(video.currentTime,9);assert.equal(video.paused,true);}
 // Run the production Back-to-video callback with the same closure dependencies.
 const back=source.match(/back\.addEventListener\('click', \(\) => \{ (reset\(\);[^\n]+) \}\);/)[1];
 let plays=0;video.play=()=>{plays++;return Promise.resolve();};
 vm.runInNewContext(back,{reset,viewer,video,launch,reduced:{matches:false}});
 assert.equal(plays,external?0:1,'Back must preserve a paused external clock');
 console.log('PASS viewer reset and Back to video; external clock='+external);
}
