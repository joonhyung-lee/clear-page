"""Ensure displayed TeX occurs in the supplied manuscript's active source."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from bs4 import BeautifulSoup
p=argparse.ArgumentParser(description=__doc__);p.add_argument('manuscript',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parents[1]
source='\n'.join(line.split('%',1)[0] for line in a.manuscript.read_text().splitlines())
def normalize(tex):return re.sub(r'\s+','',tex.replace('&','').replace('{}','').replace('\\\\',''))
source=normalize(source)
soup=BeautifulSoup((root/'index.html').read_text(),'html.parser');formulas=[e['data-tex'] for e in soup.select('[data-tex]')]
assert formulas
for tex in formulas:assert normalize(tex) in source,'Notation outside the manuscript: '+tex
assert not soup.select('.grounding-input-definition')
for node in soup.select('.equation'):assert 'paper-equation-row' in node.parent.get('class',[])
subprocess.run(['node','-e',"const katex=require('./assets/katex/katex.min.js');for(const tex of JSON.parse(process.argv[1]))katex.renderToString(tex,{throwOnError:true,strict:'error'});",json.dumps(formulas)],cwd=root,check=True)
print('PASS',len(formulas),'displayed TeX expressions match the active manuscript and render in KaTeX')
