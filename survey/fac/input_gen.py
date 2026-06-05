"""Generate a FAC Python trial script from a survey config dict.

The only public symbol is build_fac_script(config) -> str.
"""
from __future__ import annotations


def _quote(value: str) -> str:
    return repr(value)


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _expand_l_symbols(l_values, l_symbol_map, n_value=None):
    symbols = []
    for l_value in l_values:
        if n_value is not None and l_value > n_value - 1:
            continue
        key = str(l_value)
        if key not in l_symbol_map:
            raise ValueError(f"No l symbol defined for l={l_value}")
        symbols.append(l_symbol_map[key])
    return symbols


def _active_group_by(template, principal_key, angular_key):
    group_by = template.get("group_by", principal_key)
    aliases = {
        "principal": principal_key, "n": "n", "m": "m",
        "angular": angular_key, "l": "l", "k": "k",
    }
    group_by = aliases.get(str(group_by).strip().lower(), group_by)
    if group_by not in (principal_key, angular_key):
        raise ValueError(
            f"Unsupported group_by={template.get('group_by')!r} in {template['id']}; "
            f"use {principal_key!r} or {angular_key!r}"
        )
    return group_by


def _expand_template(template, l_symbol_map):
    prefix = template["prefix"].strip()
    active = template.get("active")
    if not active:
        return [(template["id"], prefix)]

    if active not in ("nl", "mk"):
        raise ValueError(f"Unsupported active template {active!r} in {template['id']}")

    configs = []
    occupancy = template.get("occupancy", 1)
    occ_suffix = "" if occupancy in (None, 1) else str(occupancy)
    principal_key = "n" if active == "nl" else "m"
    angular_key = "l" if active == "nl" else "k"
    group_by = _active_group_by(template, principal_key, angular_key)

    for n_value in template[principal_key]:
        l_symbols = _expand_l_symbols(template[angular_key], l_symbol_map, n_value=n_value)
        if not l_symbols:
            raise ValueError(f"No valid l values for n={n_value} in {template['id']}")
        if group_by == angular_key:
            for l_symbol in l_symbols:
                configs.append((template["id"], f"{prefix} {n_value}{l_symbol}{occ_suffix}"))
        else:
            l_part = ",".join(l_symbols)
            configs.append((template["id"], f"{prefix} {n_value}[{l_part}]{occ_suffix}"))
    return configs


def _target_peak_comments(config):
    target = config["target"]
    hc = target["conversion"]["hc_eV_angstrom"]
    nm_to_a = target["conversion"]["nm_to_angstrom"]
    lines = []
    for peak in target.get("reference_peaks", []):
        wl = peak["wavelength"]["value"]
        unit = peak["wavelength"]["unit"]
        wl_a = wl * nm_to_a if unit == "nm" else wl
        lines.append(
            f"# target {peak['id']}: {wl:g} {unit} = "
            f"{wl_a:.8f} angstrom = {hc / wl_a:.8f} eV"
        )
    return lines


