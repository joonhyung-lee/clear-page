"""Build an anonymous, static reading view of the verified source snapshot.

The code is displayed, never executed. This reader includes only the component
excerpts and their related modules. Full source is provided by the source ZIP.
"""
import ast
import hashlib
import html
import io
import json
import keyword
from pathlib import Path
import re
import tokenize
import black

from code_system_spec import NODES, diagram

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'clear-standalone-anonymous'
OUT = ROOT / 'code'
CORE = 'runtime/clear/model/clear_core.py'
MORPH = 'runtime/experiments/exp3/trajectory_v3/shared_morphology.py'
PLANNER = 'runtime/experiments/exp3/trajectory_v3/navigation_planner.py'

GUIDES = [
    dict(id='grounding', label='Grounding', title='Embodiment-conditioned grounding',
         description='Robot structure is encoded with masked pooling and combined with object and scene features.',
         file='runtime/clear/model/structure_encoder.py', symbol='StructureEncoder.pool',
         notes=[], related=[CORE]),
    dict(id='ordering', label='Selection and order', title='Select objects and sample their order',
         description='Selection logits identify participating objects. Sampled latent scores determine their order.',
         file=CORE, symbol='OrderingHead.sample', notes=[], related=[]),
    dict(id='generation', label='Object generation', title='Ordered object trajectory generation',
         description='Rank-conditioned flow generates object targets while preserving access to observed scene geometry.',
         file='runtime/clear/model/target_flow.py', symbol='RankCausalTargetFlow.sample',
         notes=[], related=[CORE]),
    dict(id='validation', label='Feasibility', title='Validate the interaction sequence',
         description='Each proposed interaction updates the scene used to check the next approach and the final route.',
         file=PLANNER, symbol='validate_sequence', notes=[], related=[]),
    dict(id='execution', label='Execution', title='Execute interactions and reach the goal',
         description='Execute object references, update observations and navigate through the opened passages.',
         file='runtime/experiments/exp3/trajectory_v3/native_sumo_task.py', symbol='SumoTaskBackend',
         notes=[], related=[]),
]


