#!/usr/bin/env python3
"""FAC survey configuration for Pd-like I7+ (Z=53, 46 electrons).

Edit this file to change parameters for an I7+ survey:
  - KNOWN_PEAKS  : known transitions (exp_nm, paper_fac_nm, config, J) — scoring targets
  - BASE_CONFIG  : FAC hidden-shell occupancies for config label reconstruction
  - CONFIGURATIONS : configuration families passed to FAC
  - OPTIMIZE_RADIAL: hand-picked OptimizeRadial strategy list (survey enumerates all subsets)
  - ION / FAC_INPUT: atomic and FAC run parameters

Reference: Kimura et al., PRA 102, 032807 (2020).
"""

import re

from survey.peaks import KnownPeak


# ---------------------------------------------------------------------------
# Physical data — edit these when changing ions or reference wavelengths.
# ---------------------------------------------------------------------------

# FAC hides shells at block-reference occupancy in short config labels.
# BASE_CONFIG lets the scorer reconstruct full config strings.
BASE_CONFIG = {"4p": 6, "4d": 10}

# Known spectral features from Table I (Kimura et al. 2020).
# exp_nm      : experimental wavelength
# paper_fac_nm: FAC theoretical wavelength (λ_th) — used as the scoring target
# upper_config / lower_config / upper_2j / lower_2j : jj-coupling assignment
# Line c (4d-1_5/2 5p3/2, 19.6547 nm) excluded — large theory/experiment gap.
KNOWN_PEAKS = [
    # a: (4d^-1_{5/2} 5s_{1/2})_J=2  E2 -> 4d10 (J=0)
    KnownPeak(
        peak_id="a_4d9_5s_E2",
        exp_nm=26.21, paper_fac_nm=26.24,
        upper_config="4d9.5s1", lower_config="4d10",
        upper_2j=4, lower_2j=0,
        multipole="E2", note="(4d-1_5/2 5s_1/2) J=2 -> 4d10",
    ),
    # b: (4d^-1_{3/2} 5s_{1/2})_J=2  E2 -> 4d10 (J=0)
    KnownPeak(
        peak_id="b_4d9_5s_E2",
        exp_nm=25.27, paper_fac_nm=25.27,
        upper_config="4d9.5s1", lower_config="4d10",
        upper_2j=4, lower_2j=0,
        multipole="E2", note="(4d-1_3/2 5s_1/2) J=2 -> 4d10",
    ),
    # d: (4d^-1_{3/2} 5p_{1/2})_J=1  E1 -> 4d10 (J=0)
    KnownPeak(
        peak_id="d_4d9_5p_E1",
        exp_nm=19.42, paper_fac_nm=19.45,
        upper_config="4d9.5p1", lower_config="4d10",
        upper_2j=2, lower_2j=0,
        multipole="E1", note="(4d-1_3/2 5p_1/2) J=1 -> 4d10",
    ),
    # e: (4d^-1_{3/2} 5p_{3/2})_J=1  E1 -> 4d10 (J=0)
    KnownPeak(
        peak_id="e_4d9_5p_E1",
        exp_nm=19.02, paper_fac_nm=19.09,
        upper_config="4d9.5p1", lower_config="4d10",
        upper_2j=2, lower_2j=0,
        multipole="E1", note="(4d-1_3/2 5p_3/2) J=1 -> 4d10",
    ),
    # f: (4d^-1_{5/2} 4f_{5/2})_J=1  E1 -> 4d10 (J=0)
    KnownPeak(
        peak_id="f_4d9_4f_E1",
        exp_nm=16.44, paper_fac_nm=16.56,
        upper_config="4d9.4f1", lower_config="4d10",
        upper_2j=2, lower_2j=0,
        multipole="E1", note="(4d-1_5/2 4f_5/2) J=1 -> 4d10",
    ),
    # g: (4d^-1_{3/2} 4f_{5/2})_J=1  E1 -> 4d10 (J=0)
    KnownPeak(
        peak_id="g_4d9_4f_E1",
        exp_nm=15.71, paper_fac_nm=15.77,
        upper_config="4d9.4f1", lower_config="4d10",
        upper_2j=2, lower_2j=0,
        multipole="E1", note="(4d-1_3/2 4f_5/2) J=1 -> 4d10",
    ),
]

DEFAULT_PEAK = {
    "unit": "nm",
    "fwhm_eV": 0.2,
    "fwhm_angstrom": None,
    "fwhm_nm": None,
    "sigma_eV": None,
    "type": "anchor",
}

ION = {
    "element": "W",
    "Z": 53,
    "charge_state": 7,
    "K": 46,
}

