"""Create the small, fast-start muted teaser without changing its timing."""
from pathlib import Path
import subprocess
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y',
 '-i',str(ROOT/'assets/media/teaser.mp4'),'-an','-map_metadata','-1',
 '-vf','scale=1280:-2,fps=24','-c:v','libx264','-preset','slow','-crf','29',
 '-pix_fmt','yuv420p','-g','48','-movflags','+faststart',
 str(ROOT/'assets/media/teaser-stream.mp4')],check=True)
