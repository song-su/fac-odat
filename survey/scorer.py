"""Code-independent scorer: match computed transitions to known peaks.

Works on any Level/Transition objects that expose the expected attributes
(two_j, config, wavelength_nm, a_value, gf, upper_ilev, lower_ilev, etc.).
In practice these come from survey.fac.parser, but the scorer itself has no
FAC dependency.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from survey.peaks import KnownPeak, derive_transition_label


@dataclass(frozen=True)
class Candidate:
    peak_id: str
    target_nm: float
    paper_fac_nm: float
    multipole: str
    upper_ilev: int
    upper_2j: int
    lower_ilev: int
    lower_2j: int
    wavelength_nm: float
    residual_angstrom: float
    a_value: float
    gf: float
    upper_config: str
    lower_config: str
    upper_label: str
    lower_label: str
    base_config: Optional[Dict[str, int]] = None

    @property
    def transition(self) -> Optional[str]:
        return derive_transition_label(
            self.upper_config, self.lower_config, self.base_config
        )


def rms_angstrom(candidates: List[Candidate]) -> Optional[float]:
    residuals = [c.residual_angstrom for c in candidates]
    if not residuals:
        return None
    return math.sqrt(sum(r * r for r in residuals) / len(residuals))


def find_candidates(
    transitions: Iterable,
    levels: Dict[int, object],
    target_nm: float,
    upper_config: str,
    lower_config: str = "4d10",
    upper_2j: Optional[int] = None,
    lower_2j: Optional[int] = None,
    top_n: int = 5,
    base_config: Optional[Dict[str, int]] = None,
) -> List[Candidate]:
    """Return the top_n transitions from upper_config→lower_config closest to target_nm.

    upper_2j / lower_2j: if not None, only transitions whose level 2J matches
    exactly are considered, removing contamination from other J values in the
    same configuration family.
    """
    target_angstrom = target_nm * 10.0
    candidates: List[Candidate] = []
    for tr in transitions:
        upper = levels.get(tr.upper_ilev)
        lower = levels.get(tr.lower_ilev)
        if upper is None or lower is None:
            continue
        if upper.config != upper_config or lower.config != lower_config:
            continue
        if upper_2j is not None and upper.two_j != upper_2j:
            continue
        if lower_2j is not None and lower.two_j != lower_2j:
            continue
        residual = target_angstrom - tr.wavelength_angstrom
        candidates.append(Candidate(
            peak_id="",
            target_nm=target_nm,
            paper_fac_nm=0.0,
            multipole="",
            upper_ilev=tr.upper_ilev,
            upper_2j=tr.upper_2j,
            lower_ilev=tr.lower_ilev,
            lower_2j=tr.lower_2j,
            wavelength_nm=tr.wavelength_nm,
            residual_angstrom=residual,
            a_value=tr.a_value,
            gf=tr.gf,
            upper_config=upper.config,
            lower_config=lower.config,
            upper_label=upper.label,
            lower_label=lower.label,
            base_config=base_config,
        ))
    candidates.sort(key=lambda c: abs(c.residual_angstrom))
    return candidates[:top_n]


def find_known_candidates(
    peaks: List[KnownPeak],
    en_path: Path,
    tr_path: Path,
    top_n: int = 5,
    use_paper_fac_target: bool = False,
    base_config: Optional[Dict[str, int]] = None,
) -> List[Candidate]:
    """Find FAC transition candidates for each peak, restricted by config+J.

    Parameters
    ----------
    peaks              : list of KnownPeak entries
    en_path / tr_path  : FAC ASCII level and transition tables
    top_n              : max candidates per peak, sorted by |residual|
    use_paper_fac_target: True → score against paper_fac_nm; False → exp_nm
    base_config        : passed to Candidate for transition label derivation
    """
    from survey.fac.parser import parse_en_table, parse_tr_table
    levels = parse_en_table(en_path)
    transitions = parse_tr_table(tr_path)

    all_candidates: List[Candidate] = []
    for peak in peaks:
        target_nm = peak.paper_fac_nm if use_paper_fac_target else peak.exp_nm
        raw = find_candidates(
            transitions, levels,
            target_nm=target_nm,
            upper_config=peak.upper_config,
            lower_config=peak.lower_config,
            upper_2j=peak.upper_2j,
            lower_2j=peak.lower_2j,
            top_n=top_n,
            base_config=base_config,
        )
        for c in raw:
            all_candidates.append(Candidate(
                peak_id=peak.peak_id,
                target_nm=target_nm,
                paper_fac_nm=peak.paper_fac_nm,
                multipole=peak.multipole,
                upper_ilev=c.upper_ilev,
                upper_2j=c.upper_2j,
                lower_ilev=c.lower_ilev,
                lower_2j=c.lower_2j,
                wavelength_nm=c.wavelength_nm,
                residual_angstrom=c.residual_angstrom,
                a_value=c.a_value,
                gf=c.gf,
                upper_config=c.upper_config,
                lower_config=c.lower_config,
                upper_label=c.upper_label,
                lower_label=c.lower_label,
                base_config=base_config,
            ))
    return all_candidates


def format_candidates(candidates: List[Candidate]) -> str:
    header = (
        "peak", "mult", "transition",
        "target_nm", "lambda_nm", "resid_A",
        "A", "up", "2J_u", "lo", "config", "label",
    )
    rows = [header]
    for item in candidates:
        rows.append((
            item.peak_id,
            item.multipole,
            item.transition if item.transition is not None else "None",
            f"{item.target_nm:.4f}",
            f"{item.wavelength_nm:.4f}",
            f"{item.residual_angstrom:+.3f}",
            f"{item.a_value:.3e}",
            str(item.upper_ilev),
            str(item.upper_2j),
            str(item.lower_ilev),
            f"{item.upper_config}->{item.lower_config}",
            item.upper_label,
        ))
    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    lines = []
    for idx, row in enumerate(rows):
        lines.append("  ".join(v.ljust(widths[i]) for i, v in enumerate(row)))
        if idx == 0:
            lines.append("  ".join("-" * w for w in widths))
    return "\n".join(lines)
