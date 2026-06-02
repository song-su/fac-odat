#!/usr/bin/env python3
"""Compact Python input for FAC + ODAT-SE phase-1 search.

Only edit the "User inputs" section in normal use. Internal ids, peak ids,
nl expansion, and OptimizeRadial strategies are generated automatically.
"""

import re


# ---------------------------------------------------------------------------
# User inputs
# ---------------------------------------------------------------------------

# Experimental wavelengths. A plain number uses DEFAULT_PEAK below.
#
# If the real experimental peak width is known and all peaks use the same
# width, edit DEFAULT_PEAK below. You can use an energy width:
#   "fwhm_eV": 3.0
# or a wavelength width:
#   "fwhm_angstrom": 0.01
#   "fwhm_nm": 0.001
#
# If only one peak has a different measured width, write that peak as a dict:
#   {"wavelength": 5.69, "fwhm_angstrom": 0.01}
# The program uses sigma_eV directly if provided; otherwise it derives
# sigma_eV = fwhm_eV / 2.355.
#
# Use a dict also when a peak should be weakly weighted:
#   {"wavelength": 7.9280, "type": "ambiguous"}
REFERENCE_PEAKS = [
    5.69,
    5.87,
    7.0262,
    7.1733,
    7.9280,
]

DEFAULT_PEAK = {
    "unit": "angstrom",
    # Replace this with the measured experimental FWHM when available.
    # If your measured width is in wavelength units, prefer fwhm_angstrom or
    # fwhm_nm. The program converts it to eV near each peak center.
    # This controls the Gaussian soft window around each experimental peak.
    "fwhm_eV": 3.0,
    "fwhm_angstrom": None,
    "fwhm_nm": None,
    # Leave as None unless you already know sigma in eV.
    "sigma_eV": None,
    # "anchor" is a strong constraint; use "ambiguous" for uncertain/blended
    # peaks whose FAC-only assignment should have weaker influence.
    "type": "anchor",
}

ION = {
    "element": "W",
    "Z": 74,
    "charge_state": 46,
    "K": 28,
}

FAC_INPUT = {
    # Leave as None to derive from ION:
    #   output_prefix -> "{element}{K}", e.g. "W28"
    #   potential_file -> "{element}{charge_state}.pot", e.g. "W46.pot"
    "output_prefix": None,
    "potential_file": None,
    "closed_shells": ["1s", "2s", "2p", "3s"],
    "set_uta": 0,
    # Parallel execution mode for each FAC trial:
    #   "serial" : python trial.py
    #   "openmp" : python trial.py openmp
    #              uses fac.InitializeMPI(nproc), for FAC built with --with-mpi=omp
    #   "mpi"    : mpirun -np nproc python trial.py mpi
    #              uses fac.InitializeMPI(), for FAC built with real MPI support
    "parallel": {
        "mode": "serial",
        "nproc": 16,
        "launcher": "mpirun",
        "nproc_flag": "-np",
        "launcher_args": [],
    },
}

# Default expansion for any configuration ending with " nl" or " mk".
# The generator automatically enforces l <= n - 1 / k <= m - 1,
# so n=4 will not generate 4g and m=5 will not generate 5h.
DEFAULT_NL = {
    "n": [4, 5, 6, 7],
    "l": [0, 1, 2, 3, 4, 5, 6],
    "m": [5, 6, 7, 8],
    "k": [0, 1, 2, 3, 4, 5, 6, 7],
    "occupancy": 1,
}

# Reference configurations. The first entry is required by default; later
# entries are optional by default. Add/remove strings freely.
#
# Examples:
#   "3p6 3d10"       -> one FAC configuration
#   "3p6 3d9 nl"     -> expands with DEFAULT_NL
#   "3p6 3d9 mk"     -> expands with DEFAULT_NL["m"] and DEFAULT_NL["k"]
#   {"config": "3p6 3d9 nl", "n": [4, 5], "l": [0, 1, 2]}
#   {"config": "3p6 3d9 mk", "m": [5, 6], "k": [0, 1, 2]}
CONFIGURATIONS = [
    "3p6 3d10",
    "3p6 3d9 nl",
    "3p5 3d10 nl",
    "3p6 3d8 4s2",
    "3p5 3d9 4s2",
]

