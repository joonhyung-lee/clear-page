"""Package available paper-map models that pass the identifier metadata scan.

Missing and flagged models remain explicit registry entries, never substituted.
Duplicate references share a single unchanged file. No checkpoint is unpickled.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--store", action="append", default=[], type=Path)
    p.add_argument("--destination", required=True, type=Path)
    args = p.parse_args()
    root = args.destination.resolve()
    inventory = json.loads((root / "docs/checkpoint_inventory.json").read_text())
    audit = json.loads((root / "docs/checkpoint_metadata_audit.json").read_text())["models"]
    manifest_path = root / "docs/artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    roots = {"source": args.source}
    roots.update({f"store-{i}": store for i, store in enumerate(args.store)})
    packaged, rows = {}, []
    for row in inventory["checkpoints"]:
        expected = row.get("sha256")
        entry = dict(manifest=row["manifest"], label=row["label"], sha256=expected,
                     status="missing", path=None)
        rows.append(entry)
        if row["status"] != "verified":
            continue
        if audit.get(expected, {}).get("status") != "identifier-scan-passed":
            entry["status"] = "metadata-review-required"
            continue
        if expected not in packaged:
            location = row["locations"][0]
            original = roots[location["origin"]] / location["path"]
            if sha(original) != expected:
                raise ValueError("Model differs from audited identity")
            label = row["label"]
            if label.startswith("assets/") and ".." not in Path(label).parts:
                relative = "runtime/" + label
            else:
                group = re.sub(r"[^A-Za-z0-9_-]", "_", row["manifest"].split("/")[2])
                name = re.sub(r"[^A-Za-z0-9_-]", "_", label)
                relative = f"runtime/assets/checkpoints/leap2026/{group}/{name}-{expected[:10]}{original.suffix}"
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if sha(destination) != expected:
                    raise ValueError("Refusing to replace a different packaged model")
            else:
                temporary = destination.with_suffix(destination.suffix + ".partial")
                shutil.copyfile(original, temporary)
                if sha(temporary) != expected:
                    raise ValueError("Model copy hash mismatch")
                temporary.replace(destination)
            manifest["files"][relative] = dict(source_origin=location["origin"],
                source_path=location["path"], source_sha256=expected, sha256=expected,
                bytes=destination.stat().st_size, changes=[])
            packaged[expected] = relative
        entry.update(status="packaged", path=packaged[expected])
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    (root / "docs/checkpoints.json").write_text(json.dumps(dict(
        schema="clear-standalone-checkpoints-v1", full_release_validated=False,
        unique_packaged_models=len(packaged), references=rows), indent=2) + "\n")
    print(json.dumps(dict(unique_packaged_models=len(packaged),
                          unresolved_references=sum(r["status"] != "packaged" for r in rows))))


if __name__ == "__main__":
    main()
