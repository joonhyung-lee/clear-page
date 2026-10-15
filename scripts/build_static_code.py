"""Render archive trees and source excerpts before any browser scripts run."""
import html
import json
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]

def read_assignment(path):
    return json.loads(path.read_text().split('=', 1)[1].strip().removesuffix(';'))

def size(value):
    for limit, unit in [(10**9,'GB'), (10**6,'MB'), (10**3,'KB')]:
        if value >= limit: return f'{value/limit:.1f} {unit}'
    return f'{value} B'

def tree(members):
    root = {'children': {}, 'bytes': 0, 'count': 0}
    for member in members:
        node = root
        for name in member['path'].split('/'):
            node['bytes'] += member['bytes']; node['count'] += 1
            node = node['children'].setdefault(name, {'children': {}, 'bytes': 0, 'count': 0})
        node.update(bytes=member['bytes'], type=member.get('type'))
    def branch(parent, depth=0):
        rows = []
        for name, entry in sorted(parent['children'].items(), key=lambda kv:(not bool(kv[1]['children']),kv[0].lower())):
            while len(entry['children']) == 1:
                child_name, child = next(iter(entry['children'].items()))
                if not child['children']: break
                name += '/' + child_name; entry = child
            folder = bool(entry['children'])
            label = html.escape(name + ('/' if folder else ''))
            meta = (f"{entry['count']} files · " if folder else 'link · ' if entry.get('type')=='symlink' else '') + size(entry['bytes'])
            tag = 'summary' if folder else 'div'
            row = f'<{tag} class="archive-row"><span class="archive-name">{label}</span><span class="archive-meta">{meta}</span></{tag}>'
            if folder: row = f'<details{" open" if depth==0 else ""}>{row}{branch(entry,depth+1)}</details>'
            rows.append('<li>'+row+'</li>')
        return '<ul>'+''.join(rows)+'</ul>'
    return branch(root)

def build():
    path = ROOT/'code/index.html'; soup = BeautifulSoup(path.read_text(),'html.parser')
    archives = read_assignment(ROOT/'assets/code-archives.js')
    catalog = read_assignment(ROOT/'code/catalog.js')
    for region in soup.select('[data-archive-tree]'):
        archive = archives[region['data-archive-tree']]
        region.clear(); region.append(BeautifulSoup(tree(archive['members']),'html.parser'))
        region['data-prerendered']='true'
    downloads = read_assignment(ROOT/'assets/code-download-locations.js')
    for label in soup.select('[data-archive]'):
        key = label['data-archive']; archive = archives[key]; link = label.find_parent('a')
        url = archive['url']+'?v='+archive['sha256'][:12] if key == 'source' else downloads.get(key)
        if url:
            label.string = 'ZIP · '+size(archive['bytes']) if key == 'source' else f"Browse · {archive['files']} models · {size(archive['bytes'])}"
            link['href'] = url; link.attrs.pop('aria-disabled', None); link.attrs.pop('tabindex', None)
            if key == 'checkpoints': link.attrs.pop('download', None)
        else:
            label.string = f"Download pending · {archive['files']} models"
            link.attrs.pop('href', None); link['aria-disabled'] = 'true'; link['tabindex'] = '-1'
    for index, panel in enumerate(soup.select('section.component')):
        if index: panel['hidden']=''
        else: panel.attrs.pop('hidden',None)
        panel.select_one('.component-index').string=f'{index+1:02d}'
        card=panel.select_one('.snippet')
        guide=next(n for n in catalog['nodes'] if n['stage']==panel['id'])
        file=next(f for f in catalog['files'] if f['path']==guide['file'])
        raw=(ROOT/'code'/file['url'].split('?')[0]).read_text()
        # Generated calls carry two JSON arguments; no source code is executed.
        args=json.loads('['+raw.split('.register(',1)[1].rsplit(')',1)[0]+']')
        data=args[1]; display=data.get('formatted',data)
        symbol=next(s for s in display['symbols'] if s['name']==guide['symbol'])
        start,end=symbol['start'],symbol['end']
        rows=''.join(f'<span class="code-line"><span class="line-number" aria-hidden="true">{n}</span><span class="line-content">{display["lines"][n-1]}</span></span>' for n in range(start,end+1))
        code=card.select_one('code');code.clear();code.append(BeautifulSoup(rows,'html.parser'))
        card['data-prerendered-node']=guide['id'];card.select_one('.code-status').clear()
        card.select_one('.snippet-heading>span').string=guide['symbol']
        card.select_one('.snippet-footer').string=guide['file'].removeprefix('runtime/')+f' · {end-start+1} lines'
        card.select_one('[data-copy-source]').attrs.pop('disabled',None)
    soup.select_one('.implementation-workspace').attrs.pop('data-workspace-view', None)
    for tabs in soup.select('.workspace-views'):
        tabs.decompose()
    for panel in soup.select('section.component'):
        for selector, label in (('.result', 'Visualization'), ('.snippet', 'Code')):
            region = panel.select_one(selector)
            heading = region.select_one(':scope > .workspace-column-label')
            if not heading:
                heading = soup.new_tag('h3', attrs={'class': 'workspace-column-label'})
                region.insert(0, heading)
            heading.string = label
    path.write_text(str(soup).rstrip()+'\n')

if __name__=='__main__': build()
