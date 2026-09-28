"""Create a silent, metadata-free H.264 copy of the supplied TL;DR video."""
import argparse
from pathlib import Path
import subprocess
import imageio_ffmpeg
p=argparse.ArgumentParser();p.add_argument('source',type=Path);a=p.parse_args()
out=Path(__file__).resolve().parents[1]/'assets/media'
ff=imageio_ffmpeg.get_ffmpeg_exe()
subprocess.run([ff,'-y','-v','error','-i',str(a.source),'-map','0:v:0','-an','-map_metadata','-1','-map_chapters','-1','-c:v','libx264','-crf','20','-preset','fast','-pix_fmt','yuv420p','-fflags','+bitexact','-flags:v','+bitexact','-movflags','+faststart',str(out/'tldr.mp4')],check=True)
subprocess.run([ff,'-y','-v','error','-ss','5','-i',str(out/'tldr.mp4'),'-frames:v','1','-map_metadata','-1',str(out/'tldr.png')],check=True)
print('TL;DR video and poster ready')
