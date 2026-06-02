#!/usr/bin/env python3
"""Run a simple grid search over optional configuration templates."""

import argparse
import csv
import itertools
import json
import math
import shutil
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

from config_loader import load_config
from generate_fac_input import build_fac_script


def peak_energies(config):
    target = config["target"]
    hc = target["conversion"]["hc_eV_angstrom"]
    nm_to_angstrom = target["conversion"]["nm_to_angstrom"]
    peaks = []
    for peak in target["reference_peaks"]:
        wavelength = peak["wavelength"]["value"]
        unit = peak["wavelength"]["unit"]
        if unit == "nm":
            wavelength_angstrom = wavelength * nm_to_angstrom
        elif unit == "angstrom":
            wavelength_angstrom = wavelength
        else:
            raise ValueError(f"Unsupported wavelength unit {unit!r}")
        peaks.append(
            {
                "id": peak["id"],
                "wavelength": wavelength,
                "wavelength_unit": unit,
                "wavelength_angstrom": wavelength_angstrom,
                "wavelength_nm": wavelength_angstrom / nm_to_angstrom,
                "energy_eV": hc / wavelength_angstrom,
                "fwhm_eV": peak.get("fwhm_eV"),
                "sigma_eV": peak.get("sigma_eV"),
                "type": peak.get("type", "anchor"),
            }
        )
    return peaks


def wavelength_window_nm(config):
    scoring = config["search"]["scoring"]
    window = scoring["wavelength_window"]["value"]
    unit = scoring["wavelength_window"]["unit"]
    nm_to_angstrom = config["target"]["conversion"]["nm_to_angstrom"]
    if unit == "nm":
        return window
    if unit == "angstrom":
        return window / nm_to_angstrom
    raise ValueError(f"Unsupported wavelength window unit {unit!r}")


def select_templates(config, selected_ids):
    trial_config = deepcopy(config)
    templates = config["configuration_space"]["templates"]["bound"]
    trial_templates = [
        template for template in templates if template["id"] in selected_ids
    ]
    trial_config["configuration_space"]["templates"]["bound"] = trial_templates
    return trial_config


def selected_tokens(config, selected_ids):
    templates = config["configuration_space"]["templates"]["bound"]
    selected = set(selected_ids)
    tokens = set(selected)
    for template in templates:
        if template["id"] not in selected:
            continue
        tokens.update(template.get("tags", []))
    return tokens


def _shell_occupancy(tag):
    text = str(tag)
    index = len(text)
    while index > 0 and text[index - 1].isdigit():
        index -= 1
    if index == len(text) or index == 0:
        return None
    subshell = text[:index]
    if not any(ch.isalpha() for ch in subshell):
        return None
    principal = subshell[:-1]
    if not principal.isdigit():
        return None
    return subshell, int(text[index:])


def shell_occupancies_by_template(config):
    result = {}
    templates = config["configuration_space"]["templates"]["bound"]
    for template in templates:
        occupancies = []
        for tag in template.get("tags", []):
            parsed = _shell_occupancy(tag)
            if parsed is not None:
                occupancies.append(parsed)
        result[template["id"]] = occupancies
    return result


def shell_occupancies(config, selected_ids=None):
    selected = None if selected_ids is None else set(selected_ids)
    by_shell = {}
    for template in config["configuration_space"]["templates"]["bound"]:
        if selected is not None and template["id"] not in selected:
            continue
        for subshell, occupancy in shell_occupancies_by_template(config)[template["id"]]:
            by_shell.setdefault(subshell, set()).add(occupancy)
    return by_shell


def generic_selection_constraint_violation(config, selected_ids):
    constraints = config.get("search", {}).get("selection_constraints", {})
    if not constraints:
        return None

    selected_by_shell = shell_occupancies(config, selected_ids)
    available_by_shell = shell_occupancies(config)

    if constraints.get("require_contiguous_shell_occupancies", False):
        for subshell, occupancies in selected_by_shell.items():
            if len(occupancies) < 2:
                continue
            for occupancy in range(min(occupancies), max(occupancies) + 1):
                if occupancy not in occupancies:
                    return f"{subshell}_occupancy_gap_{occupancy}"

    max_depth = constraints.get("max_shell_hole_depth_without_bridge")
    if max_depth is not None:
        max_depth = int(max_depth)
        for subshell, selected_occupancies in selected_by_shell.items():
            available = available_by_shell.get(subshell, set())
            if not available:
                continue
            reference = max(available)
            for occupancy in selected_occupancies:
                if reference - occupancy <= max_depth:
                    continue
                bridge = set(range(occupancy + 1, reference)) & selected_occupancies
                if not bridge:
                    return f"{subshell}{occupancy}_needs_bridge_to_{subshell}{reference}"

    return None


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _rule_applies(rule, tokens):
    if_any = _as_list(rule.get("if_any", rule.get("if_selected")))
    if_all = _as_list(rule.get("if_all"))
    if if_any and not any(item in tokens for item in if_any):
        return False
    if if_all and not all(item in tokens for item in if_all):
        return False
    if not if_any and not if_all:
        return True
    return True


def selection_rule_violation(config, selected_ids):
    generic_violation = generic_selection_constraint_violation(config, selected_ids)
    if generic_violation is not None:
        return generic_violation

    tokens = selected_tokens(config, selected_ids)
    for rule in config.get("search", {}).get("selection_rules", []):
        if not _rule_applies(rule, tokens):
            continue
        require_any = _as_list(rule.get("require_any", rule.get("then_any")))
        if require_any and not any(item in tokens for item in require_any):
            return rule.get("id", "unnamed_rule")
        require_all = _as_list(rule.get("require_all", rule.get("then_all")))
        if require_all and not all(item in tokens for item in require_all):
            return rule.get("id", "unnamed_rule")
        forbid_any = _as_list(rule.get("forbid_any"))
        if forbid_any and any(item in tokens for item in forbid_any):
            return rule.get("id", "unnamed_rule")
    return None


def is_legal_selection(config, selected_ids):
    return selection_rule_violation(config, selected_ids) is None


