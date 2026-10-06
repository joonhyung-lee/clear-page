# Upright controller diagnosis

The upright task is **not solved**. The original upright batch completed zero
of three tasks. Five subsequent motor configurations failed an empty-floor
forward, stop and reverse test. Failed experimental changes have not been
promoted into the default runtime or the public demonstration.

## What failed

Two distinct problems were found.

1. **Terminal contact-direction discontinuity.** The waypoint tracker accepts
   15 cm, while the final goal requires 8 cm. At 35.4 simulated seconds in the
   original first interaction, all waypoints were marked visited while the
   object was still 9.9 cm from its target. The controller changed its contact
   direction from `(0, -1)` to approximately `(-0.667, -0.745)`. After overshoot
   it requested the opposite face, and the ego contact detector rejected it
   with `not behind`.
2. **The motor does not reliably stop with the new held-arm posture.** This
   persists without an object, MPC or a planner. Therefore endpoint logic and
   MPC weights alone cannot fix the task. The existing motor and the new arm
   control/observation combination require adaptation and qualification.

The first object was meant to move 2.026 m. It entered a 5.3 cm neighborhood
of its goal transiently, but did not settle there. After failed reacquisition,
its longitudinal overshoot was 20.2 cm. A momentarily close object position,
physical bilateral contact, or an upright robot is not task completion.

## Empty-floor measurements

Each diagnostic used the real native robot, held forward palms and no crouch
offsets. Each command phase lasted three seconds. The table reports mean
measured forward body velocity over the final second of each phase. These are
single-seed diagnostics, not benchmark success rates.

| Configuration | Forward command +0.15 m/s | Stop command 0 | Reverse command -0.15 m/s | Result |
|---|---:|---:|---:|---|
| Original flat motor, relative arm observations | +0.215 | +0.192 | +0.737 | Drift and failed reverse tracking |
| Original flat motor, native arm observations | +0.090 | +0.151 | +0.070 | Falls, minimum root height 0.11 m |
| Original flat motor, relative observations and arm gravity support | +0.480 | +0.944 | +0.885 | Increased drift |
| Existing low-contact motor without crouch offsets | -0.026 | +0.033 | +0.052 | Falls, minimum root height 0.07 m |
| Existing low-contact motor, no crouch, arm gravity support | +0.017 | +0.045 | -0.002 | Falls, minimum root height 0.07 m |

The old low-contact runtime also supplied arm gravity compensation. Removing
that runtime removed the compensation along with crouch offsets. Restoring only
arm compensation was explicitly tested and **did not solve the problem**.
Likewise, stronger reverse braking did not fix the physical interaction.
Neither has been enabled in the default runtime.

The sanitized measurements and source-result checksums are in
[diagnostics/upright-controller-audit.json](diagnostics/upright-controller-audit.json).

## Changes retained

- Preserve the last planned push-side contact direction after the loose
  waypoint tracker completes. Intermediate corners still change direction.
- Re-observe the strict goal and settling state every native 0.1 s tick,
  rather than finishing a 0.5 s command chunk after entering the goal region.
- Return an explicit failure when a completed path overshoots by more than
  12 cm. Continuing a unilateral push cannot recover this endpoint.
- Record object linear and angular speeds in contact observations.
- Reject expensive comparison rebuilding unless the motor has passed measured
  forward, stop and reverse qualification in the same arm posture.
- Do not publish a new comparison batch unless at least one method completes
  the full physical task under the strict audit.

These fixes do not qualify the motor or establish improved task completion.
The default runtime is explicitly marked unqualified. All success criteria
remain unchanged: 8 cm, 0.12 rad, object linear speed at most 0.05 m/s and
angular speed at most 0.1 rad/s for 0.3 s, plus measured bilateral contact.

## Reproduction

```bash
python scripts/check_replanning_terminal_control.py --project <pinned-source> --upstream
python scripts/check_replanning_terminal_control.py --project <pinned-source>
```

The first command reproduces the original contact-direction regression and
fails. The second passes the terminal and corner cases and the overshoot guard.

`scripts/probe_upright_motor_stop.py` records actual empty-floor responses.
`scripts/check_upright_motor_response.py --result <result.json> --output <validation.json>`
returns a nonzero status for each failed configuration above.

`scripts/probe_replanning_upright.py` tests an actual object interaction.
`--guide-only --worlds 3` is a labeled diagnostic isolation of the geometric
base/palm guide. It must not be described as the full MPC comparison.

## Work required before another task recording

Adapt a locomotion policy to the actual forward-palm arm targets and their
actuator behavior. Training must include zero velocity, reverse velocity,
posture transitions and contact loads. The existing terrain-arm task is a
starting point, but its eight-joint arm range does not cover the requested
fourteen-joint palm/wrist reference as-is. Preserve the measured 99-channel
motor observation contract and the no-crouch requirement.

Qualify that policy on empty-floor commands first, then on box stopping in
multiple directions, and finally on the unchanged complete planning scene.
A new trained policy is not yet available. This session performed CPU physics
validation; CUDA reported no available devices. No successful new motor
training run or full-task result is claimed.
