"""FAC survey runner: enumerate trials, execute FAC, score, write results.

Entry points
------------
make_parser(...)  : build an argparse.ArgumentParser with survey defaults
run_survey(args, known_peaks, base_config)  : run the full survey
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import importlib
import itertools
import math
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from survey.config_loader import load_config
from survey.fac.input_gen import build_fac_script
from survey.scorer import find_known_candidates, rms_angstrom


# ---------------------------------------------------------------------------
# Trial enumeration
# ---------------------------------------------------------------------------

def _optimize_template_ids(config: dict) -> List[str]:
    templates = config["configuration_space"]["templates"]["bound"]
    return [t["id"] for t in templates if t.get("optimize_radial", True)]


def _combinations_iter(items: list, max_size: Optional[int] = None) -> Iterator:
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
) -> List[dict]:
    template_ids = _optimize_template_ids(config)
    trials = []
    global_index = 0
    for mode, mode_map in group_by_modes.items():
        mode_config = _apply_group_by(config, mode_map)
        for strategy_index, combo in enumerate(
            _combinations_iter(template_ids, max_combination_size), start=1
        ):
            global_index += 1
            sid = _strategy_id(strategy_index, combo)
            trial_id = f"trial_{global_index:06d}"
            trial_dir = Path("trials") / mode / f"{trial_id}_{sid}"
            trials.append({
                "mode": mode,
                "trial_id": trial_id,
                "strategy_id": sid,
                "combo_size": len(combo),
                "optimize_templates": ";".join(combo),
                "trial_dir": str(trial_dir),
                "config": _build_trial_config(mode_config, combo),
            })
    return trials


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _run_one(
    trial: dict,
    output_dir: Path,
    fac_mode: str,
    python: str,
    force: bool,
) -> Tuple[dict, str, int]:
    trial_dir = output_dir / trial["trial_dir"]
    trial_dir.mkdir(parents=True, exist_ok=True)
    done = trial_dir / "DONE"

    if done.exists() and not force:
        return trial, "skipped", 0

    (trial_dir / "trial.py").write_text(
        build_fac_script(trial["config"]), encoding="utf-8"
    )

    with (trial_dir / "fac.stdout").open("w") as out, \
         (trial_dir / "fac.stderr").open("w") as err:
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


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_trial(
    trial_dir: Path,
    known_peaks,
    base_config=None,
) -> Optional[dict]:
    en_files = sorted(trial_dir.glob("*a.en"))
    tr_files = sorted(trial_dir.glob("*a.tr"))
    if not en_files or not tr_files:
        return None
    candidates = find_known_candidates(
        known_peaks,
        en_files[0],
        tr_files[0],
        top_n=1,
        use_paper_fac_target=True,
        base_config=base_config,
    )
    if not candidates:
        return None
    rms = rms_angstrom(candidates)
    if rms is None:
        return None
    residuals = [c.residual_angstrom for c in candidates]
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
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    return path


# ---------------------------------------------------------------------------
# Ion loading
# ---------------------------------------------------------------------------

def _load_ion(ion_name: str):
    """Import survey.ions.<ion_name> and return (KNOWN_PEAKS, BASE_CONFIG)."""
    try:
        mod = importlib.import_module(f"survey.ions.{ion_name}")
    except ModuleNotFoundError:
        raise SystemExit(
            f"Ion module 'survey.ions.{ion_name}' not found. "
            f"Create survey/ions/{ion_name}.py with KNOWN_PEAKS and BASE_CONFIG."
        )
    known_peaks = getattr(mod, "KNOWN_PEAKS", None)
    base_config = getattr(mod, "BASE_CONFIG", None)
    if known_peaks is None:
        raise SystemExit(f"survey.ions.{ion_name} must define KNOWN_PEAKS")
    return known_peaks, base_config


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_DEFAULT_GROUP_BY_MODES = {
    "nm": {"nl": "n", "mk": "m"},
    "lk": {"nl": "l", "mk": "k"},
}


def make_parser(
    default_input: str = "inputs/survey.py",
    default_output: str = "runs/survey",
    default_jobs: int = 1,
    default_mode: str = "serial",
    default_early_stop_rms: Optional[float] = None,
    default_ion: str = "i7plus",
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a FAC OptimizeRadial survey.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 run_fac_survey.py\n"
            "  python3 run_fac_survey.py openmp -n 12\n"
            "  python3 run_fac_survey.py openmp -n 12 --early-stop-rms 0.3\n"
            "  bsub -n 12 python3 run_fac_survey.py openmp\n"
        ),
    )
    parser.add_argument(
        "mode", nargs="?", default=default_mode,
        choices=("serial", "openmp", "mpi"),
        help=f"FAC parallelism mode (default: {default_mode}).",
    )
    parser.add_argument(
        "-n", dest="jobs", type=int, default=default_jobs, metavar="CORES",
        help=f"Parallel trial processes (default: {default_jobs}).",
    )
    parser.add_argument("--input", type=Path, default=Path(default_input))
    parser.add_argument("--output", type=Path, default=Path(default_output))
    parser.add_argument("--ion", default=default_ion,
                        help="Ion module under survey/ions/ (default: %(default)s).")
    parser.add_argument("--max-combination-size", type=int, default=None)
    parser.add_argument("--force", action="store_true",
                        help="Re-run trials even if DONE exists.")
    parser.add_argument("--score-only", action="store_true",
                        help="Skip FAC; score existing output and write known_scores.csv.")
    parser.add_argument(
        "--early-stop-rms", type=float, default=default_early_stop_rms,
        metavar="A",
        help="Stop as soon as any trial RMS (Å) falls below this value.",
    )
    return parser


def run_survey(args: argparse.Namespace) -> int:
    known_peaks, base_config = _load_ion(args.ion)
    config = load_config(args.input)
    args.output.mkdir(parents=True, exist_ok=True)

    group_by_modes = _DEFAULT_GROUP_BY_MODES
    trials = enumerate_trials(config, group_by_modes, args.max_combination_size)
    print(
        f"Survey: {len(trials)} trials  ion={args.ion}  "
        f"mode={args.mode}  jobs={args.jobs}  input={args.input}"
    )

    if not args.score_only:
        failures = 0
        early_stop_hit = False
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = {
                pool.submit(
                    _run_one, t, args.output, args.mode, sys.executable, args.force
                ): t
                for t in trials
            }
            for i, future in enumerate(concurrent.futures.as_completed(futures), start=1):
                trial, status, code = future.result()
                if status == "failed":
                    failures += 1
                rms_str = ""
                if status == "ok" and args.early_stop_rms is not None:
                    scores = _score_trial(
                        args.output / trial["trial_dir"], known_peaks, base_config
                    )
                    if scores is not None:
                        rms_str = f"  RMS={scores['rms_A']:.4f} Å"
                        if scores["rms_A"] < args.early_stop_rms:
                            print(
                                f"[{i:06d}/{len(trials):06d}] {status:7s}  "
                                f"{trial['trial_dir']}{rms_str}",
                                flush=True,
                            )
                            print(
                                f"Early stop: RMS={scores['rms_A']:.4f} Å < "
                                f"threshold {args.early_stop_rms} Å",
                                flush=True,
                            )
                            for f in futures:
                                f.cancel()
                            early_stop_hit = True
                            break
                print(
                    f"[{i:06d}/{len(trials):06d}] {status:7s}  "
                    f"{trial['trial_dir']}{rms_str}",
                    flush=True,
                )
        if failures:
            print(f"WARNING: {failures} trial(s) failed", file=sys.stderr)
        if early_stop_hit:
            print("Survey stopped early.", flush=True)

    print("Scoring …")
    score_rows = []
    for trial in trials:
        scores = _score_trial(
            args.output / trial["trial_dir"], known_peaks, base_config
        )
        row = {k: v for k, v in trial.items() if k != "config"}
        if scores:
            row["status"] = "ok"
            row["rms_A"] = f"{scores['rms_A']:.8g}"
            row["mean_abs_A"] = f"{scores['mean_abs_A']:.8g}"
            row["max_abs_A"] = f"{scores['max_abs_A']:.8g}"
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
