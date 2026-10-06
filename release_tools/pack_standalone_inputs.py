"""Copy explicit runtime inputs and record their unchanged source hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


CORE_INPUTS = [
    "clear/model/quantizers/LICENSE",
    "experiments/exp1/configs/main.yaml",
    "experiments/exp1/configs/debug.yaml",
    "experiments/exp1/data/ordering_main",
    "experiments/exp2/data/paper",
    "experiments/exp3/data/primary_prepared_local_edges",
    "training/configs/exp3",
    "training/exp4/config.json",
    "training/exp4/data",
]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    target = args.destination.resolve()
    path = target / "docs/artifact_manifest.json"
    manifest = json.loads(path.read_text())
    upstream = json.loads((source / "artifact_manifest.json").read_text())["files"]
    copies = []
    for relative in CORE_INPUTS:
        original = source / relative
        if not original.exists():
            raise FileNotFoundError(relative)
        files = [original] if original.is_file() else sorted(original.rglob("*"))
        for item in files:
            if not item.is_file() or "__pycache__" in item.parts:
                continue
            rel = item.relative_to(source).as_posix()
            sha = digest(item)
            if rel in upstream and sha != upstream[rel].get("sha256"):
                raise ValueError("Source input differs from release manifest: " + rel)
            copies.append((item, rel, sha))
    # Validate all sources before writing any destination files.
    for original, relative, sha in copies:
        dst = target / "runtime" / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and digest(dst) != sha:
            raise ValueError("Refusing to overwrite a different packaged input: " + relative)
        if not dst.exists():
            shutil.copyfile(original, dst)
        if digest(dst) != sha:
            raise ValueError("Copy hash differs: " + relative)
        manifest["files"]["runtime/" + relative] = dict(
            source_path=relative, source_sha256=sha, sha256=sha, bytes=dst.stat().st_size, changes=[])
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Verified and copied {len(copies)} inputs")


if __name__ == "__main__":
    main()
