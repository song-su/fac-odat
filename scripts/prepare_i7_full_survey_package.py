#!/usr/bin/env python3
"""Prepare a standalone FAC full-combination survey package.

The package contains generated PFAC trial inputs, a manifest, a runner script,
and a scorer script.  It does not run FAC locally; it prepares files that can
be copied to a server or cluster and executed there.

Customise the "User parameters" section below for a different ion or survey
input.  All logic in the "Implementation" section is ion-independent.
"""

import argparse
import csv
import itertools
import json
import shutil
import stat
from copy import deepcopy
from pathlib import Path

from config_loader import load_config
from generate_fac_input import build_fac_script


# ---------------------------------------------------------------------------
# User parameters — edit for each survey
# ---------------------------------------------------------------------------

# Input config file that defines the configuration space and ion parameters.
DEFAULT_INPUT = Path("survey/configs/i7plus_fac.py")

# Output directory for the generated survey package.
DEFAULT_OUTPUT = Path("runs/i7_full_fac_survey_package")

# FAC group-by modes to enumerate.  Each mode maps active-orbital type
# ("nl" or "mk") to a grouping key ("n"/"l" or "m"/"k").
# Add or remove entries here to change which grouping modes are surveyed.
GROUP_BY_MODES = {
    "nm": {"nl": "n", "mk": "m"},   # 5[s,p,d,f] in one group
    "lk": {"nl": "l", "mk": "k"},   # 5s, 5p, 5d, 5f in separate groups
}


# ---------------------------------------------------------------------------
# Implementation — no user edits needed below
# ---------------------------------------------------------------------------


def optimize_template_ids(config):
    templates = config["configuration_space"]["templates"]["bound"]
    ids = [
        template["id"]
        for template in templates
        if template.get("optimize_radial", True)
    ]
    if not ids:
        raise ValueError("No templates are available for OptimizeRadial survey")
    return ids


def combinations_by_size(items, max_size=None):
    limit = len(items) if max_size is None else min(int(max_size), len(items))
    for size in range(1, limit + 1):
        for combo in itertools.combinations(items, size):
            yield combo


def strategy_id(index, combo):
    if len(combo) == 1:
        suffix = combo[0]
    else:
        suffix = f"{len(combo)}groups"
    return f"opt_{index:04d}_{suffix}"


def apply_group_by_mode(config, mode):
    mode_map = GROUP_BY_MODES[mode]
    updated = deepcopy(config)
    for template in updated["configuration_space"]["templates"]["bound"]:
        active = template.get("active")
        if active in mode_map:
            template["group_by"] = mode_map[active]
    return updated


def build_strategy_config(config, combo):
    trial_config = deepcopy(config)
    trial_config.setdefault("radial_potential", {})["optimize_radial_groups"] = list(combo)
    return trial_config


def write_text(path, content, executable=False):
    path.write_text(content, encoding="utf-8")
    if executable:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def runner_script():
    return """#!/usr/bin/env python3
import argparse
import concurrent.futures
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def trial_scripts():
    return sorted((ROOT / "trials").glob("*/*/trial.py"))


def run_trial(script, mode, python_executable, force):
    trial_dir = script.parent
    done = trial_dir / "DONE"
    if done.exists() and not force:
        return str(trial_dir.relative_to(ROOT)), "skipped", 0

    with (trial_dir / "fac.stdout").open("w", encoding="utf-8") as stdout:
        with (trial_dir / "fac.stderr").open("w", encoding="utf-8") as stderr:
            result = subprocess.run(
                [python_executable, "trial.py", mode],
                cwd=str(trial_dir),
                stdout=stdout,
                stderr=stderr,
            )

    if result.returncode == 0:
        done.touch()
        status = "ok"
    else:
        status = "failed"
    return str(trial_dir.relative_to(ROOT)), status, result.returncode


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--mode", choices=("serial", "openmp", "mpi"), default="serial")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--force", action="store_true", help="Rerun trials even if DONE exists.")
    return parser.parse_args()


def main():
    args = parse_args()
    scripts = trial_scripts()
    print(f"Running {len(scripts)} FAC trials with jobs={args.jobs}, mode={args.mode}")
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = [
            executor.submit(run_trial, script, args.mode, args.python, args.force)
            for script in scripts
        ]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            trial_dir, status, code = future.result()
            if status == "failed":
                failures += 1
            print(f"[{index:04d}/{len(scripts):04d}] {status:7s} code={code:3d} {trial_dir}", flush=True)

    if failures:
        print(f"{failures} trial(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def score_script():
    return """#!/usr/bin/env python3
import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent

from known import find_known_candidates, KNOWN_PEAKS


def score(en_path, tr_path):
    candidates = find_known_candidates(
        KNOWN_PEAKS,
        en_path=en_path,
        tr_path=tr_path,
        top_n=1,
        use_paper_fac_target=True,
    )
    if not candidates:
        return math.inf, math.inf, math.inf, []
    residuals = [item.residual_angstrom for item in candidates]
    rms = math.sqrt(sum(value * value for value in residuals) / len(residuals))
    mean_abs = sum(abs(value) for value in residuals) / len(residuals)
    max_abs = max(abs(value) for value in residuals)
    return rms, mean_abs, max_abs, candidates


