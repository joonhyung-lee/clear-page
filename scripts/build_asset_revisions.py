"""Version public assets by content so refreshed pages load the current media."""
from pathlib import Path
from hashlib import sha256
from urllib.parse import urlsplit
import json
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1]
paths=[p for p in (root/'assets').rglob('*') if p.is_file() and p.name!='asset-revisions.js' and p.suffix in ['.js','.css','.png','.mp4','.svg']]
revisions={p.relative_to(root).as_posix():sha256(p.read_bytes()).hexdigest()[:12] for p in paths}
manifest=root/'assets/asset-revisions.js';manifest.write_text('window.CLEAR_ASSET_REVISIONS = '+json.dumps(revisions,separators=(',',':'))+';\n')
revisions['assets/asset-revisions.js']=sha256(manifest.read_bytes()).hexdigest()[:12]
soup=BeautifulSoup((root/'index.html').read_text(),'html.parser')
seen=set()
for tag in list(soup.find_all('script',src=True)):
 base=urlsplit(tag['src']).path
 if base in seen:tag.decompose()
 else:seen.add(base)
if 'assets/asset-revisions.js' not in seen:
 script=soup.new_tag('script',attrs={'src':'assets/asset-revisions.js','defer':''})
 first=soup.head.find('script')
 if first:first.insert_before(script)
 else:soup.head.append(script)
for tag in soup.find_all(True):
 for key in ['src','href','poster']:
  value=tag.get(key,'');base=urlsplit(value).path
  if base in revisions:tag[key]=base+'?v='+revisions[base]
(root/'index.html').write_text(str(soup).rstrip()+'\n')
print('Versioned',len(revisions),'public assets')
