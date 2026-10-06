"""Check resolved model metadata before anonymous packaging; never unpickle."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def scan(path, terms):
    patterns = [term.casefold().encode() for term in terms]
    hits = []
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                # Torch stores object metadata in data.pkl; tensor storage is
                # separate. Scan member names as well, without exposing matches.
                if any(term in name.casefold().encode() for term in patterns):
                    hits.append("archive-member-name")
                if name.endswith(".pkl"):
                    metadata = archive.read(name).lower()
                    if any(term in metadata for term in patterns):
                        hits.append("pickle-metadata")
        return sorted(set(hits))
    # Legacy torch and ONNX need a separate structural metadata review; a raw
    # identifier scan alone cannot certify either serialization format.
    return ["unsupported-serialization-review-required"]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--store", action="append", default=[], type=Path)
    p.add_argument("--inventory", required=True, type=Path)
    p.add_argument("--private-term", action="append", required=True)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    roots = {"source": args.source}
    roots.update({f"store-{i}": root for i, root in enumerate(args.store)})
    models = {}
    for row in json.loads(args.inventory.read_text())["checkpoints"]:
        if row["status"] != "verified" or row["sha256"] in models:
            continue
        location = row["locations"][0]
        path = roots[location["origin"]] / location["path"]
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != row["sha256"]:
            raise ValueError("Checkpoint changed since inventory")
        flags = scan(path, args.private_term)
        models[actual] = dict(flags=flags, status="review-required" if flags else "identifier-scan-passed")
    result = dict(schema="clear-checkpoint-metadata-audit-v1", models=models,
                  scope="archive names and pickle metadata identifier scan; no checkpoint loading",
                  full_anonymity_certified=False)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    flagged = sum(bool(r["flags"]) for r in models.values())
    print(json.dumps(dict(scanned=len(models), review_required=flagged)))
    return bool(flagged)


if __name__ == "__main__":
    raise SystemExit(main())
