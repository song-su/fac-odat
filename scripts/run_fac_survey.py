#!/usr/bin/env python3
"""Shim — entry point has moved to survey/run_fac_survey.py. Edit defaults there."""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
runpy.run_path(
    str(Path(__file__).resolve().parent.parent / "survey" / "run_fac_survey.py"),
    run_name="__main__",
)
