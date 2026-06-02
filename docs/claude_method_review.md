# Method Review Brief: FAC + ODAT-SE Phase-1 Configuration Search

## Project Goal

We have EBIT experimental spectra for highly charged heavy ions. The long-term
goal is to identify atomic configurations and radial-potential strategies that
can explain observed UTA / blended spectral peaks.

FAC is used as the forward solver:

```text
configuration + radial potential -> FAC -> levels + transition energies + A-values
```

ODAT-SE, or a simpler search loop before full ODAT-SE integration, is used as
the inverse search layer:

```text
experimental peak features -> search configuration + potential strategy
```

The current stage is not a full CRM spectral fit. It is a phase-1 screening
step. We only ask whether a trial configuration set can produce plausible
theoretical line groups near the experimental peaks.

Important physical limitation:

```text
one experimental UTA peak != one theoretical transition
one experimental UTA peak ~= one theoretical line group
```

FAC A-values are not treated as true experimental intensities because the
upper-level populations are not known without CRM:

```text
I_ul proportional to N_u A_ul
```

At this stage, A-values are used only as radiative-potential weights.

## Current Example Case

Ion:

```yaml
element: W
Z: 74
charge_state: 46
K: 28
```

This is Ni-like W46+ with 28 bound electrons.

Reference wavelengths:

```yaml
5.69 nm
5.87 nm
```

These are converted internally to energy using:

```text
E[eV] = 12398.419843320026 / lambda[angstrom]
```

Approximate energies:

```text
5.69 nm -> 217.8984 eV
5.87 nm -> 211.2167 eV
```

Closed shells currently used in FAC:

```python
fac.Closed('1s', '2s', '2p', '3s')
```

Configuration templates:

```text
3p6 3d10
3p6 3d9 nl
3p5 3d10 nl
```

with:

```text
n = 4, 5, 6
l = 0, 1, 2, 3, 4
```

The generator enforces the orbital constraint:

```text
l <= n - 1
```

So for `n=4`, `l=4` is not generated. That means:

```text
4[s,p,d,f]
```

not:

```text
4[s,p,d,f,g]
```

## Files

Main editable target input:

```text
inputs/target_case.yaml
```

FAC input generator:

```text
scripts/generate_fac_input.py
```

Simple grid-search runner:

```text
scripts/run_configuration_search.py
```

Generated single FAC script example:

```text
generated/W46_phase1.py
```

Operational notes:

```text
docs/run_generation.md
```

This review brief:

```text
docs/claude_method_review.md
```

## Input YAML Design

The YAML file is intended to be the user-facing control file. It separates:

1. Experimental targets.
2. Ion identity.
3. FAC fixed settings.
4. Configuration-generation rules.
5. Radial-potential strategy.
6. Search/scoring settings.

Configuration templates are written compactly. Example:

```yaml
configuration_space:
  templates:
    bound:
      - id: "hole_3d9_nl"
        prefix: "3p6 3d9"
        active: "nl"
        n: [4, 5, 6]
        l: [0, 1, 2, 3, 4]
        occupancy: 1
        required: false
```

This expands to FAC configurations like:

```python
fac.Config('3p6 3d9 4[s,p,d,f]', group='n3')
fac.Config('3p6 3d9 5[s,p,d,f,g]', group='n4')
fac.Config('3p6 3d9 6[s,p,d,f,g]', group='n5')
```

The ground template is currently required:

```yaml
- id: "ground_3p6_3d10"
  prefix: "3p6 3d10"
  active: null
  required: true
```

The two `nl` families are currently optional, so the first grid search tries
all on/off combinations of them.

## FAC Generation

The generator converts the YAML to a PFAC Python script similar to the provided
standard input file `Bi22.py`.

Core generated FAC flow:

```python
fac.SetAtom(a)
SetUTA(0)
fac.Closed(...)
fac.Config(...)

fac.ConfigEnergy(0)
fac.OptimizeRadial([...])
fac.ConfigEnergy(1)
fac.GetPotential(...)

fac.Structure(...)
fac.MemENTable(...)
fac.PrintTable(..., 1)

fac.SetTransitionMaxE(3)
fac.SetTransitionMaxM(3)
fac.TransitionTable(..., 0)
fac.PrintTable(..., 1)
```

Important FAC multipole convention:

```text
TransitionTable(..., m)

m < 0: electric multipole, e.g. -1 = E1
m > 0: magnetic multipole, e.g. +1 = M1
m = 0 or omitted: sum allowed multipoles
```

The current setup uses:

