# ODAT-SE integration notes

This project now has a first ODAT-SE-facing FAC solver wrapper.

## Files

- `scripts/odatse_fac_solver.py`
  - Defines `Solver`, a custom ODAT-SE direct-problem solver.
  - ODAT-SE passes a one-dimensional parameter vector `x`.
  - `x[0]` is interpreted as an integer `candidate_id`.
  - The candidate maps to a legal configuration set plus an `OptimizeRadial`
    strategy.
  - The solver reuses the existing FAC generation, FAC execution, and v2 loss
    calculation code from `scripts/run_configuration_search.py`.

- `scripts/run_odatse_fac_mapper.py`
  - Prepares `candidate_mesh.txt`, `candidate_table.csv`, and
    `inputs/odatse_fac_mapper.toml`.
  - Can run through ODAT-SE when `odatse` is installed.
  - Can run a local mapper with `--local` for interface testing without ODAT-SE.

- `inputs/odatse_fac_mapper.toml`
  - ODAT-SE input file using `algorithm.name = "mapper"`.
  - The mesh is one-dimensional: `candidate_id`.

## Prepare ODAT-SE input

```bash
python3 scripts/run_odatse_fac_mapper.py --target inputs/target_case_v2.py --prepare-only --clean
```

This writes:

```text
runs/odatse_W46_v2/candidate_mesh.txt
runs/odatse_W46_v2/candidate_table.csv
inputs/odatse_fac_mapper.toml
```

## Run with ODAT-SE

After installing ODAT-SE:

```bash
python3 scripts/run_odatse_fac_mapper.py --target inputs/target_case_v2.py --clean
```

The script instantiates:

```text
odatse.Info
FAC Solver
odatse.Runner
ODAT-SE mapper Algorithm
```

and then calls `algorithm.main()`.

## Local mapper fallback

For testing the same solver without ODAT-SE:

```bash
python3 scripts/run_odatse_fac_mapper.py --target inputs/target_case_v2.py --local --clean
```

This evaluates every candidate in `candidate_mesh.txt` using the same custom
solver class and writes:

```text
runs/odatse_W46_v2/fac_results.csv
runs/odatse_W46_v2/loss_configuration_optimization.csv
runs/odatse_W46_v2/ColorMap.txt
```

## Current modeling choice

The first ODAT-SE parameterization is intentionally simple:

```text
x[0] = candidate_id
```

`candidate_id` indexes a precomputed legal table:

```text
configuration templates + OptimizeRadial strategy
```

This avoids treating categorical configuration choices as continuous variables.
The first recommended ODAT-SE algorithm is therefore `mapper`, not `minsearch`.