def enumerate_trials(config):
    templates = config["configuration_space"]["templates"]["bound"]
    required = [template for template in templates if template.get("required", False)]
    optional = [template for template in templates if not template.get("required", False)]
    required_ids = [template["id"] for template in required]

    search = config.get("search", {})
    radial = config.get("radial_potential", {})
    vary_radial = search.get("vary_optimize_radial_strategies", False)
    if vary_radial:
        strategies = radial.get("optimize_radial_strategies", [])
    else:
        strategies = [
            {
                "id": "fixed",
                "groups": radial.get("optimize_radial_groups"),
                "requires_templates": [],
            }
        ]
    max_trials = search.get("max_trials")
    stop_config = search.get("stop_on_configuration", {})
    stop_exact_ids = set(stop_config.get("exact_template_ids") or [])
    stop_enabled = bool(stop_config.get("enabled", False) and stop_exact_ids)
    count = 0
    template_ids = {template["id"] for template in templates}
    if stop_enabled and stop_exact_ids.issubset(template_ids) and set(required_ids).issubset(stop_exact_ids):
        selected = [template["id"] for template in templates if template["id"] in stop_exact_ids]
        if not is_legal_selection(config, selected):
            return
        for strategy in strategies:
            groups = strategy.get("groups")
            if not groups:
                continue
            required_for_strategy = strategy.get("requires_templates", [])
            if any(template_id not in selected for template_id in required_for_strategy):
                continue
            if any(group not in selected for group in groups if group in template_ids):
                continue
            trial_config = select_templates(config, selected)
            trial_config.setdefault("radial_potential", {})["optimize_radial_groups"] = groups
            yield {
                "trial_id": "trial_0001",
                "selected_template_ids": selected,
                "optimize_radial_strategy_id": strategy.get("id", "fixed"),
                "active_optional_count": sum(
                    1 for template in optional if template["id"] in selected
                ),
                "stop_after_trial": True,
                "config": trial_config,
            }
            return

    for mask in itertools.product([False, True], repeat=len(optional)):
        selected = list(required_ids)
        selected.extend(template["id"] for include, template in zip(mask, optional) if include)
        if not selected:
            continue
        if not is_legal_selection(config, selected):
            continue
        stop_after_selected = stop_enabled and set(selected) == stop_exact_ids
        for strategy in strategies:
            groups = strategy.get("groups")
            if not groups:
                continue
            required_for_strategy = strategy.get("requires_templates", [])
            if any(template_id not in selected for template_id in required_for_strategy):
                continue
            if any(group not in selected for group in groups if group in template_ids):
                continue
            count += 1
            if max_trials is not None and count > max_trials:
                return
            trial_config = select_templates(config, selected)
            trial_config.setdefault("radial_potential", {})["optimize_radial_groups"] = groups
            yield {
                "trial_id": f"trial_{count:04d}",
                "selected_template_ids": selected,
                "optimize_radial_strategy_id": strategy.get("id", "fixed"),
                "active_optional_count": sum(
                    1 for template in optional if template["id"] in selected
                ),
                "stop_after_trial": stop_after_selected,
                "config": trial_config,
            }
            if stop_after_selected:
                return


def configured_radial_strategies(config):
    search = config.get("search", {})
    radial = config.get("radial_potential", {})
    if search.get("vary_optimize_radial_strategies", False):
        return radial.get("optimize_radial_strategies", [])
    return [
        {
            "id": "fixed",
            "groups": radial.get("optimize_radial_groups"),
            "requires_templates": [],
        }
    ]


def valid_strategies_for_selection(config, selected_ids):
    if not is_legal_selection(config, selected_ids):
        return []
    templates = config["configuration_space"]["templates"]["bound"]
    template_ids = {template["id"] for template in templates}
    selected_set = set(selected_ids)
    valid = []
    for strategy in configured_radial_strategies(config):
        groups = strategy.get("groups")
        if not groups:
            continue
        required_for_strategy = strategy.get("requires_templates", [])
        if any(template_id not in selected_set for template_id in required_for_strategy):
            continue
        if any(group not in selected_set for group in groups if group in template_ids):
            continue
        valid.append(strategy)
    return valid


def make_trial(config, selected_ids, strategy, trial_number):
    templates = config["configuration_space"]["templates"]["bound"]
    optional = [template for template in templates if not template.get("required", False)]
    trial_config = select_templates(config, selected_ids)
    trial_config.setdefault("radial_potential", {})["optimize_radial_groups"] = strategy["groups"]
    return {
        "trial_id": f"trial_{trial_number:04d}",
        "selected_template_ids": list(selected_ids),
        "optimize_radial_strategy_id": strategy.get("id", "fixed"),
        "active_optional_count": sum(
            1 for template in optional if template["id"] in selected_ids
        ),
        "stop_after_trial": False,
        "config": trial_config,
    }


def numeric_loss(value):
    if value in ("", None):
        return math.inf
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.inf


def line_weight(upper_2j, a_value, radiative_weight):
    mode = str(radiative_weight or "(2J+1)*A").strip().lower()
    if mode in ("a", "a_value", "avalue"):
        return a_value
    if mode in ("ga", "g*a", "(2j+1)*a", "(2j_u+1)*a", "(2j+1) * a"):
        return (upper_2j + 1) * a_value
    raise ValueError(
        "Unsupported radiative_weight "
        f"{radiative_weight!r}; use 'A' or '(2J+1)*A'"
    )


def read_tr_ascii(filename, min_A=0.0, radiative_weight="(2J+1)*A"):
    """Return (energies, weights) from a FAC ASCII transition table.

    FAC column layout (8 columns, the only format observed in practice):
      upper_2J  upper_ilev  lower_2J  lower_ilev  delta_E(eV)  gf  A(s^-1)  gf

    The radiative-potential weight is selected by radiative_weight:
      A           -> A-value only
      (2J+1)*A    -> upper-level statistical weight times A

    Lines with A < min_A are silently dropped before scoring.
    """
    energies = []
    weights = []
    with Path(filename).open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) not in (8, 10):
                continue
            try:
                upper_2j = int(parts[0])
                int(parts[1])
                int(parts[2])
                int(parts[3])
                energy = float(parts[4])
                a_value = float(parts[7] if len(parts) == 10 else parts[6])
            except ValueError:
                continue
            if a_value < min_A:
                continue
            energies.append(energy)
            weights.append(line_weight(upper_2j, a_value, radiative_weight))
    return energies, weights


