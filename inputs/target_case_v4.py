#!/usr/bin/env python3
"""Self-contained Python input for FAC + ODAT-SE phase-1 search — v4.

Changes from v3:
  - scoring_space = "wavelength": residuals are computed in Angstrom instead
    of eV.  The default shift mode now checks per-peak wavelength shift
    consistency instead of forcing one exact global shift.
  - fwhm_angstrom replaces fwhm_eV in DEFAULT_PEAK so the window width is
    uniform in wavelength across all peaks rather than uniform in energy.
  - prefilter_window_eV is enlarged to cover the Gaussian window at the
    shortest wavelength in the list.
  - max_shift_spread_angstrom replaces sanity_range_eV in GLOBAL_SHIFT.
  - position_weight is scaled up so the residual^2 term (now in Angstrom^2)
    competes meaningfully with the -log(score) strength term.
  - min_A_value can be used to discard lines too weak to be observed.

All other logic (configurations, OptimizeRadial, selection constraints,
forward_selection / grid_search) is identical to v3.
"""

import re


# ---------------------------------------------------------------------------
# User inputs
# ---------------------------------------------------------------------------

REFERENCE_PEAKS = [
    5.69,
    5.87,
    7.0262,
    7.1733,
    7.9280,
]

# fwhm_angstrom sets the Gaussian half-width in wavelength space.
# A value of 0.1 A is a reasonable starting point for EUV/soft-X-ray lines.
# If you prefer to specify in energy, set fwhm_angstrom=None and fwhm_eV instead;
# the scoring code converts automatically using |dE/dlambda| at each peak.
DEFAULT_PEAK = {
    "unit": "angstrom",
    "fwhm_eV": None,
    "fwhm_angstrom": 0.1,   # Angstrom; uniform wavelength window across all peaks
    "fwhm_nm": None,
    "sigma_eV": None,
    "type": "anchor",
}

ION = {
    "element": "W",
    "Z": 74,
    "charge_state": 46,
    "K": 28,
}

FAC_INPUT = {
    "output_prefix": None,
    "potential_file": None,
    "closed_shells": ["1s", "2s", "2p", "3s"],
    "set_uta": 0,
    "parallel": {
        "mode": "serial",
        "nproc": 16,
        "launcher": "mpirun",
        "nproc_flag": "-np",
        "launcher_args": [],
    },
}

# Default expansion for configurations ending with " nl" or " mk".
# The generator enforces l <= n - 1 / k <= m - 1.
DEFAULT_NL = {
    "n": [4, 5, 6, 7],
    "l": [0, 1, 2, 3, 4, 5, 6],
    "m": [5, 6, 7, 8],
    "k": [0, 1, 2, 3, 4, 5, 6, 7],
    "occupancy": 1,
}

CONFIGURATIONS = [
    {
        "config": "3p6 3d10",
        "required": True,
        "optimize_radial": True,
        "optimize_radial_base": True,
        "potential_label": "ground",
    },
    {
        "config": "3p6 3d9 nl",
        "required": True,
        "optimize_radial": True,
        "optimize_radial_base": True,
        "potential_label": "target_excited",
    },
    {
        "config": "3p5 3d10 nl",
        "required": True,
        "optimize_radial": True,
    },
    {
        "config": "3p6 3d8 4s2",
        "required": False,
        "optimize_radial": True,
    },
    {
        "config": "3p5 3d9 4s2",
        "required": False,
        "optimize_radial": True,
    },
]

SELECTION_CONSTRAINTS = {
    "require_contiguous_shell_occupancies": True,
    "max_shell_hole_depth_without_bridge": 2,
}

SELECTION_RULES = []

# "auto" uses configuration-level potential annotations:
#   required               -> controls whether this configuration is included
#                             in every FAC calculation trial.
#   optimize_radial        -> controls whether this configuration may be used
#                             by OptimizeRadial strategies.
#   optimize_radial_base   -> marks a potential starting point.  If multiple
#                             bases are marked, auto compares them separately.
OPTIMIZE_RADIAL = "auto"
OPTIMIZE_RADIAL_BASE = "first_required"

RUN_NAMING = {
    "version": "v4",
    "ion_label": None,
    "work_dir": None,
    "generated_dir": None,
    "results_file": None,
}

