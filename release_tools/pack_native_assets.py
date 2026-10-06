"""Copy the robot descriptions used by the shipped registry, preserving geometry."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

BUNDLES = ('g1_wo_wrist', 'spot', 'spot_w_arm', 'google_robot', 'husky')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strip_png_metadata(data):
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Invalid PNG signature')
    output, removed, offset = bytearray(data[:8]), [], 8
    while offset < len(data):
        length = struct.unpack('>I', data[offset:offset+4])[0]
        kind = data[offset+4:offset+8]
        end = offset + 12 + length
        if end > len(data):
            raise ValueError('Truncated PNG chunk')
        if kind in {b'tEXt', b'zTXt', b'iTXt', b'eXIf', b'tIME', b'pHYs'}:
            removed.append(kind.decode())
        else:
            output.extend(data[offset:end])
        offset = end
    return bytes(output), removed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--destination', required=True, type=Path)
    args = p.parse_args()
    source, root = args.source.resolve(), args.destination.resolve()
    manifest_path = root / 'docs/artifact_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    original_manifest = json.loads((source / 'artifact_manifest.json').read_text())['files']
    copies = []
    for bundle in BUNDLES:
        for original in sorted((source / 'assets' / bundle).rglob('*')):
            if not original.is_file():
                continue
            relative = original.relative_to(source).as_posix()
            digest = sha(original)
            if relative in original_manifest and original_manifest[relative].get('sha256') != digest:
                raise ValueError('Robot asset differs from source release: ' + relative)
            copies.append((original, relative, digest))
    for original, relative, digest in copies:
        target = root / 'runtime' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        changes = []
        if target.exists():
            previous = manifest['files'].get('runtime/' + relative)
            if previous and sha(target) != previous.get('sha256'):
                raise ValueError('Refusing to overwrite an edited robot asset')
        if relative == 'assets/husky/README.md':
            content = original.read_text()
            start, end = content.index('Copied on '), content.index('The XML and five STL meshes')
            content = content[:start] + 'Conversion-source attribution is withheld in this anonymous working copy.\n\n' + content[end:]
            target.write_text(content)
            changes.append('Withheld identifying conversion-source paragraph; retained licensing limitations and dynamics description')
        elif original.suffix.lower() == '.png':
            content, removed = strip_png_metadata(original.read_bytes())
            target.write_bytes(content)
            if removed:
                changes.append(dict(operation='Remove ancillary PNG metadata; preserve image data chunks', chunks=removed))
        else:
            if target.exists() and sha(target) != digest:
                raise ValueError('Refusing to overwrite different robot geometry')
            shutil.copyfile(original, target)
        manifest['files']['runtime/' + relative] = dict(source_path=relative, source_sha256=digest,
            sha256=sha(target), bytes=target.stat().st_size, changes=changes)
    alias = root / 'runtime/asset'
    if alias.is_symlink():
        if alias.readlink().as_posix() != 'assets':
            raise ValueError('Unexpected asset compatibility alias')
    elif alias.exists():
        raise ValueError('Refusing to replace existing asset directory')
    else:
        alias.symlink_to('assets', target_is_directory=True)
    manifest['files']['runtime/asset'] = dict(symlink='assets',
        changes=['Internal relative compatibility alias; no paths outside the package'])
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(robot_asset_files=len(copies), compatibility_alias='asset -> assets')))


if __name__ == '__main__':
    main()
