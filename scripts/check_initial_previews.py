"""Check sharp first-paint assets and focused/radial player controls."""
import base64,io,json,asyncio,argparse
from pathlib import Path
from bs4 import BeautifulSoup
from PIL import Image
from playwright.async_api import async_playwright
parser=argparse.ArgumentParser()
parser.add_argument('--base-url',default='http://localhost:8773')
BASE=parser.parse_args().base_url.rstrip('/')
root=Path(__file__).resolve().parents[1]
for name in ['index.html','code/index.html']:
 soup=BeautifulSoup((root/name).read_text(),'html.parser');count=0
 for tag in soup.select('[data-preview-src]'):
  src=tag.get('poster' if tag.name=='video' else 'src','')
  assert src.startswith('data:'),(name,tag['data-preview-src'])
  image=Image.open(io.BytesIO(base64.b64decode(src.split(',')[1])))
  original=Image.open((root/name).parent/tag['data-preview-src'].split('?')[0])
  assert image.width>=min(original.width,600),(name,tag['data-preview-src'],image.size,original.size)
  count+=1
 if name=='index.html':
  placeholder=soup.select_one('[data-policy-placeholder]')
  assert placeholder is not None
  assert Image.open(io.BytesIO(base64.b64decode(placeholder['src'].split(',')[1]))).width>=928
 print(name,'sharp embedded previews',count,flush=True)
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  for width in [1440,390]:
   page=await browser.new_page(viewport={'width':width,'height':1000},device_scale_factor=1)
   errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   await page.route('**/*page-previews*',lambda r:r.abort())
   await page.goto(BASE+'/',wait_until='domcontentloaded')
   await page.wait_for_function('window.CLEAR_APP_READY===true')
   await page.locator('#controller-pretraining').scroll_into_view_if_needed()
   await page.locator('[data-checkpoint-video]').wait_for(state='visible')
   movie=page.locator('[data-checkpoint-video]')
   await page.locator('[data-checkpoint-stage]').last.click()
   await page.wait_for_function('document.querySelector("[data-checkpoint-video]").currentTime>1')
   print('viewport',width,await movie.evaluate('(v)=>({src:v.currentSrc,width:v.videoWidth,height:v.videoHeight,box:v.getBoundingClientRect().width,time:v.currentTime})'),flush=True)
   assert await page.get_by_label('Terrain view',exact=True).input_value()=='stairs_up'
   await page.get_by_label('Terrain view',exact=True).select_option('matrix')
   await page.wait_for_function('document.querySelector("[data-checkpoint-video]").videoWidth===960')
   await page.get_by_label('Terrain view',exact=True).select_option('slope_up')
   await page.wait_for_function('document.querySelector("[data-checkpoint-video]").currentSrc.includes("-slope_up.mp4")')
   await page.get_by_label('Enlarge terrain view',exact=True).click()
   await page.locator('dialog video').wait_for(state='visible')
   await page.keyboard.press('Escape')
   await page.locator('#controller-pretraining').screenshot(path=f'/tmp/clear-radial-page-{width}.png')
   assert not errors,errors
   assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
   await page.close()
  await browser.close()
asyncio.run(main())
