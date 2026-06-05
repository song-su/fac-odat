"""Shim — configuration has moved to survey/configs/i7plus_fac.py."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from survey.configs.i7plus_fac import build_config, CONFIG  # noqa: F401