SEARCH = {
    "method": "grid_search",
    "run_fac": True,
    "keep_generated_scripts": True,
    "timeout_seconds_per_trial": None,
    "forward_selection": {"min_loss_improvement": 0.0, "max_rounds": None},
    "scoring": {
        "use_gaussian_soft_window": True,
        # "energy"     -> Gaussian and residual in eV   (v3 behaviour)
        # "wavelength" -> Gaussian and residual in Angstrom (v4 default)
        "scoring_space": "wavelength",
        # Energy-space pre-filter applied before the wavelength Gaussian.
        # Must be large enough to cover the Gaussian window at the shortest
        # peak wavelength.  For fwhm_angstrom=0.1 A at ~5.7 A (2180 eV):
        #   dE = hc * dlambda / lambda^2 = 12398 * 0.3 / 5.7^2 ~ 115 eV (3 sigma)
        # 200 eV gives comfortable headroom for all peaks in the list.
        "prefilter_window_eV": 200.0,
        # Use "A" or "(2J+1)*A".  Population is not included at this stage,
        # so this is only a radiative-potential proxy.
        "radiative_weight": "(2J+1)*A",
        "rate_floor": 1.0e-99,
        "min_A_value": None,   # s^-1; e.g. 1e8 to discard very weak lines
        # Used only by GLOBAL_SHIFT mode "per_peak_consistency".  This should
        # be wide enough to include line groups that may need a sizeable common
        # wavelength shift before later-stage refinement.
        "local_shift_search_window_angstrom": 5.0,
        # Once candidates are found inside the large search window, score each
        # peak against the strongest local line group rather than averaging all
        # lines across the whole shift-search window.
        "local_line_group_window_angstrom": 0.1,
        "max_local_shift_groups_per_peak": 12,
    },
}

# position_weight scaling note:
#   In wavelength mode the residual^2 term is in Angstrom^2 (typical ~0.01 A^2),
#   while -log(score) is dimensionless (~10-20 for a strong E1 line).
#   Set position_weight ~ 1e3 to give both terms comparable magnitude.
#   Increase it further to penalise positional mismatches more strongly.
LOSS = {
    "position_weight": 1000.0,
    "strength_weight": 1.0,
    "anchor_weight": 1.0,
    "ambiguous_weight": 0.3,
    "complexity": {"enabled": True, "per_optional_template": 2.0},
    "missing_peak_penalty": 1000000.0,
}

# mode = "per_peak_consistency":
#   each peak gets its own wavelength shift,
#     shift_p = lambda_exp,p - lambda_center,p
#   and the trial survives if the shifts have the same direction and
#     max(shift_p) - min(shift_p) <= max_shift_spread_angstrom.
# For example, shifts of +3.0 A and +2.6 A pass with a 0.5 A spread limit.
GLOBAL_SHIFT = {
    "enabled": True,
    "mode": "per_peak_consistency",
    "require_consistent_direction": True,
    "direction_zero_tolerance_angstrom": 1.0e-6,
    "max_shift_spread_angstrom": 0.5,
    # Set this only if an absolute shift bound is desired.  Leaving it as None
    # allows large common offsets during phase-1 screening.
    "max_abs_shift_angstrom": None,
}


# ---------------------------------------------------------------------------
# Derived config consumed by scripts. Usually no edits are needed below.
# ---------------------------------------------------------------------------

L_SYMBOL_MAP = {0: "s", 1: "p", 2: "d", 3: "f", 4: "g", 5: "h", 6: "i", 7: "k"}
HC_EV_ANGSTROM = 12398.419843320026
NM_TO_ANGSTROM = 10.0


def _slug(text: str) -> str:
    text = text.replace("+", "plus").replace("-", "minus")
    text = re.sub(r"[^0-9A-Za-z]+", "_", text.strip())
    text = re.sub(r"_+", "_", text).strip("_").lower()
    return text or "item"


def _unique_id(base, used):
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def _peak_id(wavelength, unit, used):
    compact = f"{wavelength:g}".replace(".", "p")
    suffix = "A" if unit == "angstrom" else unit
    return _unique_id(f"peak_{compact}{suffix}", used)