def build_fac_script(config: dict) -> str:
    """Return a FAC Python script string for one trial."""
    ion = config["ion"]
    fac_input = config["fac_input"]
    conf_space = config["configuration_space"]
    calc = config["calculation_steps"]
    radial = config["radial_potential"]

    l_symbol_map = {str(k): v for k, v in conf_space["l_symbol_map"].items()}
    group_prefix = conf_space["generated_group_prefix"]["bound"]
    group_start = 2

    expanded = []
    template_to_groups = {}
    for template in conf_space["templates"]["bound"]:
        for template_id, fac_config in _expand_template(template, l_symbol_map):
            group = f"{group_prefix}{group_start + len(expanded)}"
            expanded.append((group, template_id, fac_config))
            template_to_groups.setdefault(template_id, []).append(group)

    for fac_config in conf_space.get("manual_fac_configs", {}).get("bound", []):
        group = f"{group_prefix}{group_start + len(expanded)}"
        expanded.append((group, "manual", fac_config))

    bound_groups = [g for g, _, _ in expanded]
    optimize_radial_groups = radial.get("optimize_radial_groups")
    if optimize_radial_groups is None:
        strategies = radial.get("optimize_radial_strategies", [])
        if not strategies:
            raise ValueError("optimize_radial_groups or optimize_radial_strategies must be defined")
        optimize_radial_groups = strategies[0]["groups"]
    optimize_groups = []
    for item in optimize_radial_groups:
        optimize_groups.extend(template_to_groups.get(item, [item]))
    optimize_groups = list(dict.fromkeys(optimize_groups))
    if not optimize_groups:
        raise ValueError("optimize_radial_groups must not be empty")

    prefix = fac_input.get("output_prefix") or f"{ion['element']}{ion['K']:02d}"
    potential_file = fac_input.get("potential_file") or f"{ion['element']}{ion['charge_state']}.pot"
    multipole = calc["transition_table"]["fac_multipole"]
    parallel = fac_input.get("parallel", {})
    openmp = fac_input.get("use_openmp", {})
    nproc = parallel.get("nproc", openmp.get("nproc", 1))

    lines = [
        '"""Generated FAC trial script."""',
        "",
        "import sys",
        "from pfac import fac",
        "from pfac.crm import SetUTA",
        "",
        *_target_peak_comments(config),
        "",
        "parallel_mode = 'serial'",
        "if len(sys.argv) == 2:",
        "    parallel_mode = sys.argv[1]",
        "elif len(sys.argv) > 2:",
        "    raise SystemExit('usage: python trial.py [serial|openmp|mpi]')",
        "",
        "if parallel_mode == 'openmp':",
        f"    fac.InitializeMPI({nproc})",
        "elif parallel_mode == 'mpi':",
        "    fac.InitializeMPI()",
        "elif parallel_mode != 'serial':",
        "    raise SystemExit(f'unknown parallel mode: {parallel_mode}')",
        "",
        f"Z = {ion['Z']}",
        f"K = {ion['K']}",
        "a = fac.ATOMICSYMBOL[Z]",
        f"p = {_quote(prefix)}",
        "",
        "fac.SetAtom(a)",
        f"SetUTA({fac_input['set_uta']})",
        "",
    ]

    closed_shells = fac_input.get("closed_shells", [])
    if closed_shells:
        lines.append(f"fac.Closed({', '.join(_quote(s) for s in closed_shells)})")
    lines.append("")

    for group, template_id, fac_config in expanded:
        lines.append(f"# {template_id}")
        lines.append(f"fac.Config({_quote(fac_config)}, group={_quote(group)})")
    lines.append("")

    lines += [
        "fac.ConfigEnergy(0)",
        f"fac.OptimizeRadial({optimize_groups!r})",
        "fac.ConfigEnergy(1)",
    ]
    if radial.get("save_potential", True):
        lines.append(f"fac.GetPotential({_quote(potential_file)})")
    lines.append("")

    if calc.get("run_structure", True):
        lines += [
            f"fac.Structure(p + 'b.en', {bound_groups!r})",
            "fac.MemENTable(p + 'b.en')",
            "fac.PrintTable(p + 'b.en', p + 'a.en', 1)",
            "",
        ]

    if calc.get("run_transition_table", True):
        if multipole == 0:
            lines += [
                f"fac.SetTransitionMaxE({calc['transition_table']['max_electric_rank_when_summing']})",
                f"fac.SetTransitionMaxM({calc['transition_table']['max_magnetic_rank_when_summing']})",
            ]
        lines += [
            f"fac.TransitionTable(p + 'b.tr', {bound_groups!r}, {bound_groups!r}, {multipole})",
            "fac.PrintTable(p + 'b.tr', p + 'a.tr', 1)",
            "",
        ]

    lines += [
        "if parallel_mode in ('openmp', 'mpi'):",
        "    fac.FinalizeMPI()",
        "",
    ]
    return "\n".join(lines)