def peak_sigma_eV(peak):
    sigma = peak.get("sigma_eV")
    if sigma is not None:
        return float(sigma)
    fwhm = peak.get("fwhm_eV")
    if fwhm is None:
        raise ValueError(f"Peak {peak['id']} must define sigma_eV or fwhm_eV for v2 scoring")
    return float(fwhm) / 2.355


def peak_loss_weight(peak, loss_config):
    peak_type = peak.get("type", "anchor")
    if peak_type == "anchor":
        return float(loss_config.get("anchor_weight", 1.0))
    if peak_type == "ambiguous":
        return float(loss_config.get("ambiguous_weight", 0.3))
    raise ValueError(f"Unsupported peak type {peak_type!r} for peak {peak['id']}")


def build_v2_peak_groups(energies, weights, peaks, scoring, shift, hc):
    """Build per-peak line group summaries.

    shift : float
        Global systematic offset in the scoring space (eV for 'energy',
        Angstrom for 'wavelength').  Added to each theoretical line position
        before computing the Gaussian weight and residual.
    hc : float
        hc in eV*Angstrom, used only when scoring_space='wavelength'.
    """
    scoring_space = scoring.get("scoring_space", "energy")
    prefilter_window = float(scoring["prefilter_window_eV"])
    rate_floor = float(scoring.get("rate_floor", 1.0e-99))
    summaries = []

    for peak in peaks:
        target_e = peak["energy_eV"]
        sigma_eV = peak_sigma_eV(peak)
        if scoring_space == "wavelength":
            target_x = hc / target_e                   # Angstrom
            sigma_x = target_x * target_x / hc * sigma_eV   # |dλ/dE| * sigma_eV
        else:
            target_x = target_e                        # eV
            sigma_x = sigma_eV

        candidates = []
        for energy, base_weight in zip(energies, weights):
            if abs(energy - target_e) > prefilter_window:
                continue
            if scoring_space == "wavelength":
                if energy <= 0.0:
                    continue
                x = hc / energy
            else:
                x = energy
            delta = x + shift - target_x
            gaussian = math.exp(-(delta * delta) / (2.0 * sigma_x * sigma_x))
            w = max(base_weight, rate_floor) * gaussian
            if w > 0.0:
                candidates.append((x, w))

        if not candidates:
            summaries.append({
                "peak_id": peak["id"],
                "n_lines": 0,
                "center_eV": "",
                "center_angstrom": "",
                "residual_eV": "",
                "residual_angstrom": "",
                "center_scoring": "",
                "residual_scoring": "",
                "score": 0.0,
                "sigma_eV": sigma_eV,
            })
            continue

        weight_sum = sum(w for _, w in candidates)
        center_x = sum(x * w for x, w in candidates) / weight_sum
        residual_x = target_x - (center_x + shift)

        if scoring_space == "wavelength":
            center_angstrom = center_x
            residual_angstrom = residual_x
            center_eV = hc / center_x if center_x > 0 else ""
            residual_eV = ""
        else:
            center_eV = center_x
            residual_eV = residual_x
            center_angstrom = hc / center_x if center_x > 0 else ""
            residual_angstrom = ""

        summaries.append({
            "peak_id": peak["id"],
            "n_lines": len(candidates),
            "center_eV": center_eV,
            "center_angstrom": center_angstrom,
            "residual_eV": residual_eV,
            "residual_angstrom": residual_angstrom,
            "center_scoring": center_x,
            "residual_scoring": residual_x,
            "score": weight_sum,
            "sigma_eV": sigma_eV,
        })
    return summaries


def optimize_global_shift(energies, weights, peaks, config):
    global_shift = config.get("global_shift", {})
    if not global_shift.get("enabled", False):
        return 0.0, False

    scoring = config["search"]["scoring"]
    loss_config = config["loss"]
    hc = config["target"]["conversion"]["hc_eV_angstrom"]
    scoring_space = scoring.get("scoring_space", "energy")

    summaries = build_v2_peak_groups(energies, weights, peaks, scoring, 0.0, hc)
    numer = 0.0
    denom = 0.0
    for peak, summary in zip(peaks, summaries):
        if not summary["n_lines"] or summary["center_scoring"] == "":
            continue
        weight = peak_loss_weight(peak, loss_config)
        target_e = peak["energy_eV"]
        target_x = hc / target_e if scoring_space == "wavelength" else target_e
        numer += weight * (target_x - float(summary["center_scoring"]))
        denom += weight
    if denom == 0.0:
        return 0.0, False

    shift = numer / denom
    if scoring_space == "wavelength":
        sanity_range = global_shift.get("sanity_range_angstrom")
    else:
        sanity_range = global_shift.get("sanity_range_eV")
    if sanity_range is not None:
        lower, upper = sanity_range
        if shift < lower or shift > upper:
            return shift, True
    return shift, False


def _target_scoring_coordinate(peak, scoring_space, hc):
    target_e = peak["energy_eV"]
    return hc / target_e if scoring_space == "wavelength" else target_e


def _line_scoring_coordinate(energy, scoring_space, hc):
    if scoring_space == "wavelength":
        if energy <= 0.0:
            return None
        return hc / energy
    return energy


def _local_shift_search_window(scoring, scoring_space):
    if scoring_space == "wavelength":
        value = scoring.get("local_shift_search_window_angstrom")
        return None if value is None else float(value)
    value = scoring.get("local_shift_search_window_eV")
    return None if value is None else float(value)


def _local_line_group_window(scoring, scoring_space):
    if scoring_space == "wavelength":
        value = scoring.get("local_line_group_window_angstrom")
        return None if value is None else float(value)
    value = scoring.get("local_line_group_window_eV")
    return None if value is None else float(value)


def local_line_group_options(candidates, group_window, target_x, max_groups):
    if not candidates:
        return []
    if group_window is None:
        weight_sum = sum(w for _, w in candidates)
        center_x = sum(x * w for x, w in candidates) / weight_sum
        return [(center_x, weight_sum, len(candidates), abs(center_x - target_x))]

    options = []
    seen = set()
    for seed_x, _ in candidates:
        group = [(x, w) for x, w in candidates if abs(x - seed_x) <= group_window]
        weight_sum = sum(w for _, w in group)
        center_x = sum(x * w for x, w in group) / weight_sum
        distance = abs(center_x - target_x)
        key = round(center_x, 8)
        if key in seen:
            continue
        seen.add(key)
        options.append((center_x, weight_sum, len(group), distance))
    options.sort(key=lambda item: (-item[1], item[3]))
    return options[:max_groups]