def _normalize_peak(entry, used_ids):
    if isinstance(entry, (int, float)):
        raw = {"wavelength": float(entry)}
    else:
        raw = dict(entry)

    data = {**DEFAULT_PEAK, **raw}
    unit = data.get("wavelength_unit", data.get("unit", DEFAULT_PEAK["unit"]))
    wavelength = data["wavelength"]
    wavelength_angstrom = wavelength * NM_TO_ANGSTROM if unit == "nm" else wavelength

    if "fwhm_eV" in raw and raw["fwhm_eV"] is not None:
        fwhm_eV = raw["fwhm_eV"]
    else:
        fwhm_angstrom = raw.get("fwhm_angstrom")
        if fwhm_angstrom is None and raw.get("fwhm_nm") is not None:
            fwhm_angstrom = raw["fwhm_nm"] * NM_TO_ANGSTROM
        if fwhm_angstrom is None:
            fwhm_angstrom = DEFAULT_PEAK.get("fwhm_angstrom")
        if fwhm_angstrom is None and DEFAULT_PEAK.get("fwhm_nm") is not None:
            fwhm_angstrom = DEFAULT_PEAK["fwhm_nm"] * NM_TO_ANGSTROM
        if fwhm_angstrom is not None:
            fwhm_eV = HC_EV_ANGSTROM * fwhm_angstrom / (wavelength_angstrom * wavelength_angstrom)
        else:
            fwhm_eV = DEFAULT_PEAK.get("fwhm_eV")

    return {
        "id": data.get("id") or _peak_id(wavelength, unit, used_ids),
        "wavelength": {"value": wavelength, "unit": unit},
        "fwhm_eV": fwhm_eV,
        "sigma_eV": data.get("sigma_eV"),
        "type": data.get("type", "anchor"),
    }


def _normalize_configuration(entry, index, used_ids):
    if isinstance(entry, str):
        data = {"config": entry}
    else:
        data = dict(entry)

    config = data["config"].strip()
    tokens = config.split()
    active = tokens[-1] if tokens and tokens[-1] in ("nl", "mk") else None
    prefix = " ".join(tokens[:-1]) if active else config
    base = _slug(prefix + (f" {active}" if active else ""))

    tags = set(data.get("tags", []))
    for token in config.split():
        if re.match(r"^[0-9]+[A-Za-z]+[0-9]+$", token):
            tags.add(token)

    template = {
        "id": data.get("id") or _unique_id(base, used_ids),
        "prefix": prefix,
        "active": active,
        "required": data.get("required", index == 0),
        "optimize_radial": bool(data.get(
            "optimize_radial",
            data.get("use_for_potential", data.get("potential", True)),
        )),
        "optimize_radial_base": bool(data.get(
            "optimize_radial_base",
            data.get("potential_base", False),
        )),
        "potential_label": data.get("potential_label"),
        "tags": sorted(tags),
    }
    group_by = data.get("group_by", globals().get("ACTIVE_GROUP_BY", {}).get(active))
    if group_by is not None:
        template["group_by"] = group_by
    if active == "nl":
        template["n"] = list(data.get("n", DEFAULT_NL["n"]))
        template["l"] = list(data.get("l", DEFAULT_NL["l"]))
        template["occupancy"] = data.get("occupancy", DEFAULT_NL["occupancy"])
    elif active == "mk":
        template["m"] = list(data.get("m", DEFAULT_NL.get("m", DEFAULT_NL["n"])))
        template["k"] = list(data.get("k", DEFAULT_NL.get("k", DEFAULT_NL["l"])))
        template["occupancy"] = data.get("occupancy", DEFAULT_NL["occupancy"])
    return template


def _potential_templates(templates):
    return [item for item in templates if item.get("optimize_radial", True)]


def _potential_label(template):
    return template.get("potential_label") or template["id"]


def _optimize_radial_base_ids(templates):
    required = [item for item in templates if item.get("required", False)]
    if not required:
        raise ValueError("OPTIMIZE_RADIAL='auto' requires at least one required configuration")

    marked = [item for item in templates if item.get("optimize_radial_base", False)]
    if marked:
        disabled = [item["id"] for item in marked if not item.get("optimize_radial", True)]
        if disabled:
            raise ValueError(
                "Configurations marked optimize_radial_base=True must also have "
                f"optimize_radial=True: {disabled}"
            )
        return [[item["id"]] for item in marked]

    base = OPTIMIZE_RADIAL_BASE
    if base == "first_required":
        return [[required[0]["id"]]]
    if base == "all_required":
        return [[item["id"] for item in required]]

    if isinstance(base, str):
        requested = [base]
    else:
        requested = list(base)

    resolved = []
    for item in requested:
        matches = [
            template["id"]
            for template in templates
            if item == template["id"] or item in template.get("tags", [])
        ]
        if not matches:
            raise ValueError(f"Unknown OPTIMIZE_RADIAL_BASE item {item!r}")
        for match in matches:
            if match not in resolved:
                resolved.append(match)
    return [resolved]


