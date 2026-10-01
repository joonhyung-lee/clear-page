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
compressed scene bytes. Scene downloads share in-flight requests, allow at most two concurrent loads, and retry transient failures up to twice with backoff. Incomplete responses are not cached as successful loads. A failed scene retains its preview and a retry button. Content revisions in asset URLs avoid stale browser media caches after refresh.

Previews prepare within 240 pixels of the viewport after a short dwell, with
at most two preparations at a time. Transient video failures receive up to two
retries. Videos pause outside the viewport and retain their loaded sources.
Automatic 3D scenes wait for a 550 ms dwell, start one at a time, and skip
queued work after the user scrolls away. A failed automatic scene delays the
remaining automatic queue for a minute to avoid amplifying server rate limits.
The poster or video stays visible until the native player reports readiness,
then dissolves into the interactive view. Offscreen native playback pauses
without discarding the camera or playhead. A visible player that loses its
WebGL context gets one local restart using already loaded assets.
Reduced motion disables automatic gallery preparation, playback, and transitions.

The packaged Viser client preserves mounted node references when a rewind
resends the same scene message. `scripts/patch_viser_rewind.py` applies this
small upstream compatibility fix and regenerates the runtime package.
`check_teaser_replay.py` checks repeated rewinds against both ghost poses and
all 148 observed meshes, including consecutive seeks to time zero.

Browser regressions, with the preview server running:

```sh
python scripts/check_scene_loading.py
python scripts/check_scroll_loading.py
```

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
  Five equally sized anchors and outlined lanes mark each path. Two corner ghosts
  switch to the next endpoint on both halves of a round trip. Colored outlined
  arrows above all four objects show illustrative force directions. Motion
  headings are sampled with a fixed seed and do not converge on a common center.
- Accessibility and Capability retain their explanatory videos and include
  buttons to inspect highlighted meshes. Capability highlights arm and
  gripper chains on G1 and Spot + arm. Accessibility highlights support and
  actuation links on G1, Spot, and Husky. These are anatomical illustrations,
  not inferred accessibility, measured capabilities, or learned scores.
- Explanatory paragraphs follow their media and use restrained academic prose.
  Text wrapping is balanced on desktop and adapts naturally on small screens.

These introductory illustrations do not assert a new learning result.
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

The main method example uses the original teaser's 10 by 17 metre course:
five boxes, two stair lanes, one slope, and the staggered upper maze. Native
geometry comes from its archived meshes. Four actual checkpoint draws select
no object interaction in this query. The ordering view displays that result.
The separate flow example conditions the original flow head on the designated
Object 0 reference interaction. That reference is supplied, not predicted by
OrderNet or claimed as a training sample. Waypoint anchors and two corner
ghosts show the generated midpoint and endpoint. The display interpolates the
30 saved Euler steps and then checks geometric clearance. None of these draws
produces a valid refined path, which is stated beside the viewer. These
unexecuted predictions are distinct from the teaser's physical demonstrations.

Experiments include 30 discrete grid replays, six ordered manipulation replays,
15 maze comparisons, and four long horizon examples. Physical replays retain
recorded state timing. Cases without an execution trajectory show a static
planning scene and are labeled accordingly. Long horizon examples are qualitative
transferred-plan demonstrations and are not presented as aggregate evaluation
trials. Source filenames, XML names, provenance, and checkpoint paths are not
included in the public replay payloads.

The pushing gallery contains one row of G1 and Spot + arm on each controller
side. The four clips retain their physical timing and exclude later navigation.
Spot + arm uses two new recordings of the original controllers on the same
box task. Their model geometry, mass, inertia, friction, seed and initial qpos
match. Both use 16 candidates and a one second horizon. The optimized package
uses LA-QDPP and the frozen arm controller settings; the naive package uses the
archived top-k settings. Both reported successful, collision-free interactions
without a fall. Video and Viser playback use the same complete visual meshes,
body poses and fixed camera. These qualitative runs are not paper benchmark
results or an isolated optimization ablation.

The separate G1 trajectory explanation shows development records with 24
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

