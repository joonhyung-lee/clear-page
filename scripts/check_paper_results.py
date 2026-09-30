"""Match every published numerical table row to its manuscript column."""
from pathlib import Path
import re
import json
import hashlib
from urllib.parse import urlsplit
import pymupdf
from PIL import Image
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
paper=pymupdf.open(ROOT/'assets/clear-paper.pdf')
soup=BeautifulSoup((ROOT/'index.html').read_text(),'html.parser')
assert len(paper)==8
assert not any(paper.metadata.get(key) for key in ['author','creator','producer','creationDate','modDate'])
assert paper.embfile_count()==0 and not paper.get_xml_metadata()
assert 'Anonymous Authors' in paper[0].get_text()
preview=json.loads((ROOT/'assets/paper/manifest.json').read_text())
assert preview['pdfSHA256']==hashlib.sha256((ROOT/'assets/clear-paper.pdf').read_bytes()).hexdigest()
assert len(preview['pages'])==len(paper)
for page,entry in zip(paper,preview['pages']):
    rendered=page.get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False)
    image=Image.open(ROOT/'assets'/urlsplit(entry['image']).path).convert('RGB')
    assert image.size==(rendered.width,rendered.height)
    assert image.tobytes()==rendered.samples, f'Preview differs from PDF page {page.number+1}'
    assert entry['text']==page.get_text()
print('PASS eight preview pages match PDF pixels and accessible text exactly')
for key,page,column,count in [('grid',5,0,6),('manipulation',5,1,6),('maze',6,0,9),('horizon',6,1,2)]:
    text=paper[page].get_text(clip=pymupdf.Rect(0 if column==0 else 306,0,306 if column==0 else 612,792))
    compact=re.sub(r'\s+','',text)
    rows=soup.select(f'#experiment-{key} .paper-results tbody tr')
    assert len(rows)==count
    for row in rows:
        numbers=''.join(re.sub(r'\s+','',cell.get_text()) for cell in row.select('td'))
        assert numbers in compact,(key,row.get_text(' ',strip=True))
    assert 'Paper aggregate' in soup.select_one(f'#experiment-{key} .paper-results').get_text()
    print('PASS',key,len(rows),'numerical rows match the manuscript')
print('PASS anonymous manuscript metadata, 23 table rows and aggregate scope labels')
