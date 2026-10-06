# Standalone assembly tools

These tools operate on read-only research inputs and write a separate package.
They do not change research Git history, original manifests or checkpoint bytes.

```bash
python release_tools/build_standalone.py --source SOURCE --destination DESTINATION
python release_tools/pack_standalone_inputs.py --source SOURCE --destination DESTINATION
python release_tools/anonymize_standalone_inputs.py --destination DESTINATION
python release_tools/inventory_standalone.py --source SOURCE --store CHECKPOINT_STORE \
  --output DESTINATION/docs/checkpoint_inventory.json
python release_tools/audit_checkpoint_metadata.py --source SOURCE --store CHECKPOINT_STORE \
  --inventory DESTINATION/docs/checkpoint_inventory.json --private-term PRIVATE_IDENTIFIER \
  --output DESTINATION/docs/checkpoint_metadata_audit.json
python release_tools/pack_standalone_models.py --source SOURCE --store CHECKPOINT_STORE \
  --destination DESTINATION
python -m unittest discover -s release_tools -p 'test_*.py'
```

One-command local reassembly (use a new destination):

```bash
python release_tools/assemble_standalone.py --source SOURCE --store CHECKPOINT_STORE \
  --archive NATIVE_RECORDINGS --destination DESTINATION \
  --private-term PRIVATE_IDENTIFIER
```

Repeat `--private-term` for every identifier to check. Values are never saved in
the generated package. Repeat `--archive` for each recording archive to search.
Only the small probe-scene JSON inputs are copied, after checking original scene
hashes. The assembly also includes the original regression tests, robot meshes
and numeric manuscript-table evidence. It patches provenance logging to identify
the actual exported source instead of an unrelated parent Git repository.
Grid adaptation data and the 45 exact paper-model parents are assembled separately
from the revision's selected models. Parent copies preserve their original bytes.
Recorded revision commands and input hashes are indexed in `REVISION_RECIPES.md`;
the input check reads archive members without extracting them to the filesystem.

The command returns nonzero when model references remain
unresolved, even when the usable working distribution was assembled. No partial
package is marked publication-ready. Native runtime assembly and final release
verification are still pending.

The final tree audit is mandatory during assembly. It scans compressed checkpoint
metadata as well as supplied names. Current unmodified checkpoints include private
server paths, so assembly returns a failure status for anonymous publication even
when byte checks and model loading pass. It never edits those models automatically.

After explicit authorization to create metadata-only derivatives, create a NEW
candidate directory from the original assembly:

```bash
python release_tools/anonymize_standalone_checkpoints.py \
  --package ORIGINAL_ASSEMBLY --destination NEW_ANONYMOUS_CANDIDATE \
  --source SOURCE --store CHECKPOINT_STORE --private-term PRIVATE_IDENTIFIER
```

Use the research Python environment with torch installed. Inputs must be trusted,
hash-verified research checkpoints: this command loads them on CPU for exhaustive
field comparison. It does not use torch.save. It rewrites only approved path
strings in protocol-2 pickle metadata, preserves all other archive members and
checks every decoded tensor and numeric field. Unknown fields/formats fail closed.
Originals are never overwritten. Original/released hashes are both retained, and
local Grid contracts point to released bytes. Repeat every private-term option.
Run the complete tree auditor against the new candidate after verification.

For native source mismatches, recover exact pinned bytes into a separate local
review directory, supplying a known historical revision:

```bash
python release_tools/recover_native_pins.py --source SOURCE \
  --destination NEW_REVIEW_DIRECTORY --revision HISTORICAL_REVISION \
  --report NEW_ANONYMOUS_CANDIDATE/docs/native_source_recovery.json
```

Recovery does not assemble the complete native dependency closure or certify a
controller. The recovered original source has not passed an anonymity audit.