Two dataset explorers show actual t-SNE projections of the inspected maze
checkpoint. The grounding explorer contains 82 training and 44 validation
mobility samples. The ordering explorer contains 34 training and 18 validation
plan samples, three evaluation replays, and twelve unexecuted scene queries.
The new queries vary passage layout, terrain, object mass, and embodiment.
Their paths are checkpoint predictions, and their execution-frame arrays are
empty. They carry no success or supervision labels. Hover or keyboard focus
selects the scene inputs and predictions. Recorded samples also provide the
measured robot and object rollout and supervision targets. File hashes match the
checkpoint training identity, and reference replay hashes match the training
certificates. Grounding features come from the query-conditioned classifier
input. Plan features average valid shared encoder tokens. These are projections
of one checkpoint, not a training progression or evidence of generalization.

The paired MPC surface display separates faint learned scores from two outlined
geometric palm neighborhoods. Each region is centered at a recorded palm
projected onto the box surface. Regions are clipped to observed surfaces.
They are not learned bimanual predictions or measured contact-force maps.

Below the physical replays, the optimization animation uses all 140 recorded
updates from the first object interaction for palm tracking and 260 for the
baseline. It draws the actual candidate palm displacements, costs, elite sets,
and applied candidate or elite-mean preview. Time waypoints show the 0.6 s
horizon and 0.1 s applied segment. Both panels share a displacement scale.
Stage pacing is explanatory because inference timings and intermediate
optimization iterations were not archived. Data packages load only near their
sections, and animations pause offscreen and honor reduced motion.

```sh
python scripts/check_research_visuals.py
python scripts/check_learning_explorers.py
```

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
fast-simplification, viser. Introductory previews reduce dense meshes to 6,000
faces per part. Learning checkpoints, the teaser method scene, and Spot + arm
pushing replays retain complete visual meshes. Recorded poses are unchanged.
The audit also uses zstandard. The checked-in viewer and recordings are a
matched pair and should be updated together if the Viser version changes.

