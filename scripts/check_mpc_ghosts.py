"""Check every candidate's actual canvas path, fixed XYZ axes, and record completion."""
import asyncio,json,math,statistics
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
records=json.loads((ROOT/'assets/mpc-process-data.js').read_text().split('=',1)[1].rstrip(';\n'))
PROBE='''(()=>{const state=new WeakMap();window.ghostDraws=[];for(const name of ['beginPath','moveTo','lineTo','stroke']){const original=CanvasRenderingContext2D.prototype[name];CanvasRenderingContext2D.prototype[name]=function(...args){if(this.canvas.width===560&&this.canvas.height===700&&!this.canvas.isConnected){let s=state.get(this);if(!s){s={paths:[]};state.set(this,s);ghostDraws.push(s.paths);}if(name==='beginPath')s.points=[];if(name==='moveTo'||name==='lineTo')s.points.push(args);if(name==='stroke'&&s.points.length)s.paths.push([s.points.length,...s.points[0],...s.points.at(-1)]);}return original.apply(this,args);};}})()'''
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':1440,'height':1050},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)));await page.add_init_script(PROBE)
  await page.goto('http://localhost:8765',wait_until='domcontentloaded');root=page.locator('#mpc-process');await root.scroll_into_view_if_needed();await root.locator('.mpc-process-content').wait_for()
  draws=await page.evaluate('ghostDraws');assert len(draws)==4
  limits=json.loads(await root.locator('canvas').first.get_attribute('data-coordinate-bounds'));layer=0
  for name in ['optimized','baseline']:
   r=records[name];dx,dy=[r['reference'][-1][i]-r['reference'][0][i] for i in range(2)];norm=math.hypot(dx,dy);dx/=norm;dy/=norm
   for hand in range(2):
    initial=r['observed'][0][1+hand*3:4+hand*3];expected=[]
    for u in r['updates']:
     for path in u['paths'][:r['population']]:
      for a in range(3):
       points=[]
       for j in [0,len(path)-1]:
        x,y,z=[path[j][hand][i]-initial[i] for i in range(3)];value=[x*dx+y*dy,-x*dy+y*dx,z][a];lo,hi=limits[a]
        points.extend([62+(u['time']-r['updates'][0]['time']+r['futureTimes'][j])/45*470,378+a*134-(value-lo)/(hi-lo)*96])
       expected.append([len(path),*points])
    assert len(expected)==len(draws[layer])
    for wanted,actual in zip(expected,draws[layer]):assert all(math.isclose(x,y,abs_tol=1e-7) for x,y in zip(wanted,actual)),(name,hand,wanted,actual)
    layer+=1
  async def seek(t):await root.locator('input').evaluate('(e,t)=>{e.value=t/40;e.dispatchEvent(new Event("input"))}',t)
  fixed=await root.locator('canvas').evaluate_all('es=>es.map(e=>[e.dataset.coordinateBounds,e.dataset.ghostTrajectories,e.dataset.axisEnd])')
  for t,complete in [(0,['false','false']),(13.9,['false','false']),(14,['true','false']),(20,['true','false']),(40,['true','true'])]:
   await seek(t);assert await root.locator('[data-process]').evaluate_all('es=>es.map(e=>e.dataset.complete)')==complete
   assert await root.locator('canvas').evaluate_all('es=>es.map(e=>[e.dataset.coordinateBounds,e.dataset.ghostTrajectories,e.dataset.axisEnd])')==fixed
  assert await page.evaluate('ghostDraws.length')==4,'Full populations must be cached, not redrawn every frame'
  await seek(8);snapshot=await root.locator('[data-process]').evaluate_all('es=>es.map(e=>e.dataset.update)')
  for a in range(3):
   await root.locator('button[data-detail-axis="'+str(a)+'"]').click()
   for name,r in records.items():
    panel=root.locator('[data-process='+name+']');index=int(await panel.get_attribute('data-update'));u=next(u for u in r['updates'] if u['sourceIndex']==index)
    dx,dy=[r['reference'][-1][i]-r['reference'][0][i] for i in range(2)];norm=math.hypot(dx,dy);dx/=norm;dy/=norm
    for hand,canvas in enumerate(await panel.locator('canvas').all()):
     maximum=0
     for path in u['paths'][:24]:
      for j,point in enumerate(path):
       x,y,z=[point[hand][i]-u['paths'][u['applied']][j][hand][i] for i in range(3)];maximum=max(maximum,1000*abs([x*dx+y*dy,-x*dy+y*dx,z][a]))
     assert maximum<=float(await canvas.get_attribute('data-residual-limit'))+1e-7
   assert await root.locator('[data-process]').evaluate_all('es=>es.map(e=>e.dataset.update)')==snapshot
  await root.locator('#mpc-candidate-inspect').select_option('23');assert await root.locator('canvas').evaluate_all('es=>es.every(e=>e.dataset.inspectedCandidate==="23")')
  await root.locator('[data-candidates=retained]').click();assert await root.locator('#mpc-candidate-inspect').input_value()=='-1'
  expected=[sum(len(u['elites']) for u in records[n]['updates']) for n in ['optimized','baseline']]
  assert await root.locator('canvas').evaluate_all('es=>es.map(e=>Number(e.dataset.ghostTrajectories))')==[expected[0]]*2+[expected[1]]*2
  await root.locator('[data-candidates=all]').click();assert await page.evaluate('ghostDraws.length')==8
  await root.locator('button[data-detail-axis="0"]').click();await seek(14);await root.screenshot(path='/tmp/mpc-xyz-final.png')
  timings=await root.locator('input').evaluate('e=>Array.from({length:20},(_,i)=>{const t=performance.now();e.value=i/20;e.dispatchEvent(new Event("input"));return performance.now()-t})')
  for width in [768,390]:
   await page.set_viewport_size({'width':width,'height':1000});assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');await root.screenshot(path=f'/tmp/mpc-xyz-{width}.png')
  assert not errors,errors;await b.close();print(f'PASS all 54,720 raw candidate coordinate paths, cached replay, XYZ bounds, candidate inspection, completion, mobile. Median render {statistics.median(timings):.1f} ms')
asyncio.run(main())