def shift_group_summary(peak, group, scoring_space, hc):
    center_x, weight_sum, n_lines, _ = group
    target_x = _target_scoring_coordinate(peak, scoring_space, hc)
    local_shift = target_x - center_x
    if scoring_space == "wavelength":
        center_angstrom = center_x
        residual_angstrom = local_shift
        center_eV = hc / center_x if center_x > 0 else ""
        residual_eV = ""
    else:
        center_eV = center_x
        residual_eV = local_shift
        center_angstrom = hc / center_x if center_x > 0 else ""
        residual_angstrom = ""
    return {
        "peak_id": peak["id"],
        "n_lines": n_lines,
        "center_eV": center_eV,
        "center_angstrom": center_angstrom,
        "residual_eV": residual_eV,
        "residual_angstrom": residual_angstrom,
        "center_scoring": center_x,
        "residual_scoring": local_shift,
        "local_shift": local_shift,
        "score": weight_sum,
        "sigma_eV": peak_sigma_eV(peak),
    }


def build_per_peak_shift_groups(energies, weights, peaks, scoring, hc):
    options = build_per_peak_shift_group_options(energies, weights, peaks, scoring, hc)
    summaries = []
    scoring_space = scoring.get("scoring_space", "energy")
    for peak, peak_options in zip(peaks, options):
        if not peak_options:
            summaries.append({
                "peak_id": peak["id"],
                "n_lines": 0,
                "center_eV": "",
                "center_angstrom": "",
                "residual_eV": "",
                "residual_angstrom": "",
                "center_scoring": "",
                "residual_scoring": "",
                "score": 0.0,
                "sigma_eV": peak_sigma_eV(peak),
            })
            continue
        summaries.append(shift_group_summary(peak, peak_options[0], scoring_space, hc))
    return summaries


def build_per_peak_shift_group_options(energies, weights, peaks, scoring, hc):
    scoring_space = scoring.get("scoring_space", "energy")
    prefilter_window = scoring.get("prefilter_window_eV")
    prefilter_window = None if prefilter_window is None else float(prefilter_window)
    local_window = _local_shift_search_window(scoring, scoring_space)
    group_window = _local_line_group_window(scoring, scoring_space)
    max_groups = int(scoring.get("max_local_shift_groups_per_peak", 12))
    if scoring_space == "wavelength" and local_window is not None:
        prefilter_window = None
    all_options = []

    for peak in peaks:
        target_e = peak["energy_eV"]
        target_x = _target_scoring_coordinate(peak, scoring_space, hc)
        candidates = []
        for energy, weight in zip(energies, weights):
            if prefilter_window is not None and abs(energy - target_e) > prefilter_window:
                continue
            x = _line_scoring_coordinate(energy, scoring_space, hc)
            if x is None:
                continue
            if local_window is not None and abs(x - target_x) > local_window:
                continue
            if weight > 0.0:
                candidates.append((x, weight))

        all_options.append(local_line_group_options(candidates, group_window, target_x, max_groups))
    return all_options


def local_shifts_are_direction_consistent(shifts, zero_tolerance):
    signs = []
    for shift in shifts:
        if abs(shift) <= zero_tolerance:
            continue
        signs.append(1 if shift > 0.0 else -1)
    return not signs or all(sign == signs[0] for sign in signs)


def _wavelength_shift_limit(shift_config, nm_key, angstrom_key):
    if shift_config.get(nm_key) is not None:
        return float(shift_config[nm_key]) * 10.0
    if shift_config.get(angstrom_key) is not None:
        return float(shift_config[angstrom_key])
    return None


def choose_shift_consistent_groups(group_options, peaks, scoring_space, hc, shift_config, loss_config):
    if any(not options for options in group_options):
        return None, "", "", "missing_peak"

    if scoring_space == "wavelength":
        spread_tolerance = _wavelength_shift_limit(
            shift_config,
            "max_shift_spread_nm",
            "max_shift_spread_angstrom",
        )
        max_abs_shift = _wavelength_shift_limit(
            shift_config,
            "max_abs_shift_nm",
            "max_abs_shift_angstrom",
        )
        zero_tolerance = _wavelength_shift_limit(
            shift_config,
            "direction_zero_tolerance_nm",
            "direction_zero_tolerance_angstrom",
        ) or 0.0
    else:
        spread_tolerance = shift_config.get("max_shift_spread_eV")
        max_abs_shift = shift_config.get("max_abs_shift_eV")
        zero_tolerance = float(shift_config.get("direction_zero_tolerance_eV", 0.0))

    best = None
    best_value = None
    fallback = None
    fallback_value = None
    for groups in itertools.product(*group_options):
        summaries = [
            shift_group_summary(peak, group, scoring_space, hc)
            for peak, group in zip(peaks, groups)
        ]
        shifts = [float(summary["local_shift"]) for summary in summaries]
        mean_shift = sum(shifts) / len(shifts)
        shift_spread = max(shifts) - min(shifts)
        direction_ok = True
        if shift_config.get("require_consistent_direction", True):
            direction_ok = local_shifts_are_direction_consistent(shifts, zero_tolerance)
        abs_ok = max_abs_shift is None or max(abs(shift) for shift in shifts) <= float(max_abs_shift)
        spread_ok = spread_tolerance is None or shift_spread <= float(spread_tolerance)

        score_value = 0.0
        for peak, summary in zip(peaks, summaries):
            peak_weight = peak_loss_weight(peak, loss_config)
            shift_delta = float(summary["local_shift"]) - mean_shift
            score_value += (
                float(loss_config.get("position_weight", 1.0)) * peak_weight * shift_delta * shift_delta
                - float(loss_config.get("strength_weight", 1.0)) * peak_weight
                * math.log(float(summary["score"]) + 1.0e-99)
            )

        fallback_rank = (shift_spread, score_value)
        if fallback is None or fallback_rank < fallback_value:
            fallback = (summaries, mean_shift, shift_spread)
            fallback_value = fallback_rank

        if not direction_ok or not abs_ok or not spread_ok:
            continue
        if best is None or score_value < best_value:
            best = (summaries, mean_shift, shift_spread)
            best_value = score_value

    if best is not None:
        return best[0], best[1], best[2], ""
    if fallback is None:
        return None, "", "", "missing_peak"
    return fallback[0], fallback[1], fallback[2], "shift_consistency"


