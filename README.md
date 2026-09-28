# CLEAR — anonymous local preview

```sh
python scripts/serve.py
```

Open **http://localhost:8765**. The server binds to loopback and serves only
`index.html` and `assets/`; repository metadata and scripts are not served.
No build step, remote font, analytics service, or live Viser server is required.
Lazy script packages embed recordings directly into the viewer so anonymous
hosting sandbox policies do not require a cross-origin recording fetch.

## Page and media

- One sans-serif typeface, restrained headings, white surfaces, and plain spacing.
- Full-width top-down background video with a centered paper title on a
  translucent white rectangle. The original course is rotated clockwise.
- TL;DR includes the supplied final research video (about 2 minutes 47 seconds).
  There is no separate Teaser section. The full-width background remains above.
  The public video is a silent H.264 copy with source metadata removed; the
  local source file is excluded from Git and is not served by the preview server.
- Robot structure has four separate clips in a 2 by 2 grid for G1, Spot,
  Spot + arm, and Husky. Visual meshes use their original XML material colors
  at 18 percent opacity. Nodes are link frame origins and edges follow the
  model parent hierarchy, exposing the articulated structure through the shell.
- Scene has four clips for stairs, a stepped bridge, a slope, and a mixed
  terrain maze. Each uses recorded poses. The stepped
  bridge preserves the original contact heights with an illustrative supported
  deck and omits surrounding walls. The mixed scene combines three
  independent trajectories on a normalized playback timeline.
- Hovering a tile enlarges its preview at the center of its own grid. Clicking
  or pressing Enter also opens it. Play in 3D loads the corresponding local
  Viser recording. Escape or the close button dismisses the expanded preview.
- Object states remains a separate interactive panel.
- Accessibility and Capability retain their explanatory videos and include
  buttons to inspect highlighted meshes. Accessibility highlights arm and
  gripper chains on G1 and Spot + arm. Capability highlights support and
  actuation links on G1, Spot, and Husky. These are anatomical illustrations,
  not inferred accessibility, measured capabilities, or learned scores.
- Explanatory paragraphs follow their media and use restrained academic prose.
  Text wrapping is balanced on desktop and adapts naturally on small screens.

No new physics simulation or learning result is asserted by these visualizations.
The scene clips use 12-second resampled replays. Structure clips remove global
root translation for inspection. Mobile preserves each 2 by 2 grid and stacks
the three main components. Reduced motion disables autoplay and hover animation.

## Anonymity

PNG files are converted to sRGB pixels and saved without EXIF, ICC, XMP, or
text metadata. Videos are newly encoded as silent video-only MP4s without
source metadata. Viser records only generic node names and numeric geometry
and poses; source paths, experiment manifests, and checkpoints are not copied.
Third-party Viser license notices are retained in `assets/viser/LICENSE`.

```sh
python scripts/audit_anonymity.py
python scripts/audit_anonymity.py --term PRIVATE_IDENTIFIER
```

The audit scans tracked and nonignored files, including decompressed Viser
payloads, compressed viewer code, and packaged recordings. It checks MP4
track types, creation timestamps, and identifying metadata atoms. It does not certify visible text/logos in pixels; those must also be
reviewed. Git history and filesystem ownership remain local administrative
information, so publish only the website assets through an anonymous host,
not a personal repository URL or a repository archive containing `.git`.

Media preparation accepts local source paths as arguments; no private source
path is stored in the project:

```sh
python scripts/import_tldr_video.py /path/to/final-video.mp4
python scripts/prepare_media.py /path/to/video-archive
python scripts/export_scenes.py /path/to/archived-blender-arrays
python scripts/package_viewers.py
```

Run `python scripts/capture_previews.py` with the preview server running to
regenerate the silent video previews and PNG posters. This step uses
Playwright and its Chromium browser.

Preparation dependencies: Python, Pillow, imageio-ffmpeg, numpy, trimesh,
fast-simplification, viser. Dense meshes are reduced to 6,000 faces per part
for web playback; recorded poses are unchanged.
The audit also uses zstandard. The checked-in viewer and recordings are a
matched pair and should be updated together if the Viser version changes.

The page was independently implemented with layout inspiration from
[UMI on Legs](https://umi-on-legs.github.io/) and the local playback interaction
shown in [Robot whips](https://krishnasuresh.org/blog/2026/robot-whips/).
