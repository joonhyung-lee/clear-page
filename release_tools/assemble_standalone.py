"""Rebuild the standalone working distribution from explicit research inputs.

This is a local export, not a publication command. Unresolved model references
produce a nonzero exit status even when the usable working tree was assembled.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

TOOLS = Path(__file__).resolve().parent
TEMPLATE = TOOLS.parent / "clear-standalone"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--store", action="append", type=Path, default=[])
    p.add_argument("--destination", type=Path, required=True)
    p.add_argument("--private-term", action="append", required=True)
    p.add_argument("--archive", action="append", required=True, type=Path,
                   help="Original native recording tree used to recover small probe-scene inputs")
    args = p.parse_args()
    destination = args.destination.resolve()
    if destination.exists():
        raise ValueError("Use a new destination; existing work is never overwritten")
    destination.mkdir(parents=True)
    (destination / "docs").mkdir()
    for name in ("run.py", "pyproject.toml", ".gitignore", "requirements-core-linux-py311.txt"):
        shutil.copyfile(TEMPLATE / name, destination / name)
    shutil.copytree(TEMPLATE / "tools", destination / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(TEMPLATE / "docs/TRAINING.md", destination / "docs/TRAINING.md")
    def run(script, arguments, allow_incomplete=False):
        result = subprocess.run([sys.executable, str(TOOLS / script), *map(str, arguments)])
        if result.returncode and not (allow_incomplete and result.returncode == 1):
            raise RuntimeError(script + " failed")
    common = ["--source", args.source, "--destination", destination]
    run("build_standalone.py", common)
    run("patch_standalone_provenance.py", ["--destination", destination])
    run("patch_standalone_v4.py", ["--destination", destination])
    run("pack_standalone_inputs.py", common)
    run("anonymize_standalone_inputs.py", ["--destination", destination])
    archives = [part for archive in args.archive for part in ("--archive", archive)]
    run("pack_probe_scenes.py", [*common, *archives])
    stores = [part for store in args.store for part in ("--store", store)]
    inventory = destination / "docs/checkpoint_inventory.json"
    run("inventory_standalone.py", ["--source", args.source, *stores, "--output", inventory], True)
    terms = [part for term in args.private_term for part in ("--private-term", term)]
    run("audit_checkpoint_metadata.py", ["--source", args.source, *stores,
        "--inventory", inventory, *terms, "--output", destination / "docs/checkpoint_metadata_audit.json"], True)
    run("pack_standalone_models.py", [*common, *stores])
    run("pack_standalone_tests.py", common)
    run("pack_native_assets.py", common)
    run("pack_paper_evidence.py", [*common, *terms])
    run("pack_grid_training.py", [*common, *terms])
    run("pack_grid_parents.py", [*common, *terms])
    run("pack_v4_inputs.py", [*common, *terms])
    run("pack_grid_evaluation.py", common)
    run("pack_revision_recipes.py", [*common, *terms])
    registry = json.loads((destination / "docs/checkpoints.json").read_text())
    unresolved = sum(row["status"] != "packaged" for row in registry["references"])
    status = dict(schema="clear-standalone-assembly-v1", assembled=True,
                  full_release_validated=False, unresolved_references=unresolved,
                  unique_packaged_models=registry["unique_packaged_models"],
                  native_runtime_assembled=False, clean_install_verified=False)
    (destination / "docs/assembly.json").write_text(json.dumps(status, indent=2) + "\n")
    (destination / "README.md").write_text(
        "# CLEAR standalone\n\nLocal working distribution. Full release validation is pending.\n\n"
        "Use `python run.py --help` for the common command interface and "
        "`python tools/verify.py --smoke` for the CPU planning check.\n\n"
        "Training commands: [docs/TRAINING.md](docs/TRAINING.md). "
        "Model availability: [docs/checkpoints.json](docs/checkpoints.json). "
        "Assembly status: [docs/assembly.json](docs/assembly.json).\n")
    audit_report = destination / 'docs/tree_audit.json'
    result = subprocess.run([sys.executable, str(destination / 'tools/audit_release.py'),
                             *terms, '--report', str(audit_report)])
    if result.returncode not in (0, 1):
        raise RuntimeError('Standalone tree audit could not complete')
    audit = json.loads(audit_report.read_text())
    status['tree_audit_status'] = audit['status']
    status['publication_review_findings'] = len(audit['findings'])
    (destination / "docs/assembly.json").write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps(status))
    return int(unresolved > 0 or audit['status'] != 'passed')


if __name__ == "__main__":
    raise SystemExit(main())
