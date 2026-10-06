# CLEAR upright-palm replanning recordings

The previous crouched recordings have been retired and removed from this page.
The upright bilateral palm controller uses 1.2 m boxes and 1.0 m contact
targets. Its initial comparison failed all three tasks. Recording is paused
until the motor passes physical qualification. Existing upright outputs are
incomplete diagnostic artifacts, not a completed comparison. Recorded physical
states are used for the robot, objects, Viser meshes and all MP4 views.

See [the diagnosis](UPRIGHT_DIAGNOSIS.md) and
[continuation notes](CONTINUATION.md) before starting another run.

This is a new physical controller variant. The three planning algorithms are retained. The planner was adapted
from the original checkpoint using tall-box geometric plan teachers from
separate development families. The comparison scenes are excluded from training.
Geometric teachers do not provide physical success labels. Previous controller certification and previous
video outcomes are not results for this variant.

Only the ordering and flow heads are adapted. The shared encoder and traversal
predictor remain frozen. The final checkpoint is fixed at 5,000 updates and is
shared by all three planning methods.
