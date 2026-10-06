"""Replace provenance-only Git queries in the exported code; preserve source originals."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent / 'templates/provenance.py'


def replace_function(text, name, replacement):
    tree = ast.parse(text)
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise ValueError('Expected exactly one ' + name)
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    return ''.join(lines[:node.lineno-1]) + replacement + '\n' + ''.join(lines[node.end_lineno:])


def add_import(text):
    tree = ast.parse(text)
    after = 0
    for node in tree.body:
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
                or isinstance(node, ast.ImportFrom) and node.module == '__future__'):
            after = node.end_lineno
        else:
            break
    lines = text.splitlines(keepends=True)
    return ''.join(lines[:after]) + 'from clear.provenance import package_revision\n' + ''.join(lines[after:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True, type=Path)
    args = parser.parse_args()
    root = args.destination.resolve()
    manifest_path = root / 'docs/source_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    edits = {}
    relative = 'runtime/experiments/exp2/train_comparison.py'
    text = (root / relative).read_text()
    old = "subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()"
    if text.count(old) != 1:
        raise ValueError('Unexpected manipulation provenance implementation')
    edits[relative] = add_import(text.replace(old, "package_revision()['commit']"))
    relative = 'runtime/experiments/exp3/trajectory_v3/training_state.py'
    edits[relative] = replace_function((root / relative).read_text(), 'source_revision',
        'def source_revision():\n    from clear.provenance import package_revision\n    return package_revision()\n')
    relative = 'runtime/experiments/exp1/evaluator.py'
    text = (root / relative).read_text()
    old = '''    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        commit = "unknown"
'''
    if text.count(old) != 1:
        raise ValueError('Unexpected Grid provenance implementation')
    edits[relative] = text.replace(old, "    from clear.provenance import package_revision\n    commit = package_revision()['commit']\n")
    relative = 'runtime/scripts/leap2026/common.py'
    edits[relative] = replace_function((root / relative).read_text(), 'git_sha',
        "def git_sha(cwd: Path = REPO) -> str:\n    from clear.provenance import package_revision\n    return package_revision()['commit']\n")
    edits['runtime/clear/provenance.py'] = TEMPLATE.read_text()
    for relative, text in edits.items():
        ast.parse(text)
        path = root / relative
        if relative in manifest['files']:
            record = manifest['files'][relative]
            if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
                raise ValueError('Refusing to modify changed export: ' + relative)
        else:
            record = dict(source_path=None, source_sha256=None, changes=[])
            manifest['files'][relative] = record
        path.write_text(text)
        record.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)
        record['changes'].append('Standalone provenance uses actual packaged source hashes, never ancestor Git metadata')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Patched {len(edits)} provenance source files')


if __name__ == '__main__':
    main()