def _score_calibration(energies, weights, peaks, scoring_space, hc,
                       loss_config, radiative_weight, rate_floor, missing_penalty,
                       active_optional_count):
    """Calibration mode: find the single closest FAC line to each reference wavelength.

    Bypasses the top-N-by-weight group filter so that the correct (potentially
    weak) assigned transition is not crowded out by stronger nearby lines.

    Loss = position_weight * sum(local_shift_p^2) - strength_weight * sum(log(score_p))
    where local_shift_p = lambda_reference_p - lambda_FAC_line_p  (absolute offset).
    """
    search_window = 8.0  # Angstrom; wide enough for any realistic FAC offset

    summaries = []
    for peak in peaks:
        target_e = peak["energy_eV"]
        target_x = hc / target_e  # Angstrom

        best_x = None
        best_w = 0.0
        best_dist = float("inf")
        for energy, weight in zip(energies, weights):
            if energy <= 0.0:
                continue
            x = hc / energy
            dist = abs(x - target_x)
            if dist > search_window:
                continue
            if dist < best_dist:
                best_dist = dist
                best_x = x
                best_w = weight

        if best_x is None:
            summaries.append({
                "peak_id": peak["id"],
                "n_lines": 0,
                "center_eV": "", "center_angstrom": "",
                "residual_eV": "", "residual_angstrom": "",
                "center_scoring": "", "residual_scoring": "",
                "score": 0.0,
                "sigma_eV": peak_sigma_eV(peak),
                "local_shift": 0.0,
            })
        else:
            local_shift = target_x - best_x
            center_eV = hc / best_x if best_x > 0 else ""
            summaries.append({
                "peak_id": peak["id"],
                "n_lines": 1,
                "center_eV": center_eV,
                "center_angstrom": best_x,
                "residual_eV": "",
                "residual_angstrom": "",
                "center_scoring": best_x,
                "residual_scoring": local_shift,
                "score": best_w,
                "sigma_eV": peak_sigma_eV(peak),
                "local_shift": local_shift,
            })

    valid_shifts = [
        float(s["local_shift"])
        for s in summaries
        if s.get("n_lines", 0) > 0 and s.get("local_shift", "") != ""
    ]
    mean_shift = sum(valid_shifts) / len(valid_shifts) if valid_shifts else 0.0
    shift_spread = (max(valid_shifts) - min(valid_shifts)) if len(valid_shifts) > 1 else 0.0

    for summary in summaries:
        summary["scoring_space"] = scoring_space
        summary["radiative_weight"] = radiative_weight
        summary["shift"] = summary.get("local_shift", "")
        summary["mean_shift"] = mean_shift
        summary["shift_spread"] = shift_spread
        summary["shift_out_of_range"] = False
        summary["shift_failure_reason"] = ""

    pos_w = float(loss_config.get("position_weight", 1.0))
    str_w = float(loss_config.get("strength_weight", 1.0))
    total_loss = 0.0
    for peak, summary in zip(peaks, summaries):
        if not summary.get("n_lines", 0):
            total_loss += missing_penalty
            continue
        peak_w = peak_loss_weight(peak, loss_config)
        local_shift = float(summary["local_shift"])
        score = float(summary["score"])
        total_loss += pos_w * peak_w * local_shift * local_shift
        total_loss -= str_w * peak_w * math.log(score + rate_floor)

    complexity = loss_config.get("complexity", {})
    if complexity.get("enabled", False):
        total_loss += float(complexity["per_optional_template"]) * active_optional_count
    return total_loss, summaries


def score_tr_file_per_peak_shift(tr_file, config, active_optional_count=0):
    scoring = config["search"]["scoring"]
    min_A = float(scoring["min_A_value"]) if scoring.get("min_A_value") else 0.0
    radiative_weight = scoring.get("radiative_weight", "(2J+1)*A")
    energies, weights = read_tr_ascii(
        tr_file,
        min_A=min_A,
        radiative_weight=radiative_weight,
    )
    peaks = peak_energies(config)
    loss_config = config["loss"]
    shift_config = config.get("global_shift", {})
    missing_penalty = float(loss_config["missing_peak_penalty"])
    rate_floor = float(scoring.get("rate_floor", 1.0e-99))
    hc = config["target"]["conversion"]["hc_eV_angstrom"]
    scoring_space = scoring.get("scoring_space", "energy")

    group_options = build_per_peak_shift_group_options(energies, weights, peaks, scoring, hc)

    if shift_config.get("calibration_mode", False):
        return _score_calibration(
            energies, weights, peaks, scoring_space, hc,
            loss_config, radiative_weight, rate_floor, missing_penalty,
            active_optional_count,
        )

    summaries, mean_shift, shift_spread, shift_failure_reason = choose_shift_consistent_groups(
        group_options,
        peaks,
        scoring_space,
        hc,
        shift_config,
        loss_config,
    )
    shift_failed = bool(shift_failure_reason)
    if summaries is None:
        summaries = build_per_peak_shift_groups(energies, weights, peaks, scoring, hc)

    for summary in summaries:
        summary["scoring_space"] = scoring_space
        summary["radiative_weight"] = radiative_weight
        summary["shift"] = summary.get("local_shift", "")
        summary["mean_shift"] = mean_shift
        summary["shift_spread"] = shift_spread
        summary["shift_out_of_range"] = shift_failed
        summary["shift_failure_reason"] = shift_failure_reason

    if shift_failed:
        return missing_penalty * len(peaks), summaries

    total_loss = 0.0
    for peak, summary in zip(peaks, summaries):
        weight = peak_loss_weight(peak, loss_config)
        score = float(summary["score"])
        shift_delta = float(summary["local_shift"]) - float(mean_shift)
        total_loss += (
            float(loss_config.get("position_weight", 1.0)) * weight * shift_delta * shift_delta
            - float(loss_config.get("strength_weight", 1.0)) * weight * math.log(score + rate_floor)
        )

    shift_spread_weight = float(loss_config.get("shift_spread_weight", 0.0))
    total_loss += shift_spread_weight * float(shift_spread) * float(shift_spread)

    complexity = loss_config.get("complexity", {})
    if complexity.get("enabled", False):
        total_loss += float(complexity["per_optional_template"]) * active_optional_count
    return total_loss, summaries