# Optional logical constraints between configuration templates.  Shell tags
# such as "4f13" are generated automatically from each configuration string;
# explicit tags may also be supplied on a configuration dict.
#
# Generic shell-occupancy rules:
#   require_contiguous_shell_occupancies:
#     If selected configurations contain the same subshell with two different
#     occupancies, the intermediate occupancies must also be selected.  Thus
#     4d10 + 4d8 requires 4d9; 4f6 + 4f4 requires 4f5.
#   max_shell_hole_depth_without_bridge:
#     Relative to the highest occupancy of a subshell available in this input,
#     a deeper occupancy may not appear by itself when it is more than this
#     many electrons lower.  With the default 2, 4f11 in an input that also
#     contains 4f14 must be accompanied by 4f12 or 4f13.
SELECTION_CONSTRAINTS = {
    "require_contiguous_shell_occupancies": True,
    "max_shell_hole_depth_without_bridge": 2,
}

# Additional custom rules are checked against selected template ids and tags.
#
# Example:
#   SELECTION_RULES = [
#       {
#           "id": "4f11_needs_nearby_core",
#           "if_any": ["4f11"],
#           "require_any": ["4f13", "4f12"],
#       },
#       {
#           "id": "4f11_4f13_needs_4f12",
#           "if_all": ["4f11", "4f13"],
#           "require_all": ["4f12"],
#       },
#   ]
SELECTION_RULES = []

# "auto" means:
#   1. OptimizeRadial on OPTIMIZE_RADIAL_BASE.
#   2. Also try OPTIMIZE_RADIAL_BASE + each other configuration template.
# Advanced users may replace this with explicit dict strategies if needed.
OPTIMIZE_RADIAL = "auto"

# Potential optimization start point for OPTIMIZE_RADIAL = "auto".
#
#   "first_required" : start from only the first required template, usually
#                      the ground configuration.  This is the default.
#   "all_required"   : old behavior; start from all required templates.
#   ["template_id"]  : start from an explicit combination.  Items may be
#                      template ids or tags such as "4f14".
OPTIMIZE_RADIAL_BASE = "first_required"

# Output directory names are generated from ION by default.  For example,
# W charge_state 46 with version "v2" becomes search_W46_v2.
RUN_NAMING = {
    "version": "v2",
    # Leave as None to use "{element}{charge_state}", e.g. "W46".
    "ion_label": None,
    # Set any of these to a string only when you need a custom location.
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
        "prefilter_window_eV": 15.0,
        "radiative_weight": "(2J+1)*A",
        "rate_floor": 1.0e-99,
    },
}

LOSS = {
    "position_weight": 1.0,
    "strength_weight": 1.0,
    "anchor_weight": 1.0,
    "ambiguous_weight": 0.3,
    "complexity": {"enabled": True, "per_optional_template": 2.0},
    "missing_peak_penalty": 1000000.0,
}

GLOBAL_SHIFT = {
    "enabled": True,
    "optimize_analytically": True,
    "sanity_range_eV": [-12.0, 12.0],
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

    if "fwhm_eV" in raw:
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
            # Narrow-peak conversion from E = hc / lambda:
            # |dE| = hc / lambda^2 * |d lambda|.
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
        "tags": sorted(tags),
    }
    if active == "nl":
        template["n"] = list(data.get("n", DEFAULT_NL["n"]))
        template["l"] = list(data.get("l", DEFAULT_NL["l"]))
        template["occupancy"] = data.get("occupancy", DEFAULT_NL["occupancy"])
    elif active == "mk":
        template["m"] = list(data.get("m", DEFAULT_NL.get("m", DEFAULT_NL["n"])))
        template["k"] = list(data.get("k", DEFAULT_NL.get("k", DEFAULT_NL["l"])))
        template["occupancy"] = data.get("occupancy", DEFAULT_NL["occupancy"])
    return template


def _auto_optimize_radial_strategies(templates):
    base_ids = _optimize_radial_base_ids(templates)
    base_set = set(base_ids)
    strategies = [
        {
            "id": "base_only",
            "groups": base_ids,
            "description": "Optimize on base configurations only",
        }
    ]
    for item in templates:
        if item["id"] in base_set:
            continue
        strategies.append(
            {
                "id": f"base_plus_{item['id']}",
                "groups": base_ids + [item["id"]],
                "description": f"Optimize on base configurations + {item['prefix']}",
                "requires_templates": [item["id"]],
            }
        )
    return strategies


def _optimize_radial_base_ids(templates):
    required = [item for item in templates if item.get("required", False)]
    if not required:
        raise ValueError("OPTIMIZE_RADIAL='auto' requires at least one required configuration")

    base = OPTIMIZE_RADIAL_BASE
    if base == "first_required":
        return [required[0]["id"]]
    if base == "all_required":
        return [item["id"] for item in required]

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
    return resolved


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
    default_work_dir = "runs/search_{}".format(label)
    work_dir = RUN_NAMING.get("work_dir") or default_work_dir
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
