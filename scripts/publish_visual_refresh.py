"""Publish completed palette renders, their recordings, and matching web metadata."""
import argparse
import fcntl
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from recording_io import read_recording, write_recording, compact_buffers
from style_recorded_palette import restyle

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish_scenes(directory):
    provenance = ROOT / 'assets/visual-style-provenance.json'
    existing = json.loads(provenance.read_text()) if provenance.exists() else {'palette': 'design-tokens.json', 'scenes': []}
    entries = {entry['scene']: entry for entry in existing['scenes']}
    backup = ROOT / '.git/visual-refresh/original-recordings'
    backup.mkdir(parents=True, exist_ok=True)
    for report in sorted(directory.glob('*.json')):
        entry = json.loads(report.read_text())
        scene = entry['scene']
        if scene.startswith(('teaser', 'tldr')):
            raise ValueError('Teaser is excluded')
        source = ROOT / 'assets/recordings' / (scene + '.viser')
        source_scene = entry.get('sourceScene', scene)
        original = backup / (source_scene + '.viser')
        if not original.exists():
            shutil.copyfile(ROOT / 'assets/recordings' / original.name, original)
        expected_source=ROOT/'assets/recordings'/f'{source_scene}.viser' if entry.get('currentRecording') else original
        if sha(expected_source) != entry['sourceSHA256']:
            raise ValueError(f'Source recording changed: {scene}')
        rendered_recording = directory / (scene + '.viser')
        if rendered_recording.exists():
            shutil.copyfile(rendered_recording, source)
        else:
            record, buffers = restyle(*read_recording(original))
            record, buffers = compact_buffers(record, buffers)
            with tempfile.TemporaryDirectory() as tmp:
                staged = Path(tmp) / source.name
                write_recording(staged, record, buffers)
                shutil.copyfile(staged, source)
        source.with_suffix('.hex.js').write_text(
            'window.CLEAR_RECORDINGS = window.CLEAR_RECORDINGS || {};\n'
            + f'window.CLEAR_RECORDINGS[{json.dumps(scene)}] = '
            + json.dumps(source.read_bytes().hex()) + ';\n')
        for suffix in ('.mp4', '.png'):
            shutil.copyfile(directory / (scene + suffix), ROOT / 'assets/media' / (scene + suffix))
        entry['renderSHA256'] = sha(directory / (scene + '.mp4'))
        entries[scene] = entry
    existing['scenes'] = list(entries.values())
    provenance.write_text(json.dumps(existing, indent=2) + '\n')
    print(f'Published {len(list(directory.glob("*.json")))} scene renders', flush=True)


def publish_policy(directory):
    rows = json.loads((directory / 'policy-video-provenance.json').read_text())
    bodies = set()
    for row in rows:
        stem = Path(row['file']).stem
        files = [directory / row['file'], directory / (stem + '.webp')]
        for view in row['views']:
            files.extend(directory / (stem + '-' + view['key'] + suffix) for suffix in ('.mp4', '.webp'))
        for path in files:
            shutil.copyfile(path, ROOT / 'assets/media' / path.name)
        row.update(visualStyle='editorial-v1', palette='design-tokens.json', renderSHA256=sha(directory / row['file']))
        bodies.add('spot' if row['scene'] == 'learning-spot-heading' else row['scene'].removeprefix('learning-'))
    target = ROOT / 'assets/policy-video-provenance.json'
    previous = json.loads(target.read_text())
    names = {row['file'] for row in rows}
    target.write_text(json.dumps([row for row in previous if row['file'] not in names] + rows, indent=2) + '\n')
    for body in bodies:
        name = 'spot-curriculum-data.js' if body == 'spot' else body + '-restored-data.js'
        path = ROOT / 'assets' / name
        assignment = f'window.CLEAR_BODY_CURRICULA["{body}"] = '
        prefix, raw = path.read_text().split(assignment, 1)
        data = json.loads(raw.strip().removesuffix(';'))
        for stage in data.get('checkpoints', data.get('stages', [])):
            replay = stage.get('replay')
            if replay and Path(replay.get('video', '')).name in names:
                replay['visualStyle'] = 'editorial-v1'
        path.write_text(prefix + assignment + json.dumps(data, separators=(',', ':')) + ';\n')
    print(f'Published {len(rows)} policy checkpoints and terrain views', flush=True)


def publish_cameras(directory):
    """Publish completed main/Ego camera exports and their material-matched replay."""
    report = json.loads((directory / 'render.json').read_text())
    scene = report['scene']
    backup = ROOT / '.git/visual-refresh/original-recordings' / (scene + '.viser')
    source = ROOT / 'assets/recordings' / backup.name
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copyfile(source, backup)
    if report.get('currentRecording'):
        if sha(source) != report['sourceSHA256']:
            raise ValueError(f'Rendered recording changed: {scene}')
    else:
        if report.get('sourceSHA256') and sha(backup) != report['sourceSHA256']:
            raise ValueError(f'Source recording changed: {scene}')
        record, buffers = restyle(*read_recording(backup))
        write_recording(source, record, buffers)
    provenance = ROOT / 'assets/camera-video-provenance.json'
    entries = json.loads(provenance.read_text()) if provenance.exists() else {}
    for view in ('contact', 'ego'):
        video = directory / f'{scene}-{view}.mp4'
        if not video.exists():
            continue
        poster = directory / f'{scene}-{view}-0.png'
        if not poster.exists():
            raise ValueError(f'Missing poster: {video.name}')
        name=scene if scene.startswith('mpc-spot-') and view=='contact' else f'{scene}-{view}'
        shutil.copyfile(video, ROOT / 'assets/media' / f'{name}.mp4')
        shutil.copyfile(poster, ROOT / 'assets/media' / f'{name}.png')
        entries[f'{name}.mp4'] = dict(report, view=view,
            renderSHA256=sha(video), renderer='Native Viser',
            robotMaterials='original recorded colors')
    provenance.write_text(json.dumps(entries, indent=2) + '\n')
    print(f'Published camera views for {scene}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenes-dir', type=Path)
    parser.add_argument('--policy-dir', type=Path)
    parser.add_argument('--cameras-dir', type=Path)
    args = parser.parse_args()
    with (ROOT / '.git/visual-refresh-publish.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.scenes_dir:
            publish_scenes(args.scenes_dir)
        if args.policy_dir:
            publish_policy(args.policy_dir)
        if args.cameras_dir:
            publish_cameras(args.cameras_dir)
        for script in ('build_asset_revisions.py', 'build_site_bundle.py'):
            subprocess.run([sys.executable, str(ROOT / 'scripts' / script)], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
