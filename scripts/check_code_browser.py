"""Check source fidelity, escaped rendering, navigation and preview boundaries.

--browser additionally checks actual interactions and responsive rendering.
The default checks do not require sockets or a running preview server.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import io
import json
import stat
import zipfile
import black
from pathlib import Path
from types import SimpleNamespace

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def catalog():
    text = (ROOT / 'code/catalog.js').read_text()
    return json.loads(text.removeprefix('window.CLEAR_CODE_CATALOG=').removesuffix(';\n'))


def static_checks():
    data = catalog()
    registry = {f['path']: f for f in data['files']}
    for file in data['files']:
        script = (ROOT / 'code' / file['url']).read_text()
        args = json.loads('[' + script.removeprefix('window.CLEAR_CODE.register(').removesuffix(');\n') + ']')
        path, value = args
        assert path == file['path']
        assert hashlib.sha256(value['text'].encode()).hexdigest() == file['sha256'], path
        decoded = [BeautifulSoup('<pre>'+line+'</pre>', 'html.parser').get_text() for line in value['lines']]
        expected = value['text'].split('\n')
        if value['text'].endswith('\n'): expected.pop()
        assert decoded == (expected or ['']), path
        assert len(decoded) == file['lines']
        for line in value['lines']:
            assert all(t.name == 'span' for t in BeautifulSoup(line, 'html.parser').find_all()), path
        formatted = value['formatted']
        black.assert_equivalent(value['text'], formatted['text'])
        assert black.format_str(formatted['text'], mode=black.Mode(line_length=88)) == formatted['text']
        display = [BeautifulSoup('<pre>'+line+'</pre>', 'html.parser').get_text() for line in formatted['lines']]
        assert '\n'.join(display)+'\n' == formatted['text'], path
        assert len(display) == file['formattedLines']
        assert formatted['symbols'] == file['formattedSymbols']
        assert all(tag.name=='span' for line in formatted['lines'] for tag in BeautifulSoup(line,'html.parser').find_all())
    for guide in data['guides']:
        entry = registry[guide['file']]
        symbol = next(s for s in entry['symbols'] if s['name'] == guide['symbol'])
        assert symbol['start'] <= guide['start'] <= guide['end'] <= symbol['end']
        assert all(p in registry for p in guide['related'])
    source = module('build_code_browser', ROOT / 'scripts/build_code_browser.py')
    fixture = 'value = "<img src=x onerror=alert(1)>"\ntext = """first\n<script>bad()</script>\nlast"""\n'
    lines = source.highlighted_lines(fixture, True)
    assert '\n'.join(BeautifulSoup('<pre>'+x+'</pre>', 'html.parser').get_text() for x in lines) + '\n' == fixture
    assert not BeautifulSoup(''.join(lines), 'html.parser').find(['script', 'img'])
    assert '<' not in source.js({'code': fixture})
    main = BeautifulSoup((ROOT / 'index.html').read_text(), 'html.parser')
    link = main.select_one('#research-nav > a.research-code')
    assert link['href'] == 'code/index.html' and link.get('target') is None
    assert link.find('svg') and link.find('span').get_text() == 'Code'
    page = BeautifulSoup((ROOT / 'code/index.html').read_text(), 'html.parser')
    assert page.select_one('a[aria-current="page"]').get_text(strip=True) == 'Code'
    assert len(page.select('a[download]')) == 2
    assert len(page.select('.component')) == 5
    assert not page.select('.package-note') and 'Package scope' not in page.get_text()
    stages = page.select('[data-flow-node]')
    assert [n['data-flow-node'] for n in stages] == [n['id'] for n in data['nodes']]
    by_id = {n['id']: n for n in data['nodes']}
    assert len(by_id) == len(data['nodes']) == 5
    for node, spec in zip(stages, data['nodes']):
        assert node['role'] == 'button' and node['tabindex'] == '0'
        assert page.find(id=node['aria-controls'])
        symbol = next(s for s in registry[spec['file']]['symbols'] if s['name'] == spec['symbol'])
        assert (spec['start'], spec['end']) == (symbol['start'], symbol['end'])
        seen = {spec['id']}; parent = spec['parent']
        while parent:
            assert parent in by_id and parent not in seen
            seen.add(parent); parent = by_id[parent]['parent']
    assert not page.select('.tree-edge, .flow-foot, .flow-caption')
    assert 'Module hierarchy' not in page.get_text()
    assert page.select_one('#code-system').name == 'nav'
    assert len(page.select('.pipeline-stages>li>button')) == 5
    assert [option['value'] for option in page.select('#pipeline-select option')] == list(by_id)
    assert len(page.select('.implementation-workspace > section.component')) == 5
    assert not page.select('.example-heading a')
    assert 'In paper' not in page.get_text()
    for node in data['nodes']:
        assert page.select_one('[data-source-path='+node['stage']+']').get_text() == '('+node['file']+')'
    assert len(page.select('[data-copy-source]')) == 5
    assert [b['data-workspace-view-button'] for b in page.select('[data-workspace-view-button]')] == ['example','code']
    assert not page.select('#flow-motion, #flow-prev, #flow-next, #flow-position')
    for i,node in enumerate(stages):
        assert node.name == 'button' and node['type'] == 'button'
        assert node.select_one('.pipeline-step>span').get_text() == f'{i+1:02d}'
        assert node.select_one('.pipeline-output').get_text() == data['nodes'][i]['example']
    assert len({n['stage'] for n in data['nodes']}) == 5
    assert [n['data-method-illustration'] for n in page.select('[data-method-illustration]')] == ['ordering','generation']
    for stage, original in [('ordering','method-order'),('generation','method-flow')]:
        assert str(page.select_one('#'+stage+' .result svg')) == str(main.select_one('#'+original+' .sequence-explanation svg'))
    assert any('assets/method-illustration.js' in n['src'] for n in page.select('script[src]'))
    assert len(page.select('[data-grounding-panel]')) == 3
    assert len(page.select('[data-grounding-panel=embodiment] video')) == 4
    assert len(page.select('[data-grounding-panel=scene] video')) == 4
    assert page.select_one('[data-grounding-panel=objects] source')['src'].split('?')[0] == '../assets/media/objects.mp4'
    for kind in ['paper','video']:
        assert main.select_one('[data-resource='+kind+'] span').get_text().lower() == kind
    assert 'route to the goal' in page.select_one('#validation figcaption').get_text()
    assert not page.select('.sidebar, #file-tree, #guide-nav')
    for link in page.select('a[download]'):
        assert (ROOT / 'code' / (link.get('href') or link['data-local-download'])).is_file()
    archives = json.loads((ROOT / 'assets/code-archives.js').read_text().removeprefix('window.CLEAR_CODE_ARCHIVES=').removesuffix(';\n'))
    assert {node['data-archive-tree'] for node in page.select('[data-archive-tree]')} == set(archives)
    for archive in archives.values():
        path = ROOT / 'code' / archive['url']
        assert path.stat().st_size == archive['bytes']
        with zipfile.ZipFile(path) as package:
            expected = [dict(path=i.filename, bytes=i.file_size,
                             type='symlink' if stat.S_ISLNK(i.external_attr >> 16) else 'file')
                        for i in package.infolist() if not i.is_dir()]
        assert archive['members'] == expected
        assert len(expected) == archive['files']
        assert len({entry['path'] for entry in expected}) == archive['files']
        assert all(entry['path'].startswith('clear/') and '..' not in entry['path'].split('/') for entry in expected)
    models = archives['checkpoints']['members']
    assert len(models) == 153 and all(m['path'].endswith('.pt') for m in models)
    assert {m['path'].split('/')[2] for m in models} == {'grid', 'maze', 'locomotion'}
    assert all(m['path'].startswith('clear/checkpoints/') for m in models)
    assert all('/leap2026/' not in m['path'] and '/anonymous/' not in m['path'] for m in models)
    with zipfile.ZipFile(ROOT / 'code' / archives['source']['url']) as package:
        mapping = json.loads(package.read('clear/docs/checkpoint_paths.json'))['models']
        assert {'clear/'+v['path'] for v in mapping.values()} == {m['path'] for m in models}
        assert 'clear/tools/link_checkpoints.py' in package.namelist()
    assert '../checkpoints/maze/reference/seed0/clear.pt' in page.select_one('#reproduce-command').get_text()
    for viewer in page.select('.viewer'):
        assert (ROOT / 'assets/recordings' / (viewer['data-scene']+'.hex.js')).is_file()
    for media in page.select('video source, img'):
        assert (ROOT / 'code' / media['src'].split('?')[0]).is_file()
    for el in page.select('[src], link[href]'):
        url = el.get('src') or el.get('href')
        assert not url.startswith(('http:', 'https:', '//')), url
        assert (ROOT / 'code' / url.split('?')[0]).is_file(), url
    assert not page.select('[data-native-example]')
    assert page.select_one('[data-shared-validation]')
    assert not page.select('.component-features, .selection-logic')
    for body,selector in [('g1','#mpc-process'),('spot_arm','#spot-process')]:
        reused=page.select_one('[data-execution-panel='+body+'] .viewer')
        original=main.select_one(selector+' [data-controller-pair=ours] .viewer')
        assert reused['data-scene']==original['data-scene']
        for key in ['.preview-video source','.ego-inset video']:
            assert reused.select_one(key)['src'].split('?')[0]=='../'+original.select_one(key)['src'].split('?')[0]
        assert not reused.has_attr('data-execution-clock')
    assert not any('code-native-data' in n['src'] or 'code-visuals.js' in n['src'] for n in page.select('script[src]'))
    serve = module('preview_server', ROOT / 'scripts/serve.py')
    class MemoryConnection:
        def __init__(self, path, headers=''):
            self.input = io.BytesIO(f'GET {path} HTTP/1.0\r\n{headers}\r\n'.encode())
            self.output = bytearray()
        def makefile(self, *args, **kwargs): return self.input
        def sendall(self, data): self.output.extend(data)
    class Handler(serve.Handler):
        def log_message(self, *args): pass
    def request(path, headers=''):
        connection = MemoryConnection(path, headers)
        Handler(connection, ('localhost', 0), SimpleNamespace(server_name='localhost', server_port=8765))
        return bytes(connection.output)
    for url in ['/code/index.html', '/code/catalog.js', '/code/code.js', '/code/'+data['files'][0]['url']]:
        assert request(url).startswith(b'HTTP/1.0 200'), url
    for url in ['/clear-standalone/index.html', '/clear-standalone-anonymous/README.md',
                '/code/../clear-standalone-anonymous/README.md', '/code/%2e%2e/.git/config', '/.git/config']:
        assert request(url).startswith(b'HTTP/1.0 404'), url
    assert request('/code').startswith(b'HTTP/1.0 301')
    response = request('/assets/code-downloads/clear-source.zip', 'Range: bytes=0-1023\r\n')
    assert response.startswith(b'HTTP/1.0 206') and b'Content-Type: application/zip' in response
    assert len(response.split(b'\r\n\r\n', 1)[1]) == 1024
    print(f"PASS {len(data['files'])} source files, exact highlighted text, {len(data['guides'])} guided symbols, local navigation and private-path isolation")


async def browser_checks():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width':1440, 'height':1100})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.goto((ROOT / 'code/index.html').as_uri())
        await page.locator('.code-line').first.wait_for()
        assert await page.locator('.resource[download]').count() == 2
        assert await page.locator('.archive-tree').count() == 2
        for key in ['source', 'checkpoints']:
            tree = page.locator(f'[data-archive-tree="{key}"]')
            root = tree.locator('details').first
            assert await root.get_attribute('open') is not None
            await root.locator('summary').first.click()
            assert await root.get_attribute('open') is None
            await root.locator('summary').first.press('Enter')
            assert await root.get_attribute('open') is not None
        assert await page.locator('.component').count() == 5
        assert await page.locator('.component:visible').count() == 1
        for node in catalog()['nodes']:
            await page.locator(f'[data-flow-node="{node["id"]}"]').click()
            assert await page.locator('.component:visible').count() == 1
            card=page.locator(f'.snippet[data-component="{node["stage"]}"]')
            await card.scroll_into_view_if_needed()
            await page.wait_for_function("id => { const card=document.querySelector('.snippet[data-node=\"'+id+'\"]');return card && !card.querySelector('.code-status').textContent; }", arg=node['id'])
            file = next(f for f in catalog()['files'] if f['path'] == node['file'])
            symbol = next(s for s in file['formattedSymbols'] if s['name']==node['symbol'])
            assert await card.locator('.code-line').count() == symbol['end']-symbol['start']+1
            assert await card.locator('pre').evaluate('el=>el.scrollWidth<=el.clientWidth+1 && el.scrollHeight<=el.clientHeight+1')
            await card.locator('[data-source-scope]').click()
            file = next(f for f in catalog()['files'] if f['path'] == node['file'])
            await page.wait_for_function("count => document.querySelector('.component:not([hidden]) .snippet').querySelectorAll('.code-line').length===count", arg=file['formattedLines'])
            await card.locator('[data-open-source]').click()
            await page.locator('#source-dialog .code-line').first.wait_for()
            assert await page.locator('#source-dialog').is_visible()
            await page.keyboard.press('Escape')
            assert not await page.locator('#source-dialog').is_visible()
        await page.locator('[data-flow-node="control"]').focus()
        await page.keyboard.press('Home')
        assert await page.locator('#grounding').is_visible()
        await page.keyboard.press('ArrowRight')
        assert await page.locator('#ordering').is_visible()
        await page.emulate_media(reduced_motion='reduce')
        assert await page.locator('[data-flow-node=order]').get_attribute('aria-pressed') == 'true'
        for width in [1440, 768, 390]:
            await page.set_viewport_size({'width':width,'height':1100})
            if width <= 1000:
                await page.locator('[data-workspace-view-button=code]').click()
                assert await page.locator('.component:visible .snippet').is_visible()
                assert not await page.locator('.component:visible .result').is_visible()
            if width <= 760:
                await page.locator('#pipeline-select').select_option('verification')
                assert await page.locator('#validation').is_visible()
                assert not await page.locator('#code-system').is_visible()
            assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
            assert await page.locator('.component:visible .snippet pre').evaluate('el=>el.scrollWidth<=el.clientWidth+1 && el.scrollHeight<=el.clientHeight+1'), width
            for node in await page.locator('.pipeline-node').all():
                assert await node.evaluate('e=>e.scrollWidth<=e.clientWidth && e.scrollHeight<=e.clientHeight'), width
            assert await page.locator('.code-link span').is_visible()
            if width <= 1000:
                await page.locator('[data-workspace-view-button=example]').click()
                assert await page.locator('.component:visible .result').is_visible()
                assert not await page.locator('.component:visible .snippet').is_visible()
            await page.screenshot(path=f'/tmp/clear-code-{width}.png', full_page=True)
        assert not errors, errors
        await browser.close()
    print('PASS component excerpts, full source dialog, archive links and responsive code tab')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', action='store_true')
    args = parser.parse_args()
    static_checks()
    if args.browser: asyncio.run(browser_checks())
