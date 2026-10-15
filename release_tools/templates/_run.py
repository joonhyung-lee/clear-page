"""Shared launcher for the numbered run scripts: forwards arguments to the experiment module."""
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(module, *prefix, argv=None):
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    sys.argv = [module, *prefix, *(sys.argv[1:] if argv is None else argv)]
    runpy.run_module(module, run_name='__main__', alter_sys=True)


def main(stages):
    """Dispatch `python run_XX_name.py <stage> [args]`; a stage is (module, *prefix) or a callable taking the args."""
    args = sys.argv[1:]
    if not args or args[0] not in stages:
        print(f'usage: {Path(sys.argv[0]).name} {{{"|".join(stages)}}} [args]   (args go to the stage; try <stage> --help)')
        sys.exit(2)
    stage = stages[args[0]]
    if callable(stage):
        stage(args[1:])
    else:
        run(*stage, argv=args[1:])
