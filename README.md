# CLEAR — anonymous local preview

```sh
python scripts/serve.py
```

Open **http://localhost:8765**. The server binds to loopback and serves only
`index.html` and `assets/`; repository metadata and scripts are not served.
No build step, remote font, analytics service, or live Viser server is required.
Lazy script packages embed recordings directly into the viewer so anonymous
hosting sandbox policies do not require a cross-origin recording fetch.
Packed data uses hexadecimal text to prevent name redaction from corrupting
compressed scene bytes. Scene downloads share in-flight requests, allow at most two concurrent loads, and retry transient failures up to twice with backoff. Incomplete responses are not cached as successful loads. A failed scene retains its preview and a retry button. Offscreen videos defer loading, and reopening the same hover preview reuses its loaded source. Content revisions in asset URLs avoid stale browser media caches after refresh.

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
  at 42 percent opacity. Nodes follow link frames, with the Husky base graph displayed at the chassis
  center rather than its ground-referenced source origin. Wheel circles and asymmetric sidewall markers make rolling visible.
  Wheel angles are reconstructed from signed travel and wheel radius. Edges follow the
  model parent hierarchy, exposing the articulated structure through the shell.
- Scene has four clips for stairs, a stepped bridge, a slope, and a mixed
  terrain maze. Stairs, slope, and maze use recorded poses. The bridge is an
  illustrative two-block and plank construction with a retargeted walking gait. The mixed scene combines three
  independent trajectories on a normalized playback timeline.
- Hovering a tile enlarges its preview at the center of its own grid. Clicking
  or pressing Enter also opens it. Play in 3D loads the corresponding local
  Viser recording. Escape or the close button dismisses the expanded preview.
- Object states shows four pastel objects with overlapping illustrative motions.
  Five anchors mark each path. Two fixed corner outlines disappear when their
  respective objects reach the marked pose and return on the next approach.
- Accessibility and Capability retain their explanatory videos and include
  buttons to inspect highlighted meshes. Capability highlights arm and
  gripper chains on G1 and Spot + arm. Accessibility highlights support and
  actuation links on G1, Spot, and Husky. These are anatomical illustrations,
  not inferred accessibility, measured capabilities, or learned scores.
- Explanatory paragraphs follow their media and use restrained academic prose.
  Text wrapping is balanced on desktop and adapts naturally on small screens.

No new physics simulation or learning result is asserted by these visualizations.
The scene clips use 12-second resampled replays. Structure clips use a root-following coordinate frame and translate the world
grid to retain the visual displacement of the recorded motion. Mobile preserves each 2 by 2 grid and stacks
the three main components. Reduced motion disables autoplay and hover animation.

## Method and experiment replays

The Method section keeps equations centered and secondary derivations folded.
A shared overview preview enlarges the selected component without overlapping
hover windows. Flow dots trace the planning dataflow and respect reduced motion.
The embodiment gallery preserves each walking player's camera and playback time
when Structure, Traversability, or Manipulation affordance is selected. These
modes change only mesh colors and explanatory geometric regions.

Maze ordering combines learned distributions and sampled priorities in one
native viewer, with a short explanation of how reference plans provide training targets. A recorded plan
illustrates selection and pairwise rank targets without being presented as
training-set evidence or an optimization history. Learned Gaussian curves and
saved draws share a priority axis inside the scene. Four saved random draws feed
rank causal motion generation. Generation automatically plays from normalized
time zero to one, with pause and replay controls. Four black outlined anchors
mark each path above the object tops. Exactly two box ghosts show targets.
The integrated generation display includes geometry refinement that checks entire path segments against walls,
other objects, and the observed robot footprint. It is a separate geometric
visualization, not a learned collision guarantee or a dynamics simulation.

Experiments include 30 discrete grid replays, six ordered manipulation replays,
15 maze comparisons, and four long horizon examples. Physical replays retain
recorded state timing. Cases without an execution trajectory show a static
planning scene and are labeled accordingly. Long horizon examples are qualitative
transferred-plan demonstrations and are not presented as aggregate evaluation
trials. Source filenames, XML names, provenance, and checkpoint paths are not
included in the public replay payloads.

The MPC comparison shows physically executed development records with 24
search candidates and a 0.6 second rollout horizon. Ours uses Cartesian palm
tracking and LA-QDPP. The baseline uses a direct joint CEM port and executes
its elite mean, with an extra rollout showing that mean. They share the scene
and planning seed, but change multiple controller components. The comparison
does not isolate the effect of candidate selection.

Each panel has five small black outlined reference markers, a wider lane, and follows its own recorded
time. Green denotes ours and red denotes the baseline. The ego RGB inset follows
the native player's time, including scrubbing and looping. Contact scores are
recomputed from the actual learned checkpoint on segmented ego RGB-D rendered
from replayed physical states. The field is normalized per frame and appears
only on visible object surfaces. Continuous RGBA textures follow the actual box
faces, with segmentation and depth clipping. Learned point scores are smoothed
for display using spatial interpolation. These are recomputed displays, not archived
controller telemetry or aggregate benchmark results.

Math rendering is self hosted in `assets/katex`, with its upstream license retained.

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

Run `python scripts/capture_smooth_previews.py --scenes structure-g1 structure-spot structure-spot_arm structure-husky objects scene-stairs scene-steps scene-slope scene-maze` with the preview server running to
regenerate the silent video previews and PNG posters. This step uses
Playwright and its Chromium browser. Run `python scripts/build_asset_revisions.py`
after finishing asset generation.

Preparation dependencies: Python, Pillow, imageio-ffmpeg, numpy, trimesh,
fast-simplification, viser. Dense meshes are reduced to 6,000 faces per part
for web playback; recorded poses are unchanged.
The audit also uses zstandard. The checked-in viewer and recordings are a
matched pair and should be updated together if the Viser version changes.

The page was independently implemented with layout inspiration from
[UMI on Legs](https://umi-on-legs.github.io/) and the local playback interaction
shown in [Robot whips](https://krishnasuresh.org/blog/2026/robot-whips/).
