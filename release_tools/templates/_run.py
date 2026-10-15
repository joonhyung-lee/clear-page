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
