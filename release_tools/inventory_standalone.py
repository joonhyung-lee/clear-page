"""Resolve paper checkpoint identities without changing the research checkout.

No torch deserialization, checkpoint rewriting, Git mutation or network access.
Store manifests are lookup hints only: every resolved file is hashed again.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess

HASH = re.compile(r"(?:sha256:)?([0-9a-f]{64})(?![0-9a-f])")
REFERENCE = re.compile(r"(?:outputs/leap2026|evaluation/evidence)/[a-zA-Z0-9_./+\-]+")


def references_in(text):
    return {value.rstrip(".") for value in REFERENCE.findall(text)
            if Path(value.rstrip(".")).suffix in
            {".json", ".jsonl", ".csv", ".md", ".tex", ".pdf", ".png", ".pt", ".onnx", ".npz"}}


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative_reference(value):
    """Strip only a known repository root, not arbitrary path components."""
    value = str(value).strip().strip("`\"'")
    if value.startswith("/"):
        for root in ("/outputs/", "/assets/", "/experiments/", "/data/", "/training/"):
            if root in value:
                relative = root[1:] + value.split(root, 1)[1]
                return relative if ".." not in Path(relative).parts else None
        return None
    parts = Path(value).parts
    return value if parts and ".." not in parts else None


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def inventory(source, stores=()):
    source = source.resolve()
    paper_map = source / "outputs/leap2026/PAPER_MAP.md"
    references = sorted(references_in(paper_map.read_text()))
    # Follow cited JSON/Markdown records, including preregistrations. Parent
    # manifests are not assumed to summarize every child's checkpoint.
    pending = list(references)
    visited, manifests, missing_evidence = set(), {}, set()
    while pending:
        relative = pending.pop()
        if relative in visited:
            continue
        visited.add(relative)
        path = source / relative
        if not path.is_file():
            missing_evidence.add(relative)
            continue
        if path.suffix not in {".json", ".md"}:
            continue
        content = path.read_text()
        if path.suffix == ".json":
            value = json.loads(content)
            for string in strings(value):
                pending.extend(references_in(string))
            if isinstance(value, dict) and isinstance(value.get("checkpoints"), dict):
                manifests[relative] = value
        else:
            pending.extend(references_in(content))

    candidates = defaultdict(list)
    indexes = [(source, "source", source / "artifact_manifest.json")]
    indexes.extend((store, f"store-{i}", store / "manifest.json") for i, store in enumerate(stores))
    for root, origin, index in indexes:
        if not index.is_file():
            continue
        for relative, entry in json.loads(index.read_text()).get("files", {}).items():
            if Path(relative).suffix not in {".pt", ".onnx"} or not isinstance(entry, dict):
                continue
            match = HASH.fullmatch(entry.get("sha256", ""))
            if match:
                candidates[match[1]].append((root / relative, origin, relative))

    rows, cache, mismatches = [], {}, []
    for relative, manifest in sorted(manifests.items()):
        for label, entry in manifest["checkpoints"].items():
            match = HASH.search(str(entry))
            if not match:
                rows.append(dict(manifest=relative, label=relative_reference(label) or "external-reference",
                                 status="unresolved-hash"))
                continue
            expected = match[1]
            options = []
            for value in [label, *strings(entry)]:
                for token in str(value).split():
                    ref = relative_reference(token)
                    if ref and Path(ref).suffix in {".pt", ".onnx"}:
                        options.append((source / ref, "source", ref))
            options.extend(candidates[expected])
            locations = []
            checked = set()
            for path, origin, ref in options:
                if path in checked or not path.is_file():
                    continue
                checked.add(path)
                if path not in cache:
                    cache[path] = sha256(path)
                actual = cache[path]
                if actual != expected:
                    mismatches.append(dict(manifest=relative, origin=origin, path=ref,
                                           expected=expected, actual=actual))
                else:
                    locations.append(dict(origin=origin, path=ref, bytes=path.stat().st_size))
            rows.append(dict(manifest=relative, label=relative_reference(label) or "external-reference",
                             sha256=expected, status="verified" if locations else "missing",
                             locations=locations))
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    except subprocess.CalledProcessError:
        revision = None
    return dict(schema="clear-standalone-inventory-v1", source_revision=revision,
                paper_map_sha256=sha256(paper_map), scope="checkpoint records reachable from the local PAPER_MAP",
                latest_handoff_revision_verified=False,
                counts=dict(manifests=len(manifests), records=len(rows),
                            verified=sum(r["status"] == "verified" for r in rows),
                            unique_verified_hashes=len({r["sha256"] for r in rows if r["status"] == "verified"})),
                missing_evidence=sorted(missing_evidence), hash_mismatches=mismatches,
                missing_direct_references=sorted(set(references) & missing_evidence),
                checkpoints=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--store", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = inventory(args.source, args.store)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["counts"]))
    print(f"Missing evidence: {len(report['missing_evidence'])}; hash mismatches: {len(report['hash_mismatches'])}")
    return int(bool(report["hash_mismatches"]) or any(r["status"] != "verified" for r in report["checkpoints"]))


if __name__ == "__main__":
    raise SystemExit(main())