```python
fac.SetTransitionMaxE(3)
fac.SetTransitionMaxM(3)
fac.TransitionTable(..., 0)
```

This is intended to include allowed electric and magnetic multipoles up to
rank 3 in the summed transition rate.

## OptimizeRadial

This is recognized as a major open methodological issue.

For now, `OptimizeRadial` is deliberately simple:

```yaml
radial_potential:
  optimize_radial_groups: ["ground_3p6_3d10"]
```

The generator maps this semantic template ID to the actual FAC group name,
for example:

```text
ground_3p6_3d10 -> n2
```

and generates:

```python
fac.OptimizeRadial(['n2'])
```

Later, `OptimizeRadial` should become a search variable, for example:

```text
ground only
ground + low excited family
3d-hole family
3p-hole family
weighted mean configuration
```

But this has not yet been implemented.

## Search Loop

The current search loop is a simple template-subset grid search, not full
ODAT-SE.

Command:

```bash
python3 scripts/run_configuration_search.py inputs/target_case.yaml --clean
```

The runner:

1. Keeps templates with `required: true`.
2. Enumerates on/off combinations of templates with `required: false`.
3. Generates a temporary PFAC script per trial.
4. Runs FAC in a separate trial directory.
5. Parses the ASCII `.tr` file.
6. Scores candidate line groups near the reference peaks.
7. Writes ranked results to:

```text
runs/search_W46/results.csv
```

For the current example, it tries:

```text
ground only
ground + 3p5 3d10 nl
ground + 3p6 3d9 nl
ground + both nl families
```

Trial Python scripts are not retained by default to avoid creating many files:

```yaml
search:
  keep_generated_scripts: false
```

## Scoring

FAC `.tr` files store transition energies in eV and rates/A-values.

The scoring can screen candidate lines either in energy space or wavelength
space.

Current wavelength-window example:

```yaml
search:
  scoring:
    window_space: "wavelength"
    wavelength_window:
      value: 0.1
      unit: "nm"
```

This selects transitions satisfying:

```text
abs(lambda_i - lambda_peak) <= 0.1 nm
```

Energy-window mode is also available:

```yaml
search:
  scoring:
    window_space: "energy"
    energy_window_eV: 8.0
```

For each reference peak, selected transitions form a theoretical line group.
The current group center is rate-weighted:

```text
E_group = sum(E_i A_i) / sum(A_i)
lambda_group = sum(lambda_i A_i) / sum(A_i)
```

Current simplified loss:

```text
loss += residual^2 - log(sum(A_i) + floor)
```

where the residual is either:

```text
E_group - E_peak
```

or:

```text
lambda_group - lambda_peak
```

depending on `window_space`.

If no line is found for a reference peak, a large missing-peak penalty is
added:

```yaml
missing_peak_penalty: 1000000.0
```

Again, `A_i` is only used as a radiative-potential weight, not a true
experimental intensity.

## Known Limitations

1. This is not yet ODAT-SE. It is a deterministic grid-search skeleton.
2. The search space is currently only template on/off combinations.
3. `OptimizeRadial` is fixed to the ground configuration for now.
4. The loss does not yet include a global energy shift or wavelength shift.
5. The loss does not yet use experimental peak widths, areas, or uncertainties.
6. The line group uses a hard window. A Gaussian soft window may be better.
7. Rate-weighted centers may be biased because FAC A-values are not populations.
8. No CRM population effects are included.
9. The current summed multipole treatment needs careful interpretation when
   comparing to physical emission features.
10. Large configuration sets may make FAC expensive; pruning and caching are
    not yet implemented.

## Questions For Method Review

Please evaluate the method, especially:

1. Is the phase-1 idea scientifically reasonable: using FAC line groups near
   UTA peaks as a configuration-screening criterion before CRM?
2. Is it better to screen and score in wavelength space or energy space for
   peaks specified experimentally in nm?
3. Should the first-pass line-group window be hard, or should it use Gaussian
   soft weights based on experimental peak width?
4. Is rate-weighted grouping acceptable as a rough radiative-potential score,
   or should A-values only enter as a weak prior?
5. How should global FAC energy/wavelength shift be included?
6. What `OptimizeRadial` strategies are physically reasonable to search?
7. What additional penalties are needed to avoid false positives where many
   weak lines happen to fall inside the window?
8. How should one compare candidate models with different numbers of
   configurations, given that larger models naturally produce more lines?
9. Are the current W46+ closed shells and configuration families reasonable
   for Ni-like tungsten around 5.7-5.9 nm?
10. What would be the best next step before integrating full ODAT-SE?

