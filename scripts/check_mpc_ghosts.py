"""Verify all candidate endpoints in both coordinate views and compact controls."""
import asyncio,json,math
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
records=json.loads((ROOT/'assets/mpc-process-data.js').read_text().split('=',1)[1].rstrip(';\n'))
PROBE='''(()=>{const state=new WeakMap();window.ghostDraws=[];for(const name of ['beginPath','moveTo','lineTo','stroke']){const original=CanvasRenderingContext2D.prototype[name];CanvasRenderingContext2D.prototype[name]=function(...args){if(this.canvas.width===560&&!this.canvas.isConnected){let s=state.get(this);if(!s){s={paths:[]};state.set(this,s);ghostDraws.push(s.paths);}if(name==='beginPath')s.points=[];if(name==='moveTo'||name==='lineTo')s.points.push(args);if(name==='stroke'&&s.points.length)s.paths.push([s.points.length,...s.points[0],...s.points.at(-1)]);}return original.apply(this,args);};}})()'''
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch();page=await b.new_page(viewport={'width':1440,'height':1050},reduced_motion='reduce');errors=[];page.on('pageerror',lambda e:errors.append(str(e)));await page.add_init_script(PROBE)
  await page.goto('http://localhost:8765',wait_until='domcontentloaded');root=page.locator('#mpc-process');await root.scroll_into_view_if_needed();await root.locator('.mpc-process-content').wait_for()
  assert await root.locator('button').all_text_contents()==['2D View','3D View','Play'];assert await root.locator('select').count()==0;assert await root.locator('canvas').count()==2
  bounds=json.loads(await root.locator('canvas').first.get_attribute('data-coordinate-bounds'))
  corners=[(.866*x+.5*y,.28*x-.485*y-.84*z) for x in bounds[0] for y in bounds[1] for z in bounds[2]];screen=[(min(p[a] for p in corners),max(p[a] for p in corners)) for a in range(2)];scale=min(440/(screen[0][1]-screen[0][0]),390/(screen[1][1]-screen[1][0]))
  for mode in ['3d','2d']:
   await root.locator('[data-mpc-view="'+mode+'"]').click();draws=await page.evaluate('ghostDraws');layers=draws[:2] if mode=='3d' else draws[2:]
   assert len(layers)==2
   for layer,name in zip(layers,['optimized','baseline']):
    r=records[name];dx,dy=[r['reference'][-1][i]-r['reference'][0][i] for i in range(2)];norm=math.hypot(dx,dy);dx/=norm;dy/=norm;origin=[(r['observed'][0][1]+r['observed'][0][4])/2,(r['observed'][0][2]+r['observed'][0][5])/2];expected=[]
    for u in r['updates']:
     for path in u['paths'][:24]:
      for hand in range(2):
       xyz=[]
       for j in [0,len(path)-1]:
        point=path[j][hand];x,y=point[0]-origin[0],point[1]-origin[1];xyz.append([x*dx+y*dy,-x*dy+y*dx,point[2]])
       if mode=='3d':
        points=[]
        for x,y,z in xyz:points.extend([280+(.866*x+.5*y-sum(screen[0])/2)*scale,205+(.28*x-.485*y-.84*z-sum(screen[1])/2)*scale])
        expected.append([len(path),*points])
       else:
        for a,(lo,hi) in enumerate(bounds):
         points=[]
         for point,j in zip(xyz,[0,len(path)-1]):points.extend([60+(u['time']-r['updates'][0]['time']+r['futureTimes'][j])/45*470,177+a*151-(point[a]-lo)/(hi-lo)*111])
         expected.append([len(path),*points])
    assert len(expected)==len(layer)
    for wanted,actual in zip(expected,layer):assert all(math.isclose(x,y,abs_tol=1e-7) for x,y in zip(wanted,actual)),(name,mode,wanted,actual)
  for t,complete in [(0,['false','false']),(13.9,['false','false']),(14,['true','false']),(20,['true','false']),(40,['true','true'])]:
   await root.locator('input').evaluate('(e,t)=>{e.value=t/40;e.dispatchEvent(new Event("input"))}',t);assert await root.locator('[data-process]').evaluate_all('es=>es.map(e=>e.dataset.complete)')==complete
   stamp=await root.get_attribute('data-elapsed')
   for mode in ['3d','2d']:
    await root.locator('[data-mpc-view="'+mode+'"]').click();assert await root.get_attribute('data-elapsed')==stamp
  assert await page.evaluate('ghostDraws.length')==4,'Ghost layers must be reused'
  for width in [768,390]:
   await page.set_viewport_size({'width':width,'height':1000});assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  assert not errors,errors;await b.close();print('PASS all 18,240 spatial and 54,720 coordinate paths, paired palms, fixed scales, view continuity, completion and compact responsive controls')
asyncio.run(main())
