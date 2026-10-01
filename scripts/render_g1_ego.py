"""Reconstruct the native G1 torso camera from unchanged saved body poses.

The camera matches record_sumo_native.py: torso offset (0.14, 0, 0.30),
forward +X, up +Z, vertical FOV 60 degrees. This is a rendered replay view,
not an additional sensor recording. No robot or object trajectory is changed.
"""
import json
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
from PIL import Image
from playwright.sync_api import sync_playwright

from check_research_visuals import FIND, SEEK

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / 'assets/media'
FPS = 20
CAMERA = """()=>{
 const v=testViewer,m=v.mutable.current,n=m.nodeRefFromName['/tracking/body-16'];
 if(!n)throw new Error('Missing native G1 torso');
 n.updateWorldMatrix(true,false);
 const eye=n.localToWorld(m.camera.position.clone().set(.14,0,.30));
 const at=n.localToWorld(m.camera.position.clone().set(1.14,0,.30));
 const up=m.camera.up.clone().set(0,0,1).transformDirection(n.matrixWorld);
 m.camera.up.copy(up);m.cameraControl.updateCameraUp();
 m.cameraControl.setLookAt(...eye.toArray(),...at.toArray(),false);
 m.camera.fov=60;m.camera.near=.005;m.camera.updateProjectionMatrix();
 for(const [name,node] of Object.entries(v.useSceneTree.getAll())){
  if(/candidate|waypoint|palm-centers|body-contacts|reference-path/.test(name)
     &&node.visibility!==false)v.sceneTreeActions.updateNodeAttributes(name,{visibility:false});
 }
}"""


def main():
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory(prefix='clear-g1-ego-') as folder, sync_playwright() as pw:
        temporary = Path(folder) / 'ego.mp4'
        browser = pw.chromium.launch(args=['--use-angle=vulkan', '--enable-features=Vulkan',
            '--disable-vulkan-surface', '--enable-gpu', '--ignore-gpu-blocklist'])
        page = browser.new_page(viewport={'width': 480, 'height': 360})
        page.goto('http://localhost:8765/assets/viser/index.html?playbackPath=/assets/recordings/mpc-baseline.viser')
        page.locator('input').first.wait_for(timeout=60000)
        assert page.evaluate(FIND)
        page.add_style_tag(content='body *:not(:has(canvas)):not(canvas){visibility:hidden!important} canvas{visibility:visible!important}')
        process = subprocess.Popen([ffmpeg, '-y', '-v', 'error', '-f', 'image2pipe',
            '-framerate', str(FPS), '-vcodec', 'png', '-i', '-', '-an', '-map_metadata', '-1',
            '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-fflags', '+bitexact',
            '-flags:v', '+bitexact', '-movflags', '+faststart', str(temporary)], stdin=subprocess.PIPE)
        try:
            for frame in range(40 * FPS):
                page.evaluate(SEEK, frame / FPS)
                page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                page.evaluate(CAMERA)
                page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                picture = page.screenshot(timeout=15000)
                process.stdin.write(picture)
                if frame == 0:
                    (MEDIA / 'mpc-baseline-ego.png').write_bytes(picture)
                if frame in [100, 280, 700]:
                    (Path(folder) / f'frame-{frame}.png').write_bytes(picture)
                    (Path('/tmp') / f'clear-g1-ego-{frame}.png').write_bytes(picture)
                if frame % 100 == 0:
                    print('G1 torso camera', frame, '/', 40 * FPS, flush=True)
        finally:
            process.stdin.close()
            code = process.wait()
            browser.close()
        assert code == 0
        temporary.replace(MEDIA / 'mpc-baseline-ego.mp4')
        subprocess.run([ffmpeg, '-y', '-v', 'error', '-ss', '1.545', '-i',
            str(MEDIA / 'mpc-baseline-ego.mp4'), '-t', '12.595', '-an', '-map_metadata', '-1',
            '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-fflags', '+bitexact',
            '-flags:v', '+bitexact', '-movflags', '+faststart',
            str(MEDIA / 'mpc-baseline-push-ego.mp4')], check=True)
        subprocess.run([ffmpeg, '-y', '-v', 'error', '-i', str(MEDIA / 'mpc-baseline-push-ego.mp4'),
            '-frames:v', '1', '-update', '1', str(MEDIA / 'mpc-baseline-push-ego.png')], check=True)
        with Image.open(MEDIA / 'mpc-baseline-push-ego.png') as poster:
            clean = Image.new('RGB', poster.size)
            clean.paste(poster)
            clean.save(MEDIA / 'mpc-baseline-push-ego.png')
        manifest_path = ROOT / 'assets/mpc-comparison.json'
        manifest = json.loads(manifest_path.read_text())
        for entry in manifest:
            if entry['scene'] == 'mpc-baseline':
                entry['insetView'] = ('Reconstructed torso camera from saved native body transforms. '
                    'Camera offset (0.14, 0, 0.30) m, forward +X, up +Z, vertical FOV 60 degrees. '
                    'Display annotations are hidden. This is a replay rendering, not sensor telemetry.')
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        print('PASS native G1 camera, full 40 s and matching contact interval', flush=True)


if __name__ == '__main__':
    main()
