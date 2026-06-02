# FAC Input Generation

This project can use a Python target file as the editable input, then generate
a PFAC Python script from it. YAML target files are still supported for old
runs, but the Python input avoids the PyYAML dependency.

## Edit The Target File

Edit:

```bash
inputs/target_case_v2.py
```

Important variables are at the top of the file:

```python
REFERENCE_PEAKS = [5.69, 5.87, 7.0262]

ION = {"element": "W", "Z": 74, "charge_state": 46, "K": 28}

DEFAULT_NL = {"n": [4, 5, 6, 7], "l": [0, 1, 2, 3, 4, 5, 6], "occupancy": 1}

CONFIGURATIONS = [
    "3p6 3d10",
    "3p6 3d9 nl",
    "3p5 3d10 nl",
]
```

The first configuration is required by default; later configurations are
optional by default. Internal ids and default `OptimizeRadial` strategies are
generated automatically.

For `active: "nl"`, the generator expands `n` and `l` into FAC notation.
It also applies the orbital constraint `l <= n - 1`, so `n=4, l=0-4`
expands only to `4[s,p,d,f]`; it does not generate `4g`.
For example:

```yaml
prefix: "3p6 3d9"
n: [4, 5, 6]
l: [0, 1, 2, 3, 4]
```

becomes:

```python
fac.Config('3p6 3d9 4[s,p,d,f]', group='n3')
fac.Config('3p6 3d9 5[s,p,d,f,g]', group='n4')
fac.Config('3p6 3d9 6[s,p,d,f,g]', group='n5')
```

## Generate The FAC Script

Run from the project root:

```bash
python3 scripts/generate_fac_input.py inputs/target_case_v2.py -o generated/W46_phase1.py
```

The generated file is a normal PFAC input script.

## Run FAC

Run in a separate output directory:

```bash
mkdir -p runs/W46_phase1
cd runs/W46_phase1
python3 ../../generated/W46_phase1.py
```

With OpenMP-style FAC parallelism, for FAC built with `--with-mpi=omp`:

```bash
python3 ../../generated/W46_phase1.py openmp
```

With real MPI FAC, for FAC built with MPI support:

```bash
mpirun -np 16 python3 ../../generated/W46_phase1.py mpi
```

For the automatic search runner, set this in `inputs/target_case_v2.py`:

```python
FAC_INPUT = {
    ...
    "parallel": {
        "mode": "mpi",       # "serial", "openmp", or "mpi"
        "nproc": 16,
        "launcher": "mpirun",
        "nproc_flag": "-np",
        "launcher_args": [],
    },
}
```

Then run the usual search command:

```bash
python3 scripts/run_configuration_search.py inputs/target_case_v2.py --clean
```

Each FAC trial will be launched as:

```text
mpirun -np 16 python trial.py mpi
```

For `mpiexec -n`, use:

```python
"launcher": "mpiexec",
"nproc_flag": "-n",
```

Expected main outputs:

```text
W28a.en
W28a.tr
W28b.en
W28b.tr
W46.pot
```

## OptimizeRadial

For now, `OptimizeRadial` is controlled by:

```yaml
radial_potential:
  optimize_radial_groups: ["ground_3p6_3d10"]
```

The generator maps this semantic template id to the generated FAC group name,
for example `ground_3p6_3d10 -> n2`.

Later, this field can be varied by ODAT-SE or by manual trial files without
changing the generator logic.

## Search Over Configuration Templates

The single-script generator only maps one YAML configuration into one FAC
input. To try combinations of optional configuration templates, run:

```bash
python3 scripts/run_configuration_search.py inputs/target_case_v2.py --clean
```

The search runner:

1. Keeps templates with `required: true`.
2. Enumerates on/off combinations of templates with `required: false`.
3. Generates a temporary PFAC script per trial.
4. Runs FAC in one directory per trial under `runs/search_W46/`.
5. Parses the ASCII `.tr` file.
6. Scores line groups near the reference peak energies.
7. Writes ranked results to:

```bash
runs/search_W46/results.csv
```

For the current W46+ example, the required template is:

```yaml
- id: "ground_3p6_3d10"
  required: true
```

The optional templates are:

```yaml
- id: "hole_3d9_nl"
  required: false

- id: "hole_3p5_3d10_nl"
  required: false
```

So the first grid search tries four cases:

```text
ground only
ground + 3d-hole nl
ground + 3p-hole nl
ground + both nl families
```

This is still a simple grid search, not full ODAT-SE. It is intended as the
first working loop: generate trial, run FAC, parse `.tr`, score peaks, rank
configuration candidates.

## Scoring Window

FAC `.tr` files store transition energy in eV. The search runner can screen
candidate line groups either in energy space or wavelength space.

Use wavelength screening, for example `0.1 nm`:

```yaml
search:
  scoring:
    window_space: "wavelength"
    wavelength_window:
      value: 0.1
      unit: "nm"
```

Use energy screening, for example `8 eV`:

```yaml
search:
  scoring:
    window_space: "energy"
    energy_window_eV: 8.0
```

In both cases, the runner reads transition energies from `.tr`. For wavelength
screening, it converts each transition by:

```text
lambda[angstrom] = 12398.419843320026 / E[eV]
```

The result summary records both energy and wavelength residuals.

By default, trial `.py` files are not kept:

```yaml
search:
  keep_generated_scripts: false
```

Set it to `true` only when debugging generated PFAC scripts.
