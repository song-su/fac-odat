#!/usr/bin/env python3
"""Backward-compatible shim — all logic now lives in the survey package.

    from scripts.known import find_known_candidates, KNOWN_PEAKS
is equivalent to:
    from survey.scorer import find_known_candidates
    from survey.ions.i7plus import KNOWN_PEAKS, BASE_CONFIG
"""
import argparse
import sys
from pathlib import Path

# Make the survey package importable when this script is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from survey.peaks import KnownPeak, derive_transition_label, HC_EV_ANGSTROM  # noqa: F401
from survey.fac.parser import Level, Transition, parse_en_table, parse_tr_table  # noqa: F401
from survey.scorer import (  # noqa: F401
    Candidate, find_candidates, find_known_candidates, format_candidates,
)
from survey.ions.i7plus import KNOWN_PEAKS, BASE_CONFIG  # noqa: F401

# Legacy alias
KNOWN_I7_PEAKS = KNOWN_PEAKS


def find_known_i7_candidates(en_path, tr_path, top_n=5, use_paper_fac_target=False):
    return find_known_candidates(
        KNOWN_PEAKS, en_path, tr_path, top_n, use_paper_fac_target, BASE_CONFIG
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List known-transition candidates by configuration family."
    )
    parser.add_argument("--en", type=Path, required=True)
    parser.add_argument("--tr", type=Path, required=True)
    parser.add_argument("--top", type=int, default=4)
    parser.add_argument(
        "--target", choices=("experiment", "paper-fac"), default="experiment",
    )
    args = parser.parse_args()
    candidates = find_known_candidates(
        KNOWN_PEAKS,
        en_path=args.en,
        tr_path=args.tr,
        top_n=args.top,
        use_paper_fac_target=args.target == "paper-fac",
        base_config=BASE_CONFIG,
    )
    print(format_candidates(candidates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
