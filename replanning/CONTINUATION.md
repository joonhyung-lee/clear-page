# Continuing upright controller development

Read [UPRIGHT_DIAGNOSIS.md](UPRIGHT_DIAGNOSIS.md) first. No successful upright
motor or complete task result has been obtained. No training or recording job
is intentionally running. The page remains disabled, and the partial files
under `videos-upright/` are diagnostic recordings of failed attempts.

## Source and dependencies

The physics diagnostics used CLEAR source commit
`5049ec4f846de53fdba2a8c4d69c6e7222ee5f1b`, Python 3.11 and MuJoCo 3.11.
Obtain that source and its pretrained assets separately. This website repository
does not contain the complete simulator, raw physics runs or pretrained assets.
The source snapshot used a CPU compatibility change in mjlab's `sim_data.py`
to preserve the scalar type and trailing shape of empty Warp vector/matrix
arrays when converting to Torch. Check that conversion if reproducing on CPU.
The original source checkout was not modified.

The requested arm posture is the fourteen-joint `PALM_JOINTS` reference from
`clear.maze.fixed_palm`. Do not reinstate crouch offsets. Existing eight-joint
terrain-arm training does not cover this reference without adaptation.

## Planner artifact

The diagnostic tall-box planner was adapted for 5,000 updates at learning rate
0.001 using `scripts/adapt_replanning_tall_boxes.py`. Only ordering and flow
heads were trained. Shared encoding and traversal prediction stayed frozen.
Preserve the checkpoint's `exp4_decoder=axis_chord` metadata.

The final artifact was named `last-axis.pt`, with SHA256
`e857848f0cb389247ffe75b78d199a394a68393f1f612bd41e3dc17b4e1cbc1a`.
It is not included here. Transfer it separately or reproduce adaptation from
the original `assets/checkpoints/exp4/paper_axis.pt` checkpoint:

```bash
python scripts/adapt_replanning_tall_boxes.py --project <clear-source> --output <new-output> --steps 5000 --lr 0.001
```

The script now preserves decoder metadata. A regenerated artifact need not be
byte-identical. Verify its configuration and provenance before use.

## Next experiment

1. Adapt locomotion to the actual held-palm posture, including stop, reverse,
   posture transitions and physical contact loads.
2. Record empty-floor motor responses with `probe_upright_motor_stop.py` and
   qualify them with `check_upright_motor_response.py`. All five tested motor
   configurations failed; the sanitized measurements are committed in
   `diagnostics/upright-controller-audit.json`.
3. Test object stopping and settling with `probe_replanning_upright.py` before
   running the complete scene. Guide-only mode is a diagnostic, not full MPC.
4. `rebuild_replanning_upright.py` requires `--motor-validation` with a passing,
   matching motor and arm-reference report. Its task gate also requires a
   strict full-task success before publishing a rebuilt comparison.
   Supply every private author and institution identifier through repeated
   `--private-term` arguments for the publication audit. These terms are not
   stored in source files or reports.

Terminal direction and overshoot regression checks are in
`check_replanning_terminal_control.py`. These passing code checks do not prove
physical success. Raw experimental runs and model files stored outside this
repository are not transferred by a website Git push.