def score_tr_file_v2(tr_file, config, active_optional_count=0):
    scoring = config["search"]["scoring"]
    min_A = float(scoring["min_A_value"]) if scoring.get("min_A_value") else 0.0
    radiative_weight = scoring.get("radiative_weight", "(2J+1)*A")
    if config.get("global_shift", {}).get("mode") == "per_peak_consistency":
        return score_tr_file_per_peak_shift(tr_file, config, active_optional_count)

    energies, weights = read_tr_ascii(
        tr_file,
        min_A=min_A,
        radiative_weight=radiative_weight,
    )
    peaks = peak_energies(config)
    loss_config = config["loss"]
    missing_penalty = float(loss_config["missing_peak_penalty"])
    rate_floor = float(scoring.get("rate_floor", 1.0e-99))
    hc = config["target"]["conversion"]["hc_eV_angstrom"]
    scoring_space = scoring.get("scoring_space", "energy")

    shift, shift_out_of_range = optimize_global_shift(energies, weights, peaks, config)
    if shift_out_of_range:
        return missing_penalty * len(peaks), [
            {
                "peak_id": peak["id"],
                "n_lines": 0,
                "center_eV": "",
                "center_angstrom": "",
                "residual_eV": "",
                "residual_angstrom": "",
                "center_scoring": "",
                "residual_scoring": "",
                "score": 0.0,
                "scoring_space": scoring_space,
                "shift": shift,
                "shift_out_of_range": True,
            }
            for peak in peaks
        ]

    summaries = build_v2_peak_groups(energies, weights, peaks, scoring, shift, hc)
    total_loss = 0.0
    for peak, summary in zip(peaks, summaries):
        summary["scoring_space"] = scoring_space
        summary["radiative_weight"] = radiative_weight
        summary["shift"] = shift
        if not summary["n_lines"]:
            total_loss += missing_penalty
            continue
        weight = peak_loss_weight(peak, loss_config)
        residual = float(summary["residual_scoring"])
        score = float(summary["score"])
        total_loss += (
            float(loss_config.get("position_weight", 1.0)) * weight * residual * residual
            - float(loss_config.get("strength_weight", 1.0)) * weight * math.log(score + rate_floor)
        )

    complexity = loss_config.get("complexity", {})
    if complexity.get("enabled", False):
        total_loss += float(complexity["per_optional_template"]) * active_optional_count
    return total_loss, summaries


def score_tr_file(tr_file, config, active_optional_count=0):
    scoring = config["search"]["scoring"]
    if scoring.get("use_gaussian_soft_window", False):
        return score_tr_file_v2(tr_file, config, active_optional_count)

    min_A = float(scoring["min_A_value"]) if scoring.get("min_A_value") else 0.0
    energies, weights = read_tr_ascii(
        tr_file,
        min_A=min_A,
        radiative_weight=scoring.get("radiative_weight", "(2J+1)*A"),
    )
    peaks = peak_energies(config)
    window_space = scoring.get("window_space", "energy")
    energy_window = scoring["energy_window_eV"]
    wl_window_nm = wavelength_window_nm(config)
    missing_penalty = scoring["missing_peak_penalty"]
    rate_floor = scoring["rate_floor"]
    hc = config["target"]["conversion"]["hc_eV_angstrom"]
    nm_to_angstrom = config["target"]["conversion"]["nm_to_angstrom"]

    total_loss = 0.0
    summaries = []
    for peak in peaks:
        target_e = peak["energy_eV"]
        target_wl_nm = peak["wavelength_nm"]
        candidates = []
        for energy, weight in zip(energies, weights):
            if energy <= 0:
                continue
            wl_nm = (hc / energy) / nm_to_angstrom
            if window_space == "energy":
                in_window = abs(energy - target_e) <= energy_window
            elif window_space == "wavelength":
                in_window = abs(wl_nm - target_wl_nm) <= wl_window_nm
            else:
                raise ValueError(f"Unsupported scoring.window_space {window_space!r}")
            if in_window:
                candidates.append((energy, wl_nm, max(weight, rate_floor)))
        if not candidates:
            total_loss += missing_penalty
            summaries.append(
                {
                    "peak_id": peak["id"],
                    "n_lines": 0,
                    "center_eV": "",
                    "center_nm": "",
                    "residual_eV": "",
                    "residual_nm": "",
                    "score": 0.0,
                }
            )
            continue

        weight_sum = sum(w for _, _, w in candidates)
        center_e = sum(energy * w for energy, _, w in candidates) / weight_sum
        center_wl_nm = sum(wl_nm * w for _, wl_nm, w in candidates) / weight_sum
        residual_e = center_e - target_e
        residual_wl_nm = center_wl_nm - target_wl_nm
        # Keep the first-pass objective simple: center agreement plus a weak
        # reward for radiative potential inside the peak window.
        if window_space == "energy":
            residual_for_loss = residual_e
        else:
            residual_for_loss = residual_wl_nm
        total_loss += residual_for_loss * residual_for_loss - math.log(weight_sum + rate_floor)
        summaries.append(
            {
                "peak_id": peak["id"],
                "n_lines": len(candidates),
                "center_eV": center_e,
                "center_nm": center_wl_nm,
                "residual_eV": residual_e,
                "residual_nm": residual_wl_nm,
                "score": weight_sum,
            }
        )
    return total_loss, summaries


def fac_parallel_settings(config):
    fac_input = config.get("fac_input", {})
    parallel = dict(fac_input.get("parallel", {}))
    if not parallel:
        openmp = fac_input.get("use_openmp", {})
        if openmp.get("enabled", False):
            parallel = {"mode": "openmp", "nproc": openmp.get("nproc", 1)}
        else:
            parallel = {"mode": "serial", "nproc": 1}
    parallel.setdefault("mode", "serial")
    parallel.setdefault("nproc", 1)
    parallel.setdefault("launcher", "mpirun")
    parallel.setdefault("nproc_flag", "-np")
    parallel.setdefault("launcher_args", [])
    return parallel


