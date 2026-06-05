"""Shim — logic lives in survey.config_loader."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from survey.config_loader import load_config  # noqa: F401 (re-exported)
