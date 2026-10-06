// DOM harness for the bundled offline inspector. This is not a browser rendering test.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const html=fs.readFileSync('attention/index.html','utf8'),code=html.split('<script>')[1].split('</script>')[0];
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.options=[];this.value='';this.style={};this.listeners={};this.width=this.height=640;this.attributes={}}
 add(o){this.options.push(o);if(this.options.length===1)this.value=String(o.value)}
 replaceChildren(...items){this.children=items;if(this.tagName==='select'){this.options=items;this.value=String(items[0]?.value??'')}}
 append(...nodes){this.children.push(...nodes)}
 setAttribute(k,v){this.attributes[k]=v}
 addEventListener(k,f){this.listeners[k]=f}
 getBoundingClientRect(){return {left:0,top:0,width:640,height:640}}
 getContext(){return new Proxy({isPointInPath:()=>true},{get:(o,k)=>k in o?o[k]:(()=>{}),set:(o,k,v)=>(o[k]=v,true)})}
}
const nodes={};for(const id of html.matchAll(/id="([^"]+)"/g))nodes[id[1]]=new Element(['case','component','query','layer','head','flow'].includes(id[1])?'select':'div');
Object.assign(nodes.time,{value:'0'});nodes.component.value='encoder';nodes.layer.value=nodes.head.value='-1';nodes.flow.value='0';
for(const id of ['layer','head'])nodes[id].options.push({value:-1});
const context={document:{getElementById:id=>nodes[id],createElement:tag=>new Element(tag)},Option:class {constructor(t,v){this.text=t;this.value=String(v)}},Path2D:class {moveTo(){}lineTo(){}closePath(){}},innerWidth:1440,innerHeight:1000,console};
vm.createContext(context);vm.runInContext(code,context);
const data=JSON.parse(fs.readFileSync('attention/attention.json'));
for(let ci=0;ci<data.cases.length;ci++){
 nodes.case.value=String(ci);nodes.case.listeners.input();
 for(let t=0;t<data.cases[ci].frames.length;t++)for(const component of ['encoder','flow']){
  nodes.time.value=String(t);nodes.component.value=component;nodes.query.value='all';nodes.layer.value=nodes.head.value='-1';nodes.time.listeners.input();
  const frame=data.cases[ci].frames[t],w=vm.runInContext('average(frame())',context);
  if(component==='flow'&&!frame.flow.length){assert.equal(w,null);assert.equal(nodes.empty.hidden,false);continue}
  assert(Math.abs(w.reduce((a,b)=>a+b,0)-1)<1e-6);
  assert(nodes.weights.children.length===w.length);assert(nodes.film.children.length===6);
  const raw=component==='encoder'?frame.encoder:frame.flow[0].weights;
  const q=component==='encoder'?0:frame.selected.findIndex(Boolean);
  nodes.query.value=String(q);nodes.layer.value='2';nodes.head.value='1';nodes.query.listeners.input();
  const single=vm.runInContext('average(frame())',context);
  assert.deepEqual(Array.from(single),raw[2][1][q]);
 }
}
// Filmstrip and hover exercise the actual bundled UI, without network or a browser socket.
nodes.component.value='encoder';nodes.query.value='all';nodes.component.listeners.input();nodes.film.children[1].onclick();assert.equal(nodes.time.value,1);
nodes.attention.listeners.pointermove({currentTarget:nodes.attention,clientX:300,clientY:300});assert.equal(nodes.tip.style.display,'block');assert(nodes.tip.textContent.includes('%'));nodes.attention.listeners.pointerleave();assert.equal(nodes.tip.style.display,'none');
console.log('PASS bundled inspector: 18 observations, both components, empty flow, per-layer/head/query values, six-frame navigation and raw-value hover');