FAC_INPUT = {
    "output_prefix": None,
    "potential_file": None,
    "closed_shells": ["1s", "2s", "2p", "3s", "3p", "3d", "4s"],
    "set_uta": 0,
    "parallel": {
        "mode": "openmp",
        "nproc": 12,
        "launcher": "mpirun",
        "nproc_flag": "-np",
        "launcher_args": [],
    },
}

DEFAULT_NL = {
    "n": [5, 6],
    "l": [0, 1, 2, 3],
    "m": [5, 6, 7, 8],
    "k": [0, 1, 2, 3, 4, 5, 6, 7],
    "occupancy": 1,
}

# Active-orbital grouping for generated FAC groups in the same input:
#   nl: "n" keeps 5[s,p,d,f] together; "l" splits 5s, 5p, 5d, 5f.
#   mk: "m" keeps m[...] together; "k" splits each m/k subshell.
ACTIVE_GROUP_BY = {
    "nl": "n",
    "mk": "m",
}

# All configurations are required=True (fixed set); only OptimizeRadial varies.
CONFIGURATIONS = [
    {
        "config": "4p6 4d10",
        "required": True,
        "optimize_radial": True,
    },
    {
        "config": "4p6 4d9 4f",
        "required": True,
        "optimize_radial": True,
    },
    {
        "config": "4p6 4d9 nl",
        "group_by": ACTIVE_GROUP_BY["nl"],
        "required": True,
        "optimize_radial": True,
    },
    {
        "config": "4p5 4d10 4f",
        "required": True,
        "optimize_radial": True,
    },
    {
        "config": "4p5 4d10 5l",
        "group_by": ACTIVE_GROUP_BY["nl"],
        "required": True,
        "optimize_radial": True,
    },
    {
        "config": "4p6 4d8 5s2",
        "required": True,
        "optimize_radial": True,
    },
    {
        "config": "4p6 4d8 5p2",
        "required": True,
        "optimize_radial": True,
    },
    {
        "config": "4p6 4d8 5d2",
        "required": True,
        "optimize_radial": True,
    },
    {
        "config": "4p6 4d8 5s1 5p1",
        "required": True,
        "optimize_radial": True,
    },
]

SELECTION_CONSTRAINTS = {
    "require_contiguous_shell_occupancies": True,
    "max_shell_hole_depth_without_bridge": 2,
}

SELECTION_RULES = []

# Manual strategy list: each group alone + key combinations + all-average.
# Template IDs match the slugs generated by _normalize_configuration().
OPTIMIZE_RADIAL = [
    # ---- Single-configuration potentials ----
    {
        "id": "ground_only",
        "groups": ["4p6_4d10"],
        "description": "Optimize on ground state only",
    },
    {
        "id": "4d9_4f_only",
        "groups": ["4p6_4d9_4f"],
        "description": "Optimize on 4d-1 4f only",
    },
    {
        "id": "4d9_nl_only",
        "groups": ["4p6_4d9_nl"],
        "description": "Optimize on 4d-1 nl (n=5,6) only",
    },
    {
        "id": "4p5_4d10_4f_only",
        "groups": ["4p5_4d10_4f"],
        "description": "Optimize on 4p-1 4f only",
    },
    {
        "id": "4p5_4d10_5l_only",
        "groups": ["4p5_4d10_5l"],
        "description": "Optimize on 4p-1 5l only",
    },
    {
        "id": "4d8_5s2_only",
        "groups": ["4p6_4d8_5s2"],
        "description": "Optimize on 4d-2 5s2 only",
    },
    {
        "id": "4d8_5p2_only",
        "groups": ["4p6_4d8_5p2"],
        "description": "Optimize on 4d-2 5p2 only",
    },
    {
        "id": "4d8_5d2_only",
        "groups": ["4p6_4d8_5d2"],
        "description": "Optimize on 4d-2 5d2 only",
    },
    {
        "id": "4d8_5s5p_only",
        "groups": ["4p6_4d8_5s1_5p1"],
        "description": "Optimize on 4d-2 5s5p only",
    },
    # ---- Physically motivated combinations ----
    {
        "id": "ground_plus_4d9_nl",
        "groups": ["4p6_4d10", "4p6_4d9_nl"],
        "description": "Ground + main E1 upper levels (4d-1 nl)",
    },
    {
        "id": "ground_plus_4d9_4f_nl",
        "groups": ["4p6_4d10", "4p6_4d9_4f", "4p6_4d9_nl"],
        "description": "Ground + full 4d-hole single-excitation family",
    },
    # ---- FAC Average-Level: all configurations at once ----
    {
        "id": "all_configs_average",
        "groups": [
            "4p6_4d10", "4p6_4d9_4f", "4p6_4d9_nl",
            "4p5_4d10_4f", "4p5_4d10_5l",
            "4p6_4d8_5s2", "4p6_4d8_5p2", "4p6_4d8_5d2", "4p6_4d8_5s1_5p1",
        ],
        "description": "FAC Average-Level: optimize on all bound configurations",
    },
]

