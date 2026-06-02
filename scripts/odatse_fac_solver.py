#!/usr/bin/env python3
"""ODAT-SE custom solver wrapper for the FAC configuration search."""

import csv
import math
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from config_loader import load_config
import run_configuration_search as fac_search

try:
    import odatse
except ModuleNotFoundError:  # pragma: no cover - exercised only without ODAT-SE.
    odatse = None


if odatse is None:
    class _SolverBase:
        def __init__(self, info):
            base = getattr(info, "base", {})
            root_dir = Path(base.get("root_dir", ".")).expanduser().resolve()
            output_dir = Path(base.get("output_dir", "odatse_output")).expanduser()
            if not output_dir.is_absolute():
                output_dir = root_dir / output_dir
            self.root_dir = root_dir
            self.output_dir = output_dir
            self.proc_dir = output_dir / "0"
else:
    _SolverBase = odatse.solver.SolverBase


def _resolve_path(root_dir, value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root_dir / path
    return path


def _candidate_key(trial):
    return (
        ";".join(trial["selected_template_ids"]),
        trial["optimize_radial_strategy_id"],
    )


def build_candidates(config):
    """Enumerate legal FAC candidates for ODAT-SE mapper.

    This intentionally uses the full legal candidate set, not the greedy
    forward-selection order. ODAT-SE's mapper decides which mesh points to
    evaluate.
    """
    candidates = []
    seen = set()
    for trial in fac_search.enumerate_trials(config):
        key = _candidate_key(trial)
        if key in seen:
            continue
        seen.add(key)
        candidate = deepcopy(trial)
        candidate["candidate_id"] = len(candidates)
        candidate["trial_id"] = f"candidate_{len(candidates):06d}"
        candidates.append(candidate)
    return candidates


def write_candidate_mesh(mesh_path, n_candidates):
    mesh_path.parent.mkdir(parents=True, exist_ok=True)
    with mesh_path.open("w", encoding="utf-8") as fh:
        fh.write("# mesh_index candidate_id\n")
        for candidate_id in range(n_candidates):
            fh.write(f"{candidate_id + 1} {candidate_id}\n")


def write_candidate_table(table_path, candidates):
    table_path.parent.mkdir(parents=True, exist_ok=True)
    with table_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "candidate_id",
                "trial_id",
                "configuration",
                "optimization",
                "active_optional_count",
            ],
        )
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(
                {
                    "candidate_id": candidate["candidate_id"],
                    "trial_id": candidate["trial_id"],
                    "configuration": ";".join(candidate["selected_template_ids"]),
                    "optimization": candidate["optimize_radial_strategy_id"],
                    "active_optional_count": candidate.get("active_optional_count", ""),
                }
            )


class Solver(_SolverBase):
    """FAC direct problem solver for ODAT-SE.

    ODAT-SE passes a one-dimensional parameter vector x. x[0] is interpreted as
    an integer candidate_id that indexes the legal configuration/optimization
    table generated from the target YAML.
    """

    def __init__(self, info):
        super().__init__(info)
        solver_info = getattr(info, "solver", {})
        if "target_input" not in solver_info:
            raise RuntimeError("solver.target_input is required for FAC ODAT-SE solver")

        self.target_input = _resolve_path(self.root_dir, solver_info["target_input"])
        self.config = load_config(self.target_input)
        self.candidates = build_candidates(self.config)
        if not self.candidates:
            raise RuntimeError("No legal FAC candidates were generated")

        output_dir = Path(self.output_dir)
        self.fac_work_dir = _resolve_path(
            self.root_dir,
            solver_info.get("fac_work_dir", output_dir / "fac_trials"),
        )
        self.generated_dir = _resolve_path(
            self.root_dir,
            solver_info.get("generated_dir", output_dir / "generated_fac"),
        )
        self.results_file = _resolve_path(
            self.root_dir,
            solver_info.get("results_file", output_dir / "fac_results.txt"),
        )
        self.summary_file = _resolve_path(
            self.root_dir,
            solver_info.get(
                "summary_file",
                output_dir / "loss_configuration_optimization.txt",
            ),
        )
        self.candidate_table = _resolve_path(
            self.root_dir,
            solver_info.get("candidate_table", output_dir / "candidate_table.txt"),
        )
        write_candidate_table(self.candidate_table, self.candidates)

    def _trial_for_candidate(self, candidate_id):
        if candidate_id < 0 or candidate_id >= len(self.candidates):
            raise RuntimeError(
                f"candidate_id {candidate_id} is outside [0, {len(self.candidates) - 1}]"
            )
        candidate = deepcopy(self.candidates[candidate_id])
        candidate["trial_id"] = f"candidate_{candidate_id:06d}"
        config = candidate["config"]
        config["search"]["work_dir"] = str(self.fac_work_dir)
        config["search"]["generated_dir"] = str(self.generated_dir)
        config["search"]["results_file"] = str(self.results_file)
        config["search"]["keep_generated_scripts"] = True
        return candidate

    def evaluate(self, x, args=(), nprocs=1, nthreads=1) -> float:
        if nprocs != 1 or nthreads != 1:
            raise RuntimeError("FAC ODAT-SE solver currently accepts nprocs=nthreads=1")
        if len(x) != 1:
            raise RuntimeError(f"FAC ODAT-SE solver expects dimension=1, got {len(x)}")

        candidate_id = int(round(float(x[0])))
        if not math.isclose(float(x[0]), candidate_id, abs_tol=1.0e-8):
            raise RuntimeError(f"candidate_id must be integer-like, got {x[0]!r}")

        trial = self._trial_for_candidate(candidate_id)
        result = fac_search.run_trial(trial, self.root_dir, self.config)
        row = fac_search.result_row(trial, result)
        self._append_result(row)
        fac_search.write_loss_configuration_optimization_table(
            self.summary_file,
            self._read_result_rows(),
        )
        return fac_search.numeric_loss(result["loss"])

    def _append_result(self, row):
        self.results_file.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "trial_id",
            "candidate_id",
            "loss",
            "selected_template_ids",
            "optimize_radial_strategy_id",
            "returncode",
            "run_dir",
            "script",
            "peak_summary",
        ]
        exists = self.results_file.exists()
        with self.results_file.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            writer.writerow(
                {
                    "trial_id": row["trial_id"],
                    "candidate_id": row["trial_id"].replace("candidate_", "", 1),
                    "loss": row["loss"],
                    "selected_template_ids": row["selected_template_ids"],
                    "optimize_radial_strategy_id": row["optimize_radial_strategy_id"],
                    "returncode": row["returncode"],
                    "run_dir": row["run_dir"],
                    "script": row["script"],
                    "peak_summary": row["peak_summary"],
                }
            )

    def _read_result_rows(self):
        if not self.results_file.exists():
            return []
        with self.results_file.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        converted = []
        for row in rows:
            converted.append(
                {
                    "trial_id": row["trial_id"],
                    "loss": row["loss"],
                    "selected_template_ids": row["selected_template_ids"],
                    "optimize_radial_strategy_id": row["optimize_radial_strategy_id"],
                }
            )
        return converted
