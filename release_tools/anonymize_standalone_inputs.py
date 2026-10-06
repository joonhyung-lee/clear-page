"""Remove origin-only paths from copied JSON inputs, recording every changed field.

Checkpoint bytes, labels, numeric values and controller identities are untouched.
Unknown absolute paths fail closed for manual classification.
"""
import argparse
import hashlib
import json
from pathlib import Path


def transform(value, trail=(), changes=None):
    changes = [] if changes is None else changes
    if isinstance(value, dict):
        return {key: transform(child, (*trail, key), changes) for key, child in value.items()}
    if isinstance(value, list):
        return [transform(child, (*trail, str(i)), changes) for i, child in enumerate(value)]
    if not isinstance(value, str) or not value.startswith(("/home/", "/mnt/")):
        return value
    key = trail[-1] if trail else ""
    if key == "dependencies":
        replacement = "third_party/get_zero"
    elif trail[-3:] == ("model", "get_encoder", "repository"):
        replacement = "third_party/get_zero"
    elif trail[-3:] == ("model", "cdgs", "repository"):
        replacement = "third_party/CDGS_toydomain"
    elif key in {"recording", "path"}:
        replacement = "<ARCHIVE>/" + hashlib.sha256(value.encode()).hexdigest()[:24]
    else:
        raise ValueError("Unclassified absolute path at " + ".".join(trail))
    changes.append(".".join(trail))
    return replacement


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    root = args.destination.resolve()
    manifest_path = root / "docs/artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    count = 0
    pending = []
    for rel, record in manifest["files"].items():
        path = root / rel
        if path.suffix not in {".json", ".jsonl"}:
            continue
        source = path.read_text()
        changes = []
        if path.suffix == ".jsonl":
            rows = [transform(json.loads(line), (str(i),), changes)
                    for i, line in enumerate(source.splitlines()) if line.strip()]
            content = "\n".join(json.dumps(row) for row in rows) + "\n"
        else:
            value = transform(json.loads(source), changes=changes)
            content = json.dumps(value, indent=2) + "\n"
        if changes:
            pending.append((path, record, content, changes))
    for path, record, content, changes in pending:
        path.write_text(content)
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        record["bytes"] = path.stat().st_size
        record["changes"].append(dict(operation="origin-path anonymization", fields=changes))
        count += 1
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Anonymized provenance paths in {count} copied inputs")


if __name__ == "__main__":
    main()