OPTIMIZE_RADIAL_BASE = "first_required"

RUN_NAMING = {
    "version": "v4_survey",
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
        "scoring_space": "wavelength",
        "prefilter_window_eV": 200.0,
        "radiative_weight": "(2J+1)*A",
        "rate_floor": 1.0e-99,
        "min_A_value": None,
        # Search window in wavelength space for each reference peak.
        # 5 A covers the ~3-4 A offsets seen with ground_only potential.
        "local_shift_search_window_angstrom": 5.0,
        "local_line_group_window_angstrom": 0.1,
        "max_local_shift_groups_per_peak": 12,
    },
}

# Calibration loss: L = position_weight * sum(local_shift_p^2).
# strength_weight = 0 -> pure positional calibration, easy to interpret:
#   loss / position_weight / n_peaks = mean squared wavelength error in A^2.
# E.g. ground_only with ~3.6 A shift: 100 * 3.6^2 * 6 ~ 7776
#      paper-matching potential with ~0.3 A shift: 100 * 0.3^2 * 6 ~ 54
LOSS = {
    "position_weight": 100.0,
    "strength_weight": 0.0,
    "anchor_weight": 1.0,
    "ambiguous_weight": 0.3,
    "complexity": {"enabled": False, "per_optional_template": 0.0},
    "missing_peak_penalty": 1000000.0,
}

# calibration_mode=True: bypass shift-consistency filter; each peak
# independently selects the closest FAC line group (smallest |lambda_FAC -
# lambda_ref|).  max_shift_spread_nm and require_consistent_direction are
# ignored in this mode.
GLOBAL_SHIFT = {
    "enabled": True,
    "mode": "per_peak_consistency",
    "calibration_mode": True,
    "require_consistent_direction": False,
    "direction_zero_tolerance_angstrom": 1.0e-6,
    "max_shift_spread_nm": 10.0,
    "max_abs_shift_angstrom": None,
}


# ---------------------------------------------------------------------------
# Derived config — same boilerplate as v4_I.py, no user edits needed below.
# ---------------------------------------------------------------------------

L_SYMBOL_MAP = {0: "s", 1: "p", 2: "d", 3: "f", 4: "g", 5: "h", 6: "i", 7: "k"}
HC_EV_ANGSTROM = 12398.419843320026
NM_TO_ANGSTROM = 10.0


def _slug(text):
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
            fwhm_eV = HC_EV_ANGSTROM * fwhm_angstrom / (wavelength_angstrom ** 2)
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
    last_token = tokens[-1] if tokens else ""

    _fixed_nl = re.match(r"^(\d+)l$", last_token)
    _fixed_mk = re.match(r"^(\d+)k$", last_token)
    if last_token in ("nl", "mk"):
        active = last_token
    elif _fixed_nl:
        active = "nl"
    elif _fixed_mk:
        active = "mk"
    else:
        active = None

    prefix = " ".join(tokens[:-1]) if active else config
    base = _slug(prefix + (f" {last_token}" if active else ""))

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
        "optimize_radial_base": bool(data.get("optimize_radial_base", False)),
        "potential_label": data.get("potential_label"),
        "tags": sorted(tags),
    }
    group_by = data.get("group_by", ACTIVE_GROUP_BY.get(active))
    if group_by is not None:
        template["group_by"] = group_by
    if active == "nl":
        template["n"] = [int(_fixed_nl.group(1))] if _fixed_nl else list(data.get("n", DEFAULT_NL["n"]))
        template["l"] = list(data.get("l", DEFAULT_NL["l"]))
        template["occupancy"] = data.get("occupancy", DEFAULT_NL["occupancy"])
    elif active == "mk":
        template["m"] = [int(_fixed_mk.group(1))] if _fixed_mk else list(data.get("m", DEFAULT_NL.get("m", DEFAULT_NL["n"])))
        template["k"] = list(data.get("k", DEFAULT_NL.get("k", DEFAULT_NL["l"])))
        template["occupancy"] = data.get("occupancy", DEFAULT_NL["occupancy"])
    return template


def _optimize_radial_strategies(templates):
    # OPTIMIZE_RADIAL is a manual list for the survey.
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
        ION["element"], ION["charge_state"]
    )


def build_config():
    peak_ids = set()
    template_ids = set()
    peaks = [
        _normalize_peak({"wavelength": p.paper_fac_nm, "id": p.peak_id, "unit": "nm"}, peak_ids)
        for p in KNOWN_PEAKS
    ]
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
