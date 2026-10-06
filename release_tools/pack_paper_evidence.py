"""Copy the available revision's table evidence without exporting the manuscript.

The original table checker is preserved. All parsed tables must match the full
source manuscript, so extracting tables cannot silently narrow its coverage.
This does not export raw episodes, figures or the newer handoff's evidence.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--private-term', action='append', required=True)
    args = parser.parse_args()
    source, root = args.source.resolve(), args.destination.resolve()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(source))
    script = source / 'scripts/leap2026/check_paper_map.py'
    spec = importlib.util.spec_from_file_location('original_table_checker', script)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    tex_path = source / 'paper/main.tex'
    full = tex_path.read_text()
    tables = '\n\n'.join(m[0] for m in re.finditer(
        r'\\begin\{table\*?\}.*?\\end\{table\*?\}', full, re.S)) + '\n'
    parsed = checker.parse_tables(full)
    if not parsed or checker.parse_tables(tables) != parsed:
        raise ValueError('Table extraction changed the original verification scope')
    map_path = source / 'outputs/leap2026/PAPER_MAP.md'
    mapping = checker.parse_map(map_path)
    needed = set()
    numeric_cells = 0
    for label, cells in parsed.items():
        for row, col, raw in cells:
            if checker.parse_cell(raw) is None:
                continue
            key = (label, checker.strip_latex(row), checker.strip_latex(col))
            evidence, _, _ = mapping[key]
            relative = evidence.split(':', 1)[0].strip()
            path = source / relative
            if not path.resolve().is_relative_to(source) or path.suffix != '.csv':
                raise ValueError('Expected numeric CSV evidence: ' + relative)
            needed.add(relative)
            numeric_cells += 1
    sm_path, am_path = (root / 'docs' / n for n in ('source_manifest.json', 'artifact_manifest.json'))
    sm, am = json.loads(sm_path.read_text()), json.loads(am_path.read_text())

    def put(relative, data, origin, changes, source_file=False):
        text = data.decode('utf-8')
        if any(term.lower() in text.lower() for term in args.private_term):
            raise ValueError('Private term in evidence; manual review required: ' + relative)
        if re.search(r'/(?:home|mnt)/', text):
            raise ValueError('Private absolute path in evidence: ' + relative)
        target = root / relative
        if target.exists() and target.read_bytes() != data:
            raise ValueError('Refusing to overwrite changed evidence: ' + relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        entry = dict(source_path=str(origin.relative_to(source)),
                     source_sha256=digest(origin.read_bytes()), sha256=digest(data),
                     bytes=len(data), changes=changes)
        (sm if source_file else am)['files'][relative] = entry

    put('runtime/scripts/leap2026/check_paper_map.py', script.read_bytes(), script, [], True)
    put('runtime/paper/tables.tex', tables.encode(), tex_path,
        ['extract all table environments; parsed tables equal the full manuscript'])
    put('runtime/outputs/leap2026/PAPER_MAP.md', map_path.read_bytes(), map_path, [])
    for relative in sorted(needed):
        put('runtime/' + relative, (source / relative).read_bytes(), source / relative, [])
    sm_path.write_text(json.dumps(sm, indent=2) + '\n')
    am_path.write_text(json.dumps(am, indent=2) + '\n')
    report = dict(schema='clear-standalone-paper-evidence-v1', tables=len(parsed),
        numeric_cells=numeric_cells, csv_files=sorted(needed),
        manuscript_sha256=digest(tex_path.read_bytes()),
        extracted_tables_equivalent=True, manuscript_text_included=False,
        scope='all numeric table cells in the available source revision',
        figures_verified=False, physical_reproduction_performed=False,
        latest_handoff_revision_verified=False)
    (root / 'docs/paper_evidence.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(tables=len(parsed), numeric_cells=numeric_cells, csv_files=len(needed))))


if __name__ == '__main__':
    main()
