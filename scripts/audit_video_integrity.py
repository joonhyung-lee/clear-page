"""Decode every published MP4 and report timing and content cadence separately.

Static intervals are diagnostic findings, not evidence of broken recordings.
The report stays outside the published site by default.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess

import imageio_ffmpeg
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def audit(path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    probe = subprocess.run([ffmpeg, '-hide_banner', '-i', str(path), '-an',
        '-vf', 'scale=64:48,format=gray,showinfo', '-vsync', '0',
        '-f', 'rawvideo', '-'], capture_output=True)
    log = probe.stderr.decode(errors='replace')
    pts = np.asarray([float(t) for t in re.findall(r'\bn:\s*\d+\s+pts:\s*-?\d+\s+pts_time:([\d.e+-]+)', log)])
    frames = np.frombuffer(probe.stdout, np.uint8)
    count = frames.size // (64 * 48)
    errors = []
    if probe.returncode or count < 1 or count != len(pts):
        errors.append('decode failure or timestamp/frame count mismatch')
    steps = np.diff(pts)
    median = float(np.median(steps)) if len(steps) else 0
    if len(steps) and (np.any(steps <= 0) or np.any(steps > median * 1.55)):
        errors.append('nonmonotonic timestamps or frame gap')
    images = frames[:count*64*48].reshape(count, 64*48).astype(np.float32)
    changes = np.abs(np.diff(images, axis=0)).mean(axis=1)
    still = changes < .08
    run = longest = 0
    for value in still:
        run = run + 1 if value else 0
        longest = max(longest, run)
    return dict(file=path.relative_to(ROOT).as_posix(), frames=count,
        fps=round(1/median, 3) if median else 0,
        duration=round(float(pts[-1]+median), 4) if len(pts) else 0,
        maxFrameGap=round(float(steps.max()), 5) if len(steps) else 0,
        nearStaticFraction=round(float(still.mean()), 4) if len(still) else 0,
        longestNearStaticSeconds=round(longest*median, 3), errors=errors)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('/tmp/clear-video-integrity.json'))
    args=p.parse_args()
    files=sorted((ROOT/'assets').rglob('*.mp4'))
    rows=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for row in pool.map(audit, files):
            rows.append(row)
            if row['errors']: print('FAIL', row['file'], row['errors'], flush=True)
            elif len(rows)%25==0: print('Decoded', len(rows), '/', len(files), flush=True)
    args.output.write_text(json.dumps(rows, indent=2)+'\n')
    print('Audited',len(rows),'videos;',sum(bool(r['errors']) for r in rows),'timing/decode failures')
    print('Report:',args.output)
    raise SystemExit(any(r['errors'] for r in rows))


if __name__=='__main__': main()
