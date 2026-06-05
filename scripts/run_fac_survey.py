#!/usr/bin/env python3
"""Run a FAC OptimizeRadial survey directly from a config file.

Each FAC trial is generated on-the-fly and run immediately — no separate
prepare step needed.

Typical usage
-------------
Local (serial):
  python3 scripts/run_fac_survey.py

Local (openmp, 12 parallel trials):
  python3 scripts/run_fac_survey.py openmp -n 12

Server with bsub (bsub allocates cores; script runs trials inside):
  bsub -n 12 python3 scripts/run_fac_survey.py openmp

Score existing results without re-running:
  python3 scripts/run_fac_survey.py --score-only
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import itertools
import math
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Dict, Iterator, List, Optional


# ---------------------------------------------------------------------------
# User parameters — edit this section for each survey
# ---------------------------------------------------------------------------

INPUT_FILE = Path("inputs/target_case_v4_I_survey.py")
OUTPUT_DIR  = Path("runs/i7_survey")

# Number of FAC trial processes to run in parallel.
# Set this to match the number of cores available on the machine / bsub slot.
JOBS = 1

# Default FAC parallelism mode (overridden by the positional CLI argument).
FAC_MODE = "serial"   # "serial" | "openmp" | "mpi"

# Limit the maximum number of templates in each OptimizeRadial combination.
# None = all combinations (2^N - 1 per grouping mode).
MAX_COMBINATION_SIZE: Optional[int] = None

# FAC group-by modes to enumerate.
GROUP_BY_MODES: Dict[str, Dict[str, str]] = {
    "nm": {"nl": "n", "mk": "m"},
    "lk": {"nl": "l", "mk": "k"},
}

# Early-stop threshold: stop as soon as any trial achieves RMS (Å) below this value.
# None = run all trials.
EARLY_STOP_RMS: Optional[float] = None


# ---------------------------------------------------------------------------
# Implementation — no user edits needed below
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from config_loader import load_config            # noqa: E402
from generate_fac_input import build_fac_script  # noqa: E402


def _optimize_template_ids(config: dict) -> List[str]:
    templates = config["configuration_space"]["templates"]["bound"]
    return [t["id"] for t in templates if t.get("optimize_radial", True)]


def _combinations_by_size(items: list, max_size: Optional[int] = None) -> Iterator:
    limit = len(items) if max_size is None else min(int(max_size), len(items))
    for size in range(1, limit + 1):
        yield from itertools.combinations(items, size)


def _apply_group_by(config: dict, mode_map: Dict[str, str]) -> dict:
    updated = deepcopy(config)
    for template in updated["configuration_space"]["templates"]["bound"]:
        active = template.get("active")
        if active in mode_map:
            template["group_by"] = mode_map[active]
    return updated


def _build_trial_config(config: dict, combo: tuple) -> dict:
    trial = deepcopy(config)
    trial.setdefault("radial_potential", {})["optimize_radial_groups"] = list(combo)
    return trial


def _strategy_id(index: int, combo: tuple) -> str:
    suffix = combo[0] if len(combo) == 1 else f"{len(combo)}groups"
    return f"opt_{index:04d}_{suffix}"


def enumerate_trials(
    config: dict,
    group_by_modes: Dict[str, Dict[str, str]],
    max_combination_size: Optional[int] = None,
) -> Iterator[dict]:
    template_ids = _optimize_template_ids(config)
    global_index = 0
    for mode, mode_map in group_by_modes.items():
        mode_config = _apply_group_by(config, mode_map)
        for strategy_index, combo in enumerate(
            _combinations_by_size(template_ids, max_combination_size), start=1
        ):
            global_index += 1
            sid = _strategy_id(strategy_index, combo)
            trial_id = f"trial_{global_index:06d}"
            trial_dir = Path("trials") / mode / f"{trial_id}_{sid}"
            yield {
                "mode": mode,
                "trial_id": trial_id,
                "strategy_id": sid,
                "combo_size": len(combo),
                "optimize_templates": ";".join(combo),
                "trial_dir": str(trial_dir),
                "config": _build_trial_config(mode_config, combo),
            }


def _run_one(
    trial: dict,
    output_dir: Path,
    fac_mode: str,
    python: str,
    force: bool,
) -> tuple:
    trial_dir = output_dir / trial["trial_dir"]
    trial_dir.mkdir(parents=True, exist_ok=True)
    done = trial_dir / "DONE"

    if done.exists() and not force:
        return trial, "skipped", 0

    (trial_dir / "trial.py").write_text(
        build_fac_script(trial["config"]), encoding="utf-8"
    )

    with (trial_dir / "fac.stdout").open("w", encoding="utf-8") as out, \
         (trial_dir / "fac.stderr").open("w", encoding="utf-8") as err:
        result = subprocess.run(
            [python, "trial.py", fac_mode],
            cwd=str(trial_dir),
            stdout=out,
            stderr=err,
        )

    if result.returncode == 0:
        done.touch()
        return trial, "ok", 0
    return trial, "failed", result.returncode


def _score_trial(trial_dir: Path) -> Optional[dict]:
    from known import find_known_candidates, KNOWN_PEAKS
    en_files = sorted(trial_dir.glob("*a.en"))
    tr_files = sorted(trial_dir.glob("*a.tr"))
    if not en_files or not tr_files:
        return None
    candidates = find_known_candidates(
        KNOWN_PEAKS, en_files[0], tr_files[0], top_n=1, use_paper_fac_target=True,
    )
    if not candidates:
        return None
    residuals = [c.residual_angstrom for c in candidates]
    rms = math.sqrt(sum(r * r for r in residuals) / len(residuals))
    return {
        "rms_A": rms,
        "mean_abs_A": sum(abs(r) for r in residuals) / len(residuals),
        "max_abs_A": max(abs(r) for r in residuals),
    }


def _write_scores(output_dir: Path, rows: List[dict]) -> Path:
    fieldnames = [
        "status", "rms_A", "mean_abs_A", "max_abs_A",
        "mode", "trial_id", "strategy_id", "combo_size",
        "optimize_templates", "trial_dir",
    ]
    path = output_dir / "known_scores.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a FAC OptimizeRadial survey from a config file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 run_fac_survey.py                   # uses defaults in script\n"
            "  python3 run_fac_survey.py openmp            # override mode\n"
            "  python3 run_fac_survey.py openmp -n 12     # mode + parallel jobs\n"
            "  bsub -n 12 python3 run_fac_survey.py openmp\n"
        ),
    )
    parser.add_argument(
        "mode", nargs="?", default=FAC_MODE,
        choices=("serial", "openmp", "mpi"),
        help=f"FAC parallelism mode (default: {FAC_MODE}).",
    )
    parser.add_argument(
        "-n", dest="jobs", type=int, default=JOBS,
        metavar="CORES",
        help=f"Parallel trial processes (default: {JOBS}).",
    )
    parser.add_argument(
        "--input", type=Path, default=INPUT_FILE,
        help=f"Survey config file (default: {INPUT_FILE}).",
    )
    parser.add_argument(
        "--output", type=Path, default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--max-combination-size", type=int, default=MAX_COMBINATION_SIZE,
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-run trials even if DONE already exists.",
    )
    parser.add_argument(
        "--score-only", action="store_true",
        help="Skip running FAC; score existing output and write known_scores.csv.",
    )
    parser.add_argument(
        "--early-stop-rms", type=float, default=EARLY_STOP_RMS,
        metavar="A",
        help="Stop as soon as any trial RMS (Å) falls below this value (default: run all).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.input)
    args.output.mkdir(parents=True, exist_ok=True)

    trials = list(enumerate_trials(config, GROUP_BY_MODES, args.max_combination_size))
    print(f"Survey: {len(trials)} trials  mode={args.mode}  jobs={args.jobs}  input={args.input}")

    if not args.score_only:
        failures = 0
        early_stop_hit = False
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = {
                pool.submit(_run_one, t, args.output, args.mode, sys.executable, args.force): t
                for t in trials
            }
            for i, future in enumerate(concurrent.futures.as_completed(futures), start=1):
                trial, status, code = future.result()
                if status == "failed":
                    failures += 1
                rms_str = ""
                if status == "ok" and args.early_stop_rms is not None:
                    scores = _score_trial(args.output / trial["trial_dir"])
                    if scores is not None:
                        rms_str = f"  RMS={scores['rms_A']:.4f} Å"
                        if scores["rms_A"] < args.early_stop_rms:
                            print(
                                f"[{i:06d}/{len(trials):06d}] {status:7s}  {trial['trial_dir']}{rms_str}",
                                flush=True,
                            )
                            print(
                                f"Early stop: RMS={scores['rms_A']:.4f} Å < threshold {args.early_stop_rms} Å"
                                f"  ({trial['trial_dir']})",
                                flush=True,
                            )
                            for f in futures:
                                f.cancel()
                            early_stop_hit = True
                            break
                print(f"[{i:06d}/{len(trials):06d}] {status:7s}  {trial['trial_dir']}{rms_str}", flush=True)
        if failures:
            print(f"WARNING: {failures} trial(s) failed", file=sys.stderr)
        if early_stop_hit:
            print("Survey stopped early due to RMS threshold.", flush=True)

    print("Scoring …")
    score_rows = []
    for trial in trials:
        scores = _score_trial(args.output / trial["trial_dir"])
        row = {k: v for k, v in trial.items() if k != "config"}
        if scores:
            row["status"] = "ok"
            row["rms_A"]      = f"{scores['rms_A']:.8g}"
            row["mean_abs_A"] = f"{scores['mean_abs_A']:.8g}"
            row["max_abs_A"]  = f"{scores['max_abs_A']:.8g}"
        else:
            row["status"] = "missing"
            row["rms_A"] = row["mean_abs_A"] = row["max_abs_A"] = ""
        score_rows.append(row)

    score_rows.sort(key=lambda r: float(r["rms_A"]) if r["rms_A"] else math.inf)
    scores_path = _write_scores(args.output, score_rows)

    print("\nTop results:")
    for row in score_rows[:20]:
        if row["rms_A"]:
            print(f"  RMS={row['rms_A']:>10s}  mode={row['mode']}  {row['optimize_templates']}")
    print(f"\nScores → {scores_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