def _auto_optimize_radial_strategies(templates):
    base_groups_list = _optimize_radial_base_ids(templates)
    potential_templates = _potential_templates(templates)
    template_by_id = {item["id"]: item for item in templates}
    strategies = []
    seen = set()

    for base_ids in base_groups_list:
        base_set = set(base_ids)
        if any(template_id not in {item["id"] for item in potential_templates} for template_id in base_ids):
            raise ValueError(f"OptimizeRadial base includes non-potential template(s): {base_ids}")

        base_label = "_plus_".join(_potential_label(template_by_id[item]) for item in base_ids)
        strategy = {
            "id": f"{base_label}_only",
            "groups": base_ids,
            "description": f"Optimize on {base_label} configurations only",
            "requires_templates": base_ids,
        }
        key = tuple(sorted(strategy["groups"]))
        if key not in seen:
            strategies.append(strategy)
            seen.add(key)

        for item in potential_templates:
            if item["id"] in base_set:
                continue
            groups = base_ids + [item["id"]]
            key = tuple(sorted(groups))
            if key in seen:
                continue
            partner_label = _potential_label(item)
            strategies.append(
                {
                    "id": f"{base_label}_plus_{partner_label}",
                    "groups": groups,
                    "description": f"Optimize on {base_label} + {item['prefix']}",
                    "requires_templates": groups,
                }
            )
            seen.add(key)
    return strategies


def _optimize_radial_strategies(templates):
    if OPTIMIZE_RADIAL == "auto":
        return _auto_optimize_radial_strategies(templates)
    return [dict(item) for item in OPTIMIZE_RADIAL]


def _run_label():
    ion_label = RUN_NAMING.get("ion_label")
    if ion_label is None:
        ion_label = "{}{}".format(ION["element"], ION["charge_state"])
    version = RUN_NAMING.get("version")
    if version:
        return "{}_{}".format(ion_label, version)
    return ion_label


def _search_paths():
    label = _run_label()
    work_dir = RUN_NAMING.get("work_dir") or "runs/search_{}".format(label)
    generated_dir = RUN_NAMING.get("generated_dir") or "generated/search_{}".format(label)
    results_file = RUN_NAMING.get("results_file") or "{}/results.txt".format(work_dir)
    return {
        "work_dir": work_dir,
        "generated_dir": generated_dir,
        "results_file": results_file,
    }


def _fac_output_prefix():
    return FAC_INPUT.get("output_prefix") or "{}{}".format(ION["element"], ION["K"])


def _fac_potential_file():
    return FAC_INPUT.get("potential_file") or "{}{}.pot".format(
        ION["element"],
        ION["charge_state"],
    )


def build_config():
    peak_ids = set()
    template_ids = set()
    peaks = [_normalize_peak(entry, peak_ids) for entry in REFERENCE_PEAKS]
    templates = [
        _normalize_configuration(entry, index, template_ids)
        for index, entry in enumerate(CONFIGURATIONS)
    ]

    return {
        "target": {
            "reference_peaks": peaks,
            "conversion": {
                "hc_eV_angstrom": HC_EV_ANGSTROM,
                "nm_to_angstrom": NM_TO_ANGSTROM,
            },
        },
        "ion": dict(ION),
        "fac_input": {
            "reference_style": "Bi22.py",
            "output_prefix": _fac_output_prefix(),
            "potential_file": _fac_potential_file(),
            "parallel": dict(FAC_INPUT["parallel"]),
            "use_openmp": {
                "enabled": FAC_INPUT["parallel"]["mode"] == "openmp",
                "nproc": FAC_INPUT["parallel"]["nproc"],
            },
            "set_uta": FAC_INPUT["set_uta"],
            "closed_shells": list(FAC_INPUT["closed_shells"]),
        },
        "configuration_space": {
            "mode": "iterative_templates",
            "generated_group_prefix": {"bound": "n", "ionization": "i"},
            "include_ionization_groups": False,
            "templates": {"bound": templates, "ionization": []},
            "l_symbol_map": dict(L_SYMBOL_MAP),
        },
        "radial_potential": {
            "optimize_radial_strategies": _optimize_radial_strategies(templates),
            "save_potential": True,
        },
        "global_shift": dict(GLOBAL_SHIFT),
        "search": {
            "enabled": True,
            "require_all_required_templates": True,
            "vary_optional_templates": True,
            "vary_optimize_radial_strategies": True,
            "selection_constraints": dict(SELECTION_CONSTRAINTS),
            "selection_rules": [dict(rule) for rule in SELECTION_RULES],
            "stop_on_configuration": {"enabled": False, "exact_template_ids": []},
            **_search_paths(),
            **SEARCH,
        },
        "loss": dict(LOSS),
        "calculation_steps": {
            "run_structure": True,
            "run_transition_table": True,
            "transition_table": {
                "fac_multipole": 0,
                "max_electric_rank_when_summing": 3,
                "max_magnetic_rank_when_summing": 3,
            },
        },
    }


CONFIG = build_config()
