#!/usr/bin/env python3
"""Run a FAC OptimizeRadial survey.

Edit the defaults below, then run:
  python3 scripts/run_fac_survey.py [mode] [-n CORES] [--early-stop-rms A]

All logic lives in survey.fac.runner.  To use a different ion, change
DEFAULT_ION to the module name under survey/ions/ (e.g. "ba10plus").
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from survey.fac.runner import make_parser, run_survey

# ---------------------------------------------------------------------------
# User defaults — edit here for each survey
# ---------------------------------------------------------------------------
DEFAULT_INPUT = "inputs/target_case_v4_I_survey.py"
DEFAULT_OUTPUT = "runs/i7_survey"
DEFAULT_JOBS = 1
DEFAULT_MODE = "serial"
DEFAULT_ION = "i7plus"
DEFAULT_EARLY_STOP_RMS = None   # float in Å, or None to run all trials
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = make_parser(
        default_input=DEFAULT_INPUT,
        default_output=DEFAULT_OUTPUT,
        default_jobs=DEFAULT_JOBS,
        default_mode=DEFAULT_MODE,
        default_early_stop_rms=DEFAULT_EARLY_STOP_RMS,
        default_ion=DEFAULT_ION,
    )
    args = parser.parse_args()
    raise SystemExit(run_survey(args))