def js(value):
    return json.dumps(value, ensure_ascii=True, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def symbols(text):
    result = []
    def visit(node, prefix=''):
        for child in getattr(node, 'body', []):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + child.name
                start = min([child.lineno, *[d.lineno for d in child.decorator_list]])
                result.append(dict(name=name, start=start, end=child.end_lineno))
                visit(child, name + '.')
    visit(ast.parse(text))
    return result


def highlighted_lines(text, python):
    # Token positions come from Python's own lexer. Escape every source character
    # before adding our fixed span tags, so source text can never become markup.
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    spans = []
    if python:
        previous = ''
        for t in tokenize.generate_tokens(io.StringIO(text).readline):
            category = {tokenize.STRING:'string', tokenize.COMMENT:'comment', tokenize.NUMBER:'number'}.get(t.type)
            if t.type == tokenize.NAME:
                if keyword.iskeyword(t.string): category = 'keyword'
                elif previous in ('class', 'def'): category = 'definition'
                elif t.string in ('self', 'True', 'False', 'None'): category = 'builtin'
            if category:
                start = offsets[t.start[0]-1] + t.start[1]
                end = offsets[t.end[0]-1] + t.end[1]
                spans.append((start, end, category))
            if t.type not in (tokenize.INDENT, tokenize.DEDENT, tokenize.NL, tokenize.NEWLINE):
                previous = t.string
    pieces, cursor = [], 0
    for start, end, category in spans:
        pieces.append(html.escape(text[cursor:start]))
        pieces.append('\n'.join(f'<span class="tok-{category}">{html.escape(part)}</span>' for part in text[start:end].split('\n')))
        cursor = end
    pieces.append(html.escape(text[cursor:]))
    rendered = ''.join(pieces).split('\n')
    if text.endswith('\n'): rendered.pop()
    return rendered or ['']


def formatted_source(text):
    """Format the reading view while retaining the audited archive verbatim."""
    try:
        formatted = black.format_file_contents(
            text, fast=False, mode=black.Mode(line_length=88)
        )
    except black.NothingChanged:
        formatted = text
    return dict(text=formatted, lines=highlighted_lines(formatted, True),
                symbols=symbols(formatted))


def main():
    audit = json.loads((PACKAGE / 'docs/tree_audit.json').read_text())
    if audit['status'] != 'passed':
        raise ValueError('The source snapshot must pass its anonymous payload audit first')
    OUT.mkdir(exist_ok=True)
    (OUT / 'source').mkdir(exist_ok=True)
    files = []
    needed = {path for guide in GUIDES for path in [guide['file'], *guide['related']]}
    needed.update(node['file'] for node in NODES)
    for path in sorted(PACKAGE.rglob('*')):
        if not path.is_file() or path.is_symlink() or '__pycache__' in path.parts:
            continue
        relative = path.relative_to(PACKAGE).as_posix()
        if relative not in needed:
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if audit['scanned_files'].get(relative, {}).get('sha256') != digest:
            raise ValueError('Source changed since its anonymity audit: ' + relative)
        text = data.decode('utf-8')
        headings = symbols(text) if path.suffix == '.py' else []
        doc = ast.get_docstring(ast.parse(text)) if path.suffix == '.py' else None
        summary = ' '.join(doc.split('\n\n')[0].split())[:450] if doc else ''
        payload = dict(text=text, lines=highlighted_lines(text, path.suffix == '.py'))
        if path.suffix == '.py':
            payload['formatted'] = formatted_source(text)
        # Identical source bytes at two paths still need separate registration.
        display_digest = hashlib.sha256(js(payload).encode()).hexdigest()[:12]
        filename = hashlib.sha256(relative.encode()).hexdigest()[:16] + '-' + display_digest + '.js'
        (OUT / 'source' / filename).write_text('window.CLEAR_CODE.register(' + js(relative) + ',' + js(payload) + ');\n')
        files.append(dict(path=relative, sha256=digest, bytes=len(data), lines=len(payload['lines']),
                          language='Python' if path.suffix=='.py' else path.suffix[1:].upper(),
                          url='source/' + filename, symbols=headings, summary=summary,
                          formattedLines=len(payload.get('formatted', payload)['lines']),
                          formattedSymbols=payload.get('formatted', {}).get('symbols', headings)))
    by_path = {f['path']:f for f in files}
    for guide in GUIDES:
        spec = by_path[guide['file']]
        symbol = next(s for s in spec['symbols'] if s['name'] == guide['symbol'])
        guide.update(start=symbol['start'], end=symbol['end'])
        if guide.get('excerpt_from'):
            lines = (PACKAGE / guide['file']).read_text().splitlines()
            start = next(i for i in range(symbol['start']-1, symbol['end']) if lines[i].startswith(guide['excerpt_from']))
            end = next(i for i in range(start, symbol['end']) if lines[i].startswith(guide['excerpt_through']))
            guide.update(start=start+1, end=end+1)
        for related in guide['related']:
            if related not in by_path:
                raise ValueError('Missing related source: ' + related)
    for node in NODES:
        spec = by_path[node['file']]
        symbol = next(s for s in spec['symbols'] if s['name'] == node['symbol'])
        node.update(start=symbol['start'], end=symbol['end'])
    keep = {f['url'].split('/')[-1] for f in files}
    for old in (OUT / 'source').glob('*.js'):
        if old.name not in keep: old.unlink()
    catalog = dict(files=files, guides=GUIDES, nodes=NODES, source='Anonymous standalone snapshot',
                   sourceFiles=len(files), executable=False)
    (OUT / 'catalog.js').write_text('window.CLEAR_CODE_CATALOG=' + js(catalog) + ';\n')
    index = OUT / 'index.html'
    markup = index.read_text()
    block = '<!-- code-system:start -->\n' + diagram() + '\n<!-- code-system:end -->'
    if '<!-- code-system:start -->' in markup:
        markup = re.sub(r'<!-- code-system:start -->.*?<!-- code-system:end -->', lambda _: block, markup, flags=re.S)
    else:
        markup = re.sub(r'<svg\b(?=[^>]*\bid="code-system")[^>]*>.*?</svg>', lambda _: block, markup, flags=re.S)
    for node in NODES:
        pattern = r'(<span\b[^>]*data-source-path="' + re.escape(node['stage']) + r'"[^>]*>).*?(</span>)'
        markup = re.sub(pattern, lambda m: m[1] + '(' + html.escape(node['file']) + ')' + m[2], markup, flags=re.S)
    resources = set(re.findall(r'(?:href|src|poster)="([^"?]+)(?:\?v=[a-f0-9]+)?"', markup))
    for name in sorted(resources):
        if Path(name).suffix not in {'.js', '.css', '.png', '.webp', '.mp4', '.svg'} or not name.startswith(('code.css', 'code.js', 'catalog.js', '../assets/')) or not (OUT / name).is_file():
            continue
        revision = hashlib.sha256((OUT / name).read_bytes()).hexdigest()[:12]
        markup = re.sub(r'((?:href|src|poster)=")' + re.escape(name) + r'(?:\?v=[a-f0-9]+)?"',
                        lambda m: m[1] + name + '?v=' + revision + '"', markup)
    index.write_text(markup)
    print(json.dumps(dict(source_files=len(files), guided_sections=len(GUIDES), code_executed=False)))


if __name__ == '__main__':
    main()