def build_fac_command(config, script_path):
    parallel = fac_parallel_settings(config)
    mode = parallel["mode"]
    if mode == "serial":
        return [sys.executable, str(script_path)]
    if mode == "openmp":
        return [sys.executable, str(script_path), "openmp"]
    if mode == "mpi":
        return [
            parallel.get("launcher", "mpirun"),
            *[str(item) for item in parallel.get("launcher_args", [])],
            str(parallel.get("nproc_flag", "-np")),
            str(parallel["nproc"]),
            sys.executable,
            str(script_path),
            "mpi",
        ]
    raise ValueError(f"Unsupported FAC parallel mode {mode!r}")


def run_trial(trial, root, config):
    search = config["search"]
    generated_dir = root / search["generated_dir"]
    work_root = root / search["work_dir"]
    trial_id = trial["trial_id"]
    keep_generated_scripts = search.get("keep_generated_scripts", False)
    run_dir = work_root / trial_id
    run_dir.mkdir(parents=True, exist_ok=True)
    run_script_path = run_dir / f"{trial_id}.py" if keep_generated_scripts else None
    script_path = run_script_path

    script = build_fac_script(trial["config"])
    if keep_generated_scripts:
        generated_dir.mkdir(parents=True, exist_ok=True)
        (generated_dir / f"{trial_id}.py").write_text(script, encoding="utf-8")
        run_script_path.write_text(script, encoding="utf-8")
    if not search.get("run_fac", True):
        return {
            "trial_id": trial_id,
            "script": script_path,
            "run_dir": run_dir,
            "returncode": "",
            "loss": "",
            "peak_summaries": [],
        }

    temp_name = None
    try:
        if not keep_generated_scripts:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                suffix=f"_{trial_id}.py",
                prefix="fac_trial_",
                delete=False,
            ) as fh:
                fh.write(script)
                temp_name = fh.name
            run_script_path = Path(temp_name)

        cmd = build_fac_command(config, run_script_path)
        result = subprocess.run(
            cmd,
            cwd=run_dir,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=search.get("timeout_seconds_per_trial"),
            check=False,
        )
    finally:
        if temp_name is not None:
            temp_path = Path(temp_name)
            if temp_path.exists():
                temp_path.unlink()

    (run_dir / "fac.log").write_text(result.stdout, encoding="utf-8")
    if result.returncode != 0:
        return {
            "trial_id": trial_id,
            "script": script_path,
            "run_dir": run_dir,
            "returncode": result.returncode,
            "loss": "inf",
            "peak_summaries": [],
        }

    prefix = trial["config"]["fac_input"]["output_prefix"]
    tr_file = run_dir / f"{prefix}a.tr"
    if not tr_file.exists():
        # FAC produces no .tr file when there are no transitions (e.g. ground-only
        # closed-shell configuration).  Score as all-peaks-missing.
        if trial["config"]["search"]["scoring"].get("use_gaussian_soft_window", False):
            missing_penalty = trial["config"]["loss"]["missing_peak_penalty"]
        else:
            missing_penalty = trial["config"]["search"]["scoring"]["missing_peak_penalty"]
        n_peaks = len(trial["config"]["target"]["reference_peaks"])
        loss = missing_penalty * n_peaks
        peak_summaries = []
    else:
        loss, peak_summaries = score_tr_file(
            tr_file,
            trial["config"],
            active_optional_count=trial.get("active_optional_count", 0),
        )
    return {
        "trial_id": trial_id,
        "script": script_path,
        "run_dir": run_dir,
        "returncode": result.returncode,
        "loss": loss,
        "peak_summaries": peak_summaries,
    }


def write_results(results_file, rows):
    results_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "trial_id",
        "round",
        "candidate_template_id",
        "accepted",
        "loss",
        "selected_template_ids",
        "optimize_radial_strategy_id",
        "returncode",
        "run_dir",
        "script",
        "peak_summary",
    ]
    with results_file.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_loss_configuration_optimization_table(output_file, rows):
    output_file.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(rows, key=lambda row: numeric_loss(row["loss"]))
    fieldnames = [
        "loss",
        "trial_id",
        "optimization",
    ]
    with output_file.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow(
                {
                    "loss": row["loss"],
                    "trial_id": row["trial_id"],
                    "optimization": row["optimize_radial_strategy_id"],
                }
            )