The page was independently implemented with layout inspiration from
[UMI on Legs](https://umi-on-legs.github.io/) and the local playback interaction
shown in [Robot whips](https://krishnasuresh.org/blog/2026/robot-whips/).

### Independent low-level training records

The Spot tab uses an arm-free physical model with 12 actuators and a separate
48-input policy. `scripts/bare_spot.py` removes the entire arm subtree before
physics compilation. The Spot + arm tab uses its own 84-input policy and keeps
the arm in the physical model throughout training. Its arm stage changes arm
commands while training the leg policy to maintain balance. It is not a learned
manipulation policy. G1 has a new random-initialization lineage and a separately
selectable archived controller. Their replays, losses and evaluations are kept
separate.

New runs require an explicit `--body spot` or `--body spot_arm` when invoking
`scripts/train_spot_curriculum.py`. Spot uses the locomotion and terrain budgets;
Spot + arm additionally uses the arm adaptation budget. Private run directories
must remain outside this repository. The watcher also requires the matching
`--body`, publishes separate data files, and evaluates each body's own physics.
Curves contain actual logged values, numbered by completed PPO updates.
Initialization replays precede the first optimizer update and first action.

`scripts/train_progressive_policy.py` additionally supports G1 from random
initialization. `scripts/watch_progressive_evaluation.py` evaluates saved
milestones using the same fixed protocol and publishes partial measurements
as they become available. The new G1 panel refreshes these measurements while
visible. Pending checkpoints have no fabricated values.

The private armed-body trial changes only the torso reward weight to test
whether its stance reward contributes to stationary behavior.
`scripts/continue_armed_trial.py` advances it only after at least 8 of 12 fixed
flat-ground episodes reach the goal. A failed gate stops advancement and requests
review. This is a diagnostic experiment, not an established improvement, and
does not replace the original armed-body measurements.

### Fixed-protocol policy evaluation

The three main evaluation plots use separate deterministic checkpoint rollouts,
not PPO training losses. The suite has five shared terrain templates, four
difficulty levels and three initial condition seeds per tile: 60 episodes per
checkpoint. All checkpoints of a body receive identical initial states. The
archived G1 begins from a warm start. The new G1 and both new Spot lineages begin
from random policies in their distinct physical models.

The command is 0.5 m/s in world +X. Success requires 3 m of forward progress
with at most 0.75 m lateral displacement at the goal before a fall or 20 seconds.
A fall is tilt above 70 degrees. Episodes stop contributing at their first goal,
fall or timeout. Tracking is mean episode planar velocity RMSE, with one episode
standard deviation shaded. Success and fall rates use 95% Wilson intervals.
These are repeated evaluations of one training lineage, not multiple training
seeds. Low fall rate alone does not show successful locomotion. The armed body
uses its nominal arm pose for every checkpoint, so this is not an arm motion
robustness benchmark.

`scripts/evaluate_policy_progress.py` accepts a private manifest with per-body
`update`, `phase` and checkpoint `path` records. It writes individual episodes,
initial-state hashes and checkpoint provenance outside the repository.
`scripts/export_policy_evaluation.py` verifies these against the manifest and
publishes only numeric aggregates and protocol metadata. It rejects incomplete
evaluations unless explicitly passed `--allow-partial`.
`scripts/build_policy_evaluation.py` preserves the panel when the training
section is rebuilt. `scripts/check_policy_evaluation.py` checks exact measured
values, uncertainty bands, synchronized inspection and lineage separation.
The archived armed controller remains unmeasured rather than borrowing the
new run's results.

The teaser flow panel is an unsuccessful transfer diagnostic. Its supplied
three-object order is not an OrderNet prediction. The checkpoint selects no
objects on this query, and conditional raw paths fail to form a feasible plan.
Displayed lengths come directly from generated waypoints. The checkpoint's
noise standard deviation remains unchanged. Similar predictions are not
artificially varied or presented as successful physical executions.

### Research page layout

The pre-redesign site is preserved in the `snapshot-before-layout-20260930` tag.
The main navigation has three chapters: Method, Learning and Results. The logo
returns to the unchanged video hero. Paper and video dialogs provide local
previews and downloads. The code icon points to the anonymous repository.

`build_research_layout.py` moves existing players instead of duplicating them.
Training evidence and sample explorers live under Learning. Measured controller
evaluations share the right-hand metric area through an Evaluation tab.
Reference-conditioned teaser failures live under Results. The Method schematics
are explicitly illustrative, with hand-drawn paths rather than model outputs.

`build_paper_results.py` transcribes Tables I–IV from the anonymous manuscript.
It keeps aggregate protocols separate from individual and qualitative replays.
All methods remain accessible through each result section's toggle. The local
PDF retains anonymous manuscript content with document metadata removed.
The anonymity audit also scans extracted PDF text, metadata and links, using
PyMuPDF. Pixel-level visual review remains separate from the text audit.
`build_paper_preview.py` renders all eight PDF pages for the in-page preview,
with page navigation, zoom and accessible text. The original PDF remains the
download. `check_paper_results.py` compares every preview pixel and text page
against that PDF, as well as the 23 table rows.

Run the layout builders after rebuilding older page sections, then run
`build_asset_revisions.py`. `check_research_layout.py` verifies chapter order,
resource dialogs, measured metric values, viewer continuity, deep links and
mobile navigation.

The default low-level learning summary compares Initial, Intermediate and Final
snapshots from each body's own lineage. An unfinished run has no Final preview.
Selecting a snapshot opens the corresponding native replay in the existing
dashboard. Opening the dashboard alone does not start a 3D scene.
The detailed flow-matching equations live under Planner training. Result scene
selectors and longer explanations are available through Scene and protocol.

Both default Naive tiles now show fresh **native SUMO/CEM** recordings, using
the shared scene geometry with original robot dynamics, costs, command mapping,
optimizer defaults and native joint reset. No CLEAR Cartesian tracker, extra
joint smoothing, gain override or injected jitter is used. Native spline
interpolation and the low-level policy remain intact. G1 shows its complete
40 s attempt. The displayed Spot clip ends at 10.5 s, five seconds after its
base first tips beyond 90 degrees at 5.5 s. Its full 40 s source is preserved
privately. The displayed camera is enlarged by 1.25× and recentered on the
robot and object. G1 moves the box 0.594 m and
ends with 1.459 m goal error. The displayed Spot clip moves it 1.604 m and ends with 0.404 m error,
but crosses its standing-height threshold at 2.84 s and does not satisfy the
native success condition. Different starts and success rules preclude a speedup
claim. Measured EEF and object overlays do not supply targets to the controllers.

`record_native_baseline.py` uses the pinned SUMO runtime. The scene adapter
transfers geometry and placement only. The Spot adapter matches the source
model's box mass, inertia, floor and object contact parameters. Missing inherited
Spot terminal fields are supplied from JUDO defaults without changing reward.
`bake_native_baseline.py` checks source hashes, native body/joint/actuator
parameters, cost and CEM defaults, and evaluates exact FK from saved qpos.
The physical simulation clock drives planning. Offline rollout timeouts allow
complete forecasts; padded trajectories are rejected. Protocols are available
in `assets/native-baseline-protocol.json`. `check_native_baseline_replays.py`
checks the published measured sites and synchronized video, Ego and 3D timelines.

The earlier Cartesian MPC port remains archived as `mpc-spot-baseline.mp4`.
It is not an unmodified upstream SUMO recording. Its 22.54 s interaction moves
the object 1.93 m and ends with 0.077 m position error.

An audit of the available SUMO/JUDO source found that JUDO's arm-enabled task
resets with `ARM_UNSTOWED_POS` and directly exposes base and arm commands. The
SUMO box-push reward uses goal distance, gripper proximity and object velocity.
It does not include an explicit arm jerk penalty. The local Cartesian port has
additional tracking and command-shaping behavior, so neither a high-gain failure
nor injected delay is a substitute for an upstream baseline comparison. Absence
of a jerk penalty does not alone establish the amount of jitter in a rollout.

A separate **P gain ×3** experiment is retained. The six physical arm-joint PD
stiffness gains increase from 120 to
360, while derivative gains remain 2. Torque limits, legs, gripper, command
shaping and all original baseline cost weights are unchanged. Both the real
world and the 16 forecast worlds compile the same changed gains. This attempt
fails during contact preparation, with no object displacement or fall. The
24.70 s video shows the complete attempt, including approach and failed contact
preparation, rather than a pushing interval. The original recording remains
linked. Record with `--controller baseline --arm-kp-scale 3`, bake with
`--include-failed-attempt`, export as `mpc-spot-high-kp`, and publish with
`build_pushing_gallery.py --gain-diagnostic`. The recorder rejects combinations
with cost, shaping, timing or trust-region overrides.

A separate **Cost ablation** recording remains available.
Only the base-command magnitude penalty changes, from 2 to 0. Goal, contact,
lateral, orientation and terminal object-speed costs retain their original
weights. Native joint command shaping, control timing, trust region, physics,
initial scene and random seed are unchanged. There is no injected jitter or
sample-and-hold delay. The original baseline recording remains directly linked.
The recorded pushing interval lasts 25.58 s, moves the object 1.95 m, and ends
with 0.052 m of position error. The controller reports a successful interaction.

Record this variant with `record_spot_comparison.py --controller baseline
--control-cost-weight 0`, then bake and export it as `mpc-spot-cost-ablation`.
Use `build_pushing_gallery.py --cost-ablation` with the baked variant as the
baseline directory, followed by `build_continuous_layout.py` and
`build_asset_revisions.py`. The recorder rejects combinations with command
timing, shaping or trust-region overrides. The published numerical provenance
stores every original and effective cost weight. Metrics describe this one
physical episode, not benchmark performance or an optimization speedup.
`compare_spot_motion.py` keeps derivative-based motion statistics in private
output files. Earlier command-rate and variable-delay recordings are separate
diagnostics and are not the displayed native baseline recordings.

The G1 comparison shows the saved object reference lane, five anchors and two
corner-outline reference boxes at the middle and final positions. The native
baseline receives no additional Cartesian targets from these annotations.
`annotate_g1_reference.py` updates the native overlays and the baseline movie.
The optimized contact and Ego movies share 420 frames at 30 fps over 14 s.
`render_recorded_cameras.py` reconstructs both cameras in the native viewer,
using linear position interpolation and quaternion SLERP between archived poses.
This is display interpolation, not additional measured data or a physics rerun.
All original sampled body and object poses remain unchanged.

Ego movies now run continuously alongside the authoritative video or native
replay clock. Explicit seeks and large drift trigger seeks, while small drift
uses bounded playback-rate correction. Buffering, pause, playback speed,
viewport visibility and the external controller timeline preserve that clock.

Video checks can be repeated with:

```bash
node scripts/check_ego_sync.js
python scripts/audit_video_integrity.py
python scripts/check_goal_preview.py --check check_synced_camera_assets.py --check check_all_video_assets.py --check check_video_sync_browser.py
```

The file audit decodes every public MP4 and checks frame timestamps. The browser
audit decodes and seeks the beginning, middle and end of every movie, checks
126 sample intervals and compares matching native replay durations. The paired
player check exercises all four current controller movies, including enlarged
2× playback, native replay, seek, pause and viewport return. Static intervals
in failed recordings are retained; low motion is not treated as corrupt video.
