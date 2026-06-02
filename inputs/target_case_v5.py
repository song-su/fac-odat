#!/usr/bin/env python3
"""Compatibility entry point for the merged v4/v5 target input.

The potential-search logic now lives in target_case_v4.py through per
configuration annotations:

  required=True              -> include in every FAC calculation trial
  optimize_radial=True       -> allow this configuration in OptimizeRadial
  optimize_radial_base=True  -> use this configuration as a potential base

This file keeps the v5 run label and output directories while reusing the
merged v4 configuration logic.
"""

from importlib import import_module


_v4 = import_module("inputs.target_case_v4")


def build_config():
    old_run_naming = _v4.RUN_NAMING
    try:
        _v4.RUN_NAMING = dict(_v4.RUN_NAMING)
        _v4.RUN_NAMING["version"] = "v5"
        return _v4.build_config()
    finally:
        _v4.RUN_NAMING = old_run_naming


CONFIG = build_config()