def write_calibration_summary(output_file, rows, peaks):
    """Human-readable table: per-peak FAC offsets from reference wavelengths."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(rows, key=lambda r: numeric_loss(r["loss"]))
    peak_ids = [p["id"] for p in peaks]
    col_w = 14

    with output_file.open("w", encoding="utf-8") as fh:
        header = f"{'strategy':<42} {'loss':>10} {'mean_A':>9} {'spread_A':>9}"
        for pid in peak_ids:
            header += f"  {pid[:col_w]:>{col_w}}"
        fh.write(header + "\n")
        fh.write("-" * len(header) + "\n")

        for row in sorted_rows:
            strategy = row.get("optimize_radial_strategy_id", "")[:42]
            loss = numeric_loss(row["loss"])
            summaries = json.loads(row.get("peak_summary", "[]"))
            valid = [s for s in summaries if s.get("n_lines", 0) > 0 and s.get("local_shift", "") != ""]
            shifts = [float(s["local_shift"]) for s in valid]
            mean_s = sum(shifts) / len(shifts) if shifts else float("nan")
            spread_s = (max(shifts) - min(shifts)) if len(shifts) > 1 else 0.0

            line = f"{strategy:<42} {loss:>10.2f} {mean_s:>+9.3f} {spread_s:>9.3f}"
            for s in summaries:
                sh = s.get("local_shift", "")
                if sh != "" and s.get("n_lines", 0) > 0:
                    line += f"  {float(sh):>+{col_w}.3f}"
                else:
                    line += f"  {'MISS':>{col_w}}"
            fh.write(line + "\n")


def persist_search_tables(config, root, rows):
    if not rows:
        return
    sorted_rows = sorted(rows, key=lambda row: numeric_loss(row["loss"]))
    results_file = root / config["search"]["results_file"]
    write_results(results_file, sorted_rows)
    summary_file = results_file.parent / "loss_configuration_optimization.txt"
    write_loss_configuration_optimization_table(summary_file, sorted_rows)
    if config.get("global_shift", {}).get("calibration_mode", False):
        peaks = peak_energies(config)
        cal_file = results_file.parent / "calibration_summary.txt"
        write_calibration_summary(cal_file, sorted_rows, peaks)


def result_row(trial, result, round_id="", candidate_template_id="", accepted=""):
    return {
        "trial_id": result["trial_id"],
        "round": round_id,
        "candidate_template_id": candidate_template_id,
        "accepted": accepted,
        "loss": result["loss"],
        "selected_template_ids": ";".join(trial["selected_template_ids"]),
        "optimize_radial_strategy_id": trial["optimize_radial_strategy_id"],
        "returncode": result["returncode"],
        "run_dir": result["run_dir"],
        "script": result["script"],
        "peak_summary": json.dumps(result["peak_summaries"], ensure_ascii=False),
    }


def print_trial(trial):
    print(
        f"running {trial['trial_id']}: {', '.join(trial['selected_template_ids'])}; "
        f"OptimizeRadial={trial['optimize_radial_strategy_id']}",
        flush=True,
    )


def run_grid_search(config, root):
    rows = []
    for trial in enumerate_trials(config):
        print_trial(trial)
        result = run_trial(trial, root, config)
        rows.append(result_row(trial, result))
        persist_search_tables(config, root, rows)
    return rows


def run_greedy_forward_selection(config, root):
    templates = config["configuration_space"]["templates"]["bound"]
    required_ids = [template["id"] for template in templates if template.get("required", False)]
    optional_ids = [template["id"] for template in templates if not template.get("required", False)]
    selected = list(required_ids)
    remaining = list(optional_ids)
    settings = config.get("search", {}).get("forward_selection", {})
    min_improvement = float(settings.get("min_loss_improvement", 0.0))
    max_rounds = settings.get("max_rounds")
    if max_rounds is None:
        max_rounds = len(optional_ids)

    rows = []
    trial_number = 0

    current_best = None
    for strategy in valid_strategies_for_selection(config, selected):
        trial_number += 1
        trial = make_trial(config, selected, strategy, trial_number)
        print_trial(trial)
        result = run_trial(trial, root, config)
        row = result_row(trial, result, round_id=0, candidate_template_id="baseline")
        rows.append(row)
        persist_search_tables(config, root, rows)
        loss = numeric_loss(result["loss"])
        if current_best is None or loss < current_best["loss"]:
            current_best = {
                "loss": loss,
                "selected": selected,
                "strategy_id": trial["optimize_radial_strategy_id"],
                "row": row,
            }

    if current_best is None:
        return rows

    current_loss = current_best["loss"]
    if math.isinf(current_loss):
        print("stopping: baseline loss is not available", flush=True)
        return rows

    for round_id in range(1, max_rounds + 1):
        if not remaining:
            break

        round_best = None
        for candidate_id in remaining:
            candidate_selected = selected + [candidate_id]
            for strategy in valid_strategies_for_selection(config, candidate_selected):
                trial_number += 1
                trial = make_trial(config, candidate_selected, strategy, trial_number)
                print_trial(trial)
                result = run_trial(trial, root, config)
                row = result_row(
                    trial,
                    result,
                    round_id=round_id,
                    candidate_template_id=candidate_id,
                    accepted="pending",
                )
                rows.append(row)
                persist_search_tables(config, root, rows)
                loss = numeric_loss(result["loss"])
                if round_best is None or loss < round_best["loss"]:
                    round_best = {
                        "loss": loss,
                        "candidate_id": candidate_id,
                        "selected": candidate_selected,
                        "row": row,
                    }

        if round_best is None or math.isinf(round_best["loss"]):
            print("stopping: no finite candidate loss", flush=True)
            break

        improvement = current_loss - round_best["loss"]
        if improvement >= min_improvement and round_best["loss"] < current_loss:
            selected = round_best["selected"]
            remaining = [item for item in remaining if item != round_best["candidate_id"]]
            current_loss = round_best["loss"]
            round_best["row"]["accepted"] = "yes"
            persist_search_tables(config, root, rows)
            print(
                f"accepted {round_best['candidate_id']} "
                f"loss={current_loss} improvement={improvement}",
                flush=True,
            )
        else:
            round_best["row"]["accepted"] = "no"
            persist_search_tables(config, root, rows)
            print(
                f"stopping: best candidate {round_best['candidate_id']} "
                f"loss={round_best['loss']} did not improve current loss={current_loss}",
                flush=True,
            )
            break

    for row in rows:
        if row["accepted"] == "pending":
            row["accepted"] = ""
    persist_search_tables(config, root, rows)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--clean", action="store_true", help="Remove previous search outputs first")
    args = parser.parse_args()

    root = Path.cwd()
    config = load_config(args.input)

    search = config["search"]
    if args.clean:
        for key in ("work_dir", "generated_dir"):
            path = root / search[key]
            if path.exists():
                shutil.rmtree(path)

    method = search.get("method", "grid_search")
    if method in ("grid_search", "exhaustive_grid"):
        rows = run_grid_search(config, root)
    elif method == "greedy_forward_selection":
        rows = run_greedy_forward_selection(config, root)
    else:
        raise ValueError(
            f"Unsupported search.method {method!r}; "
            "expected 'grid_search', 'exhaustive_grid', or 'greedy_forward_selection'"
        )

    rows.sort(key=lambda row: numeric_loss(row["loss"]))
    results_file = root / search["results_file"]
    write_results(results_file, rows)
    summary_file = results_file.parent / "loss_configuration_optimization.txt"
    write_loss_configuration_optimization_table(summary_file, rows)
    print(f"wrote {results_file}")
    print(f"wrote {summary_file}")
    if rows:
        best = rows[0]
        print(
            f"best {best['trial_id']} loss={best['loss']} "
            f"templates={best['selected_template_ids']} "
            f"optimize_radial={best['optimize_radial_strategy_id']}"
        )


if __name__ == "__main__":
    main()