def main():
    rows = []
    manifest_path = ROOT / "manifest.csv"
    with manifest_path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            trial_dir = ROOT / row["trial_dir"]
            en_files = sorted(trial_dir.glob("*a.en"))
            tr_files = sorted(trial_dir.glob("*a.tr"))
            if not en_files or not tr_files:
                row.update({
                    "status": "missing_output",
                    "rms_A": "",
                    "mean_abs_A": "",
                    "max_abs_A": "",
                })
            else:
                rms, mean_abs, max_abs, _ = score(en_files[0], tr_files[0])
                row.update({
                    "status": "ok",
                    "rms_A": f"{rms:.8g}",
                    "mean_abs_A": f"{mean_abs:.8g}",
                    "max_abs_A": f"{max_abs:.8g}",
                })
            rows.append(row)

    rows.sort(key=lambda item: float(item["rms_A"]) if item["rms_A"] else math.inf)
    output_path = ROOT / "known_scores.csv"
    fieldnames = [
        "status", "rms_A", "mean_abs_A", "max_abs_A",
        "mode", "trial_id", "strategy_id", "combo_size",
        "optimize_templates", "trial_dir",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})

    for row in rows[:20]:
        print(
            f"{row['status']:14s} RMS={row.get('rms_A',''):>10s} "
            f"mode={row['mode']:2s} trial={row['trial_id']} "
            f"combo={row['optimize_templates']}"
        )
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
"""


def readme_text(input_path, max_size, group_by_modes):
    max_size_text = "all" if max_size is None else str(max_size)
    mode_lines = "\n".join(
        f"- `{mode}`: " + ", ".join(f"`{k}` grouped by `{v}`" for k, v in mapping.items())
        for mode, mapping in group_by_modes.items()
    )
    return f"""# FAC Full Survey Package

Generated from `{input_path}`.

To adapt for a different ion: edit `known.py` (update `KNOWN_PEAKS`) and
replace `{input_path.name}` with your own survey input file.

This package contains generated PFAC inputs for the following grouping modes:

{mode_lines}

For each mode, all OptimizeRadial template-family combinations up to
`max_combination_size = {max_size_text}` are generated.

## Run on server

From this directory:

```bash
python3 run_all.py --jobs 12 --mode serial
```

`--jobs` is the number of independent trial processes.  `--mode` is passed to
each PFAC script (`serial`, `openmp`, or `mpi`).  If FAC was not compiled with
OpenMP/MPI, use `serial` and rely on process parallelism.

## Score after FAC finishes

```bash
python3 score_known.py
```

Scores are written to `known_scores.csv`, sorted by RMS residual against the
Kimura et al. Table I FAC wavelengths.
"""


def prepare_package(config, output_dir, input_path, max_combination_size=None):
    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "trials").mkdir(parents=True)

    template_ids = optimize_template_ids(config)
    manifest_rows = []
    global_index = 0
    for mode in ("nm", "lk"):
        mode_config = apply_group_by_mode(config, mode)
        for strategy_index, combo in enumerate(
            combinations_by_size(template_ids, max_combination_size),
            start=1,
        ):
            global_index += 1
            sid = strategy_id(strategy_index, combo)
            trial_id = f"trial_{global_index:06d}"
            trial_dir = Path("trials") / mode / f"{trial_id}_{sid}"
            abs_trial_dir = output_dir / trial_dir
            abs_trial_dir.mkdir(parents=True)
            trial_config = build_strategy_config(mode_config, combo)
            write_text(abs_trial_dir / "trial.py", build_fac_script(trial_config))
            manifest_rows.append({
                "mode": mode,
                "trial_id": trial_id,
                "strategy_id": sid,
                "combo_size": len(combo),
                "optimize_templates": ";".join(combo),
                "trial_dir": str(trial_dir),
            })

    with (output_dir / "manifest.csv").open("w", encoding="utf-8", newline="") as fh:
        fieldnames = [
            "mode", "trial_id", "strategy_id", "combo_size",
            "optimize_templates", "trial_dir",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    metadata = {
        "input": str(input_path),
        "group_by_modes": GROUP_BY_MODES,
        "template_ids": template_ids,
        "max_combination_size": max_combination_size,
        "trial_count": len(manifest_rows),
    }
    write_text(output_dir / "metadata.json", json.dumps(metadata, indent=2) + "\n")
    shutil.copy2(input_path, output_dir / input_path.name)
    shutil.copy2(Path("scripts/known.py"), output_dir / "known.py")
    write_text(output_dir / "run_all.py", runner_script(), executable=True)
    write_text(output_dir / "score_known.py", score_script(), executable=True)
    write_text(output_dir / "README.md", readme_text(input_path, max_combination_size, GROUP_BY_MODES))
    return metadata


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--max-combination-size",
        type=int,
        default=None,
        help="Limit OptimizeRadial template-family combinations. Default: all.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config(args.input)
    metadata = prepare_package(
        config=config,
        output_dir=args.output_dir,
        input_path=args.input,
        max_combination_size=args.max_combination_size,
    )
    print(args.output_dir)
    print(f"trial_count={metadata['trial_count']}")


if __name__ == "__main__":
    main()
