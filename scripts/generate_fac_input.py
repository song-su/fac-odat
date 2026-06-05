#!/usr/bin/env python3
"""Shim — logic lives in survey.fac.input_gen."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from survey.config_loader import load_config
from survey.fac.input_gen import (  # noqa: F401 (re-exported)
    build_fac_script,
    _expand_template as expand_template,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.input)
    script = build_fac_script(config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(script, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
