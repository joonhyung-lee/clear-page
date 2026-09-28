"""Make metadata-free web videos from a local media archive."""
import argparse
from pathlib import Path
import subprocess
import imageio_ffmpeg

p = argparse.ArgumentParser()
p.add_argument('archive', type=Path)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
media = root / 'assets/media'
media.mkdir(exist_ok=True)
jobs = [
 ('teaser', a.archive/'teaser/all__topdown_course.mp4', 'crop=1380:1820:290:0,transpose=1,scale=1920:-2,fps=30'),
 ('accessibility', a.archive/'affordance_renders/wider_35pct/blender/accessibility_g1/third_view.mp4', 'fps=30'),
 ('capability', a.archive/'affordance_renders/wider_35pct/blender/capability_g1/third_view.mp4', 'fps=30'),
]
for name, source, vf in jobs:
 subprocess.run([ffmpeg,'-y','-v','error','-i',str(source),'-map','0:v:0','-an','-map_metadata','-1','-map_chapters','-1','-vf',vf,'-c:v','libx264','-crf','22','-preset','fast','-pix_fmt','yuv420p','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(media/f'{name}.mp4')],check=True)
 subprocess.run([ffmpeg,'-y','-v','error','-ss','5','-i',str(media/f'{name}.mp4'),'-frames:v','1','-map_metadata','-1',str(media/f'{name}.png')],check=True)
 print(name,flush=True)
