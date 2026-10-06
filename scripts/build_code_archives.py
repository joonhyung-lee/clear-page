"""Build complementary source/checkpoint ZIPs from the audited local snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import zipfile

from code_package_layout import checkpoint_layout, README

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'clear-standalone-anonymous'
OUTPUT = ROOT / 'assets/code-downloads'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def archive_metadata(target):
    with zipfile.ZipFile(target) as archive:
        members = [dict(path=i.filename, bytes=i.file_size,
                        type='symlink' if stat.S_ISLNK(i.external_attr >> 16) else 'file')
                   for i in archive.infolist() if not i.is_dir()]
    return dict(url='../assets/code-downloads/'+target.name, bytes=target.stat().st_size,
                sha256=digest(target), files=len(members), members=members)


def main(index_only=False):
    audit = json.loads((PACKAGE / 'docs/tree_audit.json').read_text())
    if audit['status'] != 'passed':
        raise ValueError('Anonymous snapshot audit must pass before packaging')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    layout = checkpoint_layout(PACKAGE, audit)
    extras = {
        'README.md': README.encode(),
        'docs/checkpoint_paths.json': (json.dumps({'schema': 'clear-checkpoint-paths-v1', 'models': layout}, indent=2)+'\n').encode(),
        'tools/link_checkpoints.py': (ROOT / 'release_tools/templates/link_checkpoints.py').read_bytes(),
    }
    def destination(relative):
        if relative in layout:
            return layout[relative]['path']
        return 'docs/SNAPSHOT_README.md' if relative == 'README.md' else relative

    result = {}
    for key, name in [('source', 'clear-source.zip'), ('checkpoints', 'clear-pretrained.zip')]:
        entries = [(p, row) for p, row in audit['scanned_files'].items()
                   if (Path(p).suffix == '.pt') == (key == 'checkpoints')]
        target = OUTPUT / name
        if index_only:
            result[key] = archive_metadata(target)
            continue
        temporary = target.with_suffix('.zip.partial')
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for i, (relative, row) in enumerate(entries):
                path = PACKAGE / relative
                info = zipfile.ZipInfo('clear/' + destination(relative))
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info._compresslevel = 1
                if 'symlink' in row:
                    assert path.is_symlink() and str(path.readlink()) == row['symlink']
                    assert path.resolve().is_relative_to(PACKAGE) and path.exists()
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(info, row['symlink'].encode())
                else:
                    if digest(path) != row['sha256']:
                        raise ValueError('Snapshot changed after its audit: ' + relative)
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    with path.open('rb') as src, archive.open(info, 'w', force_zip64=True) as dst:
                        shutil.copyfileobj(src, dst, length=1024*1024)
                if (i+1) % 50 == 0:
                    print(f'{key}: {i+1}/{len(entries)} files', flush=True)
            if key == 'source':
                for relative, payload in extras.items():
                    info = zipfile.ZipInfo('clear/' + relative)
                    info.create_system = 3
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    archive.writestr(info, payload)
        # Check the bytes stored inside each archive, including symlink targets.
        with zipfile.ZipFile(temporary) as archive:
            for relative, row in entries:
                with archive.open('clear/' + destination(relative)) as stream:
                    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
                expected = row.get('sha256') or hashlib.sha256(row['symlink'].encode()).hexdigest()
                if actual != expected:
                    raise ValueError('Archive member changed: ' + relative)
            if key == 'source':
                for relative, payload in extras.items():
                    if archive.read('clear/' + relative) != payload:
                        raise ValueError('Generated package file changed: ' + relative)
        temporary.replace(target)
        result[key] = archive_metadata(target)
        print(f'{key}: archive verified', flush=True)
    (ROOT / 'assets/code-archives.js').write_text('window.CLEAR_CODE_ARCHIVES='+json.dumps(result,separators=(',', ':'))+';\n')
    print(json.dumps({key: {k: v for k, v in row.items() if k != 'members'} for key, row in result.items()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index-only', action='store_true', help='Read existing ZIP contents without rebuilding archives')
    main(parser.parse_args().index_only)
