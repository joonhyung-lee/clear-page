"""Build the selected source tree; leave source research files untouched."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from select_standalone import select


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build(source, destination):
    source, destination = source.resolve(), destination.resolve()
    if destination == source or source.is_relative_to(destination):
        raise ValueError("Destination must not contain the source checkout")
    selection = select(source)
    runtime = destination / "runtime"
    if runtime.exists():
        raise ValueError("Runtime already exists; use a new destination to avoid stale files")
    records = {}
    for relative in [*selection["files"], "LICENSE", "LICENSING.md"]:
        original = source / relative
        target = runtime / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        changes = []
        if relative == "clear/model/quantizers/__init__.py":
            # Remove the private clone path in a documentation comment only.
            lines = target.read_text().splitlines(keepends=True)
            lines = ["(MIT, see LICENSE; vendored quantizer implementation).\n"
                     if "upstream commit of the local clone at" in line else line for line in lines]
            target.write_text("".join(lines))
            changes.append("Removed a private clone path from the module docstring")
        records["runtime/" + relative] = dict(source_path=relative, source_sha256=digest(original),
                                             sha256=digest(target), bytes=target.stat().st_size,
                                             changes=changes)
    (destination / "docs").mkdir(exist_ok=True)
    (destination / "docs/source_selection.json").write_text(json.dumps(selection, indent=2) + "\n")
    (destination / "docs/source_manifest.json").write_text(json.dumps(dict(
        schema="clear-standalone-source-v1", files=records), indent=2) + "\n")
    shutil.copyfile(source / "LICENSE", destination / "LICENSE")
    artifacts = {}
    for relative in ("assets/checkpoints/exp3/paper/seed0/clear.pt",
                     "experiments/exp3/data/example_g1.json"):
        original, target = source / relative, runtime / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        changes = []
        if target.suffix == ".json":
            value = json.loads(target.read_text())
            if value.get("teacher", {}).get("recording"):
                # This is provenance, not a model input or runtime dependency.
                value["teacher"]["recording"] = "<ARCHIVE>/reference-recording"
                target.write_text(json.dumps(value, indent=2) + "\n")
                changes.append("Anonymized the teacher recording origin; model inputs unchanged")
        artifacts["runtime/" + relative] = dict(source_path=relative, source_sha256=digest(original),
                                               sha256=digest(target), bytes=target.stat().st_size,
                                               changes=changes)
    (destination / "docs/artifact_manifest.json").write_text(json.dumps(dict(
        schema="clear-standalone-artifacts-v1", files=artifacts), indent=2) + "\n")
    print(f"Copied {len(records)} files; {sum(r['bytes'] for r in records.values()):,} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    build(args.source, args.destination)
