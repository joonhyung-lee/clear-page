"""Compute a conservative local Python dependency closure for supported commands.

The report is a packaging plan, not proof that dynamic runtime inputs are complete.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
from pathlib import Path


ENTRYPOINTS = {
    "train-grid": "scripts.train",
    "evaluate-grid": "evaluation.exp1",
    "train-manipulation": "experiments.exp2.train_comparison",
    "refine-manipulation": "experiments.exp2.refine_flow_comparison",
    "evaluate-manipulation": "experiments.exp2.evaluate_comparison",
    "maze": "experiments.exp3.trajectory_v3.shared_cli",
    "evaluate-maze": "experiments.exp3.trajectory_v3.evaluate_frozen",
    "train-replanning": "experiments.exp4.sprint6h.train_adapt",
    "evaluate-replanning": "experiments.exp4.sprint6h.runner",
    "train-maze-v4": "experiments.exp5_maze_v4.train",
    "evaluate-maze-v4": "experiments.exp5_maze_v4.evaluate",
    "report-maze-v4": "experiments.exp5_maze_v4.report",
}
# These are loaded through the original dispatch registry and native subprocesses.
DYNAMIC = {
    "experiments.exp1.cli",
    "experiments.exp3.development.g1_metric_path",
    "experiments.exp3.development.spot_metric_path",
}
LOCAL = {"clear", "experiments", "baselines", "scripts", "evaluation", "viz", "visualization"}


def module_path(root, name):
    path = root.joinpath(*name.split("."))
    if path.with_suffix(".py").is_file():
        return path.with_suffix(".py")
    if (path / "__init__.py").is_file():
        return path / "__init__.py"
    return None


def dependencies(root, name):
    path = module_path(root, name)
    if path is None:
        return set(), set()
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    tree = ast.parse(path.read_text())
    names, literals = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                base = importlib.util.resolve_name("." * node.level + base, package)
            names.add(base)
            names.update(base + "." + alias.name for alias in node.names if alias.name != "*")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if value.split(".")[0] in LOCAL and module_path(root, value):
                names.add(value)
            if len(value) < 600 and "\n" not in value:
                literals.add(value)
    return names, literals


def select(root, extra=()):
    pending = set(ENTRYPOINTS.values()) | DYNAMIC | set(extra)
    chosen, external, missing, inputs = set(), set(), set(), set()
    while pending:
        name = pending.pop()
        if name in chosen:
            continue
        path = module_path(root, name)
        if path is None:
            missing.add(name)
            continue
        chosen.add(name)
        parts = name.split(".")
        pending.update(".".join(parts[:i]) for i in range(1, len(parts))
                       if module_path(root, ".".join(parts[:i])))
        deps, literals = dependencies(root, name)
        for dep in deps:
            if module_path(root, dep):
                pending.add(dep)
            elif dep.split(".")[0] not in LOCAL:
                external.add(dep.split(".")[0])
            # A from-import can be a symbol, so its absence is not an error.
        for value in literals:
            if value.startswith(("assets/", "asset/", "experiments/", "training/", "controllers/", "data/")):
                candidate = root / value
                if candidate.is_file():
                    inputs.add(value)
    return dict(schema="clear-standalone-selection-v1", entrypoints=ENTRYPOINTS,
                modules=sorted(chosen),
                files=sorted(str(module_path(root, name).relative_to(root)) for name in chosen),
                external_imports=sorted(external), missing_entrypoints=sorted(missing),
                literal_inputs=sorted(inputs),
                note="Dynamic imports, subprocess commands and native assets require runtime validation.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = select(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("missing_entrypoints", "external_imports")}))
    print(f"Selected {len(report['files'])} Python files")
    return bool(report["missing_entrypoints"])


if __name__ == "__main__":
    raise SystemExit(main())
