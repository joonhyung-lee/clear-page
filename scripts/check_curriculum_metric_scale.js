/* Preserve raw values on both healthy histories and recorded numerical excursions. */
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const path=require('path'),root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'assets/spot-curriculum.js'),'utf8');
const scaleSource=source.slice(source.indexOf('  function metricScale('),source.indexOf('  const stageColors'));
const context={window:{}};vm.createContext(context);
vm.runInContext(scaleSource,context);
vm.runInContext(fs.readFileSync(path.join(root,'assets/g1-curriculum-data.js'),'utf8'),context);
const rows=context.window.CLEAR_BODY_CURRICULA.g1.curves;
for(const key of ['value','policy','entropy','return','tracking']){
  const values=rows.map(r=>r[key]).filter(Number.isFinite),scale=context.metricScale(values);
  const sorted=[...values,0].sort((a,b)=>a-b);
  let previous=-Infinity;
  for(const v of sorted){
    const mapped=scale.transform(v);
    assert(Number.isFinite(mapped)&&mapped>=previous);
    assert(mapped>=scale.minimum&&mapped<=scale.maximum,'Do not clip measured excursions');
    assert(Math.abs(scale.inverse(mapped)-v)<=Math.max(1,Math.abs(v))*1e-12,'Raw hover values must remain recoverable');
    previous=mapped;
  }
  console.log('PASS',key,scale.logarithmic?'signed log axis':'linear axis','with all recorded values');
}
assert(rows.length>0);
assert(rows.filter(r=>r.stage==='locomotion').every(r=>!Object.hasOwn(r,'terrain')),'Do not invent a flat-ground terrain level');
// Historical failures must stay visible even after the public page moves to a new run.
for(const values of [[.77513,.495,29.97,8.59,1.4887585e17,228730000],[2,5,8,-149860000]]){
  const scale=context.metricScale(values);assert(scale.logarithmic);
  for(const value of values){
    const mapped=scale.transform(value);
    assert(mapped>=scale.minimum&&mapped<=scale.maximum);
    assert(Math.abs(scale.inverse(mapped)-value)<=Math.max(1,Math.abs(value))*1e-12);
  }
}
console.log('PASS historical spikes remain in range with recoverable raw values');
for(const values of [[],[0],[1,1],[-1,-1]]){
  const s=context.metricScale(values);assert(Number.isFinite(s.minimum)&&s.maximum>s.minimum);
}
