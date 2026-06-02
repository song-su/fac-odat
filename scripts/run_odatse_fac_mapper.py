#!/usr/bin/env python3
"""Prepare and run ODAT-SE mapper for the FAC search solver."""

import argparse
import csv
import importlib
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from config_loader import load_config
from odatse_fac_solver import Solver, build_candidates, write_candidate_mesh, write_candidate_table


def write_default_toml(path: Path, target_input: Path, output_dir: Path, mesh_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "[base]",
                "dimension = 1",
                'root_dir = "."',
                f'output_dir = "{output_dir.as_posix()}"',
                "",
                "[algorithm]",
                'name = "mapper"',
                "",
                "[algorithm.param]",
                f'mesh_path = "{mesh_path.as_posix()}"',
                "",
                "[solver]",
                'name = "fac"',
                "dimension = 1",
                f'target_input = "{target_input.as_posix()}"',
                f'fac_work_dir = "{(output_dir / "fac_trials").as_posix()}"',
                f'generated_dir = "{(output_dir / "generated_fac").as_posix()}"',
                f'results_file = "{(output_dir / "fac_results.txt").as_posix()}"',
                f'summary_file = "{(output_dir / "loss_configuration_optimization.txt").as_posix()}"',
                f'candidate_table = "{(output_dir / "candidate_table.txt").as_posix()}"',
                "",
                "[runner]",
                "ignore_error = false",
                "",
                "[runner.log]",
                'filename = "runner.log"',
                "interval = 1",
                "write_input = true",
                "write_result = true",
                "",
            ]
        ),
        encoding="utf-8",
    )


def prepare_files(target_input: Path, output_dir: Path, toml_path: Path) -> None:
    config = load_config(target_input)
    candidates = build_candidates(config)
    mesh_path = output_dir / "candidate_mesh.txt"
    candidate_table = output_dir / "candidate_table.txt"
    write_candidate_mesh(mesh_path, len(candidates))
    write_candidate_table(candidate_table, candidates)
    write_default_toml(toml_path, target_input, output_dir, mesh_path)
    print(f"candidates: {len(candidates)}")
    print(f"wrote {mesh_path}")
    print(f"wrote {candidate_table}")
    print(f"wrote {toml_path}")


def default_output_dir_from_target(target_input: Path) -> Path:
    config = load_config(target_input)
    work_dir = Path(config["search"]["work_dir"])
    name = work_dir.name
    if name.startswith("search_"):
        name = "odatse_" + name[len("search_"):]
    else:
        name = "odatse_" + name
    parent = work_dir.parent if str(work_dir.parent) != "." else Path("runs")
    return parent / name


def _load_toml(path: Path) -> dict:
    if sys.version_info >= (3, 11):
        import tomllib

        with path.open("rb") as fh:
            return tomllib.load(fh)
    try:
        import tomli
    except ModuleNotFoundError as exc:
        raise RuntimeError("Python < 3.11 requires tomli to read TOML files") from exc
    with path.open("rb") as fh:
        return tomli.load(fh)


class LocalInfo:
    def __init__(self, data: dict):
        self.base = data.get("base", {})
        root = Path(self.base.get("root_dir", ".")).expanduser().resolve()
        self.base["root_dir"] = root
        output = Path(self.base.get("output_dir", ".")).expanduser()
        if not output.is_absolute():
            output = root / output
        self.base["output_dir"] = output
        self.solver = data.get("solver", {})
        self.algorithm = data.get("algorithm", {})
        self.runner = data.get("runner", {})


def run_local_mapper(toml_path: Path) -> None:
    data = _load_toml(toml_path)
    info = LocalInfo(data)
    mesh_path = Path(data["algorithm"]["param"]["mesh_path"]).expanduser()
    if not mesh_path.is_absolute():
        mesh_path = info.base["root_dir"] / mesh_path
    solver = Solver(info)

    rows = []
    with mesh_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            mesh_index = int(parts[0])
            candidate_id = float(parts[1])
            loss = solver.evaluate([candidate_id], args=(mesh_index, 0))
            rows.append((mesh_index, candidate_id, loss))
            print(f"mesh={mesh_index} candidate_id={int(candidate_id)} loss={loss}", flush=True)

    color_map = info.base["output_dir"] / "ColorMap.txt"
    color_map.parent.mkdir(parents=True, exist_ok=True)
    with color_map.open("w", encoding="utf-8") as fh:
        for _, candidate_id, loss in rows:
            fh.write(f"{candidate_id:.8f} {loss:.16g}\n")
    print(f"wrote {color_map}")


def _load_odatse_algorithm(name: str):
    candidates = [
        f"odatse.algorithm.{name}",
        f"odatse.algorithm.{name}_mpi",
    ]
    for module_name in candidates:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        if hasattr(module, "Algorithm"):
            return module.Algorithm
    raise RuntimeError(f"Could not import ODAT-SE algorithm {name!r}")


def run_odatse(toml_path: Path) -> None:
    try:
        import odatse
    except ModuleNotFoundError as exc:
        raise RuntimeError("ODAT-SE is not installed; use --local or install odat-se") from exc

    info = odatse.Info.from_file(toml_path)
    solver = Solver(info)
    runner = odatse.Runner(solver, info)
    algorithm_name = info.algorithm.get("name", "mapper")
    Algorithm = _load_odatse_algorithm(algorithm_name)
    algorithm = Algorithm(info, runner)
    result = algorithm.main()
    print(result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("inputs/target_case_v2.py"),
        help="FAC target Python/YAML file used to build candidates",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="ODAT-SE output directory; defaults to target search label",
    )
    parser.add_argument(
        "--toml",
        type=Path,
        default=Path("inputs/odatse_fac_mapper.toml"),
        help="ODAT-SE TOML file to write/read",
    )
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--local", action="store_true", help="Run local mapper without ODAT-SE")
    parser.add_argument("--clean", action="store_true", help="Remove output directory first")
    args = parser.parse_args()
    if args.output_dir is None:
        args.output_dir = default_output_dir_from_target(args.target)

    if args.clean and args.output_dir.exists():
        shutil.rmtree(args.output_dir)

    prepare_files(args.target, args.output_dir, args.toml)
    if args.prepare_only:
        return
    if args.local:
        run_local_mapper(args.toml)
    else:
        run_odatse(args.toml)


if __name__ == "__main__":
    main()
