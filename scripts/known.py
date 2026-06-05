#!/usr/bin/env python3
"""Known-transition family matcher for FAC line tables.

Generic library for matching FAC computed transitions to known spectral
features by restricting candidates to the correct configuration families.
Prevents unrelated nearby lines from being mistaken for known transitions.

Usage:
  Customise KNOWN_PEAKS for your ion system (see "User data" section below),
  then either run this script directly:
    python3 known.py --en path/to/trial.en --tr path/to/trial.tr
  or import find_known_candidates() from another script.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


HC_EV_ANGSTROM = 12398.419843320026


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Level:
    ilev: int
    energy_eV: float
    parity: int
    vnl: int
    two_j: int
    config: str
    label: str


@dataclass(frozen=True)
class Transition:
    upper_ilev: int
    upper_2j: int
    lower_ilev: int
    lower_2j: int
    energy_eV: float
    gf: float
    a_value: float

    @property
    def wavelength_angstrom(self) -> float:
        return HC_EV_ANGSTROM / self.energy_eV

    @property
    def wavelength_nm(self) -> float:
        return self.wavelength_angstrom / 10.0


@dataclass(frozen=True)
class KnownPeak:
    peak_id: str
    exp_nm: float
    paper_fac_nm: float
    upper_config: str       # must match FAC .en column-7 label exactly, e.g. "4d9.5s1"
    lower_config: str       # must match FAC .en column-7 label exactly, e.g. "4d10"
    upper_2j: int           # 2*J of the upper level (from paper jj assignment)
    lower_2j: int           # 2*J of the lower level (ground state: 0)
    multipole: str
    note: str

    @property
    def transition(self) -> Optional[str]:
        """Simple transition label derived from config labels, e.g. '5s→4d'.

        Uses the module-level BASE_CONFIG to reconstruct shells that FAC hides
        in cross-block configs.  Returns None for multi-electron changes or
        unrecognised formats.
        """
        return derive_transition_label(self.upper_config, self.lower_config, BASE_CONFIG)


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

    @property
    def transition(self) -> Optional[str]:
        """Simple transition label derived from the matched config labels."""
        return derive_transition_label(self.upper_config, self.lower_config, BASE_CONFIG)


# ---------------------------------------------------------------------------
# User data — customise KNOWN_PEAKS for each ion system
# ---------------------------------------------------------------------------
#
# For each observed spectral feature, provide:
#   peak_id        unique label (used in output tables)
#   exp_nm         experimental wavelength (nm)
#   paper_fac_nm   FAC theoretical wavelength from the reference paper (nm)
#   upper_config   FAC .en column-7 config label of the upper level
#   lower_config   FAC .en column-7 config label of the lower level
#   multipole      "E1", "E2", "M1", …
#   note           free-text description
#
# The transition label (e.g. "5s→4d") is derived automatically from the
# upper_config / lower_config strings and does not need to be entered by hand.

# Active base configuration for this ion system.
# FAC hides shells that are at their maximum occupancy within each NBLOCK:
#   e.g. in the "4d" block, 4p6 is hidden; in the "4p5" block, 4d10 is hidden.
# Providing BASE_CONFIG lets derive_transition_label reconstruct the hidden
# shells before comparing upper and lower levels.
#   key   : shell name as it appears in FAC .en column-7 (e.g. "4d", "4p")
#   value : occupancy in the fully closed / reference configuration
# Set to {} to disable reconstruction (cross-block transitions return None).
#
# For I7+ (Pd-like, 46e, closed 1s..4s, active 4p6 4d10):
BASE_CONFIG: Dict[str, int] = {"4p": 6, "4d": 10}


# Current ion system: Pd-like I7+ (Z=53, 46 electrons)
# Reference: Kimura et al., PRA 102, 032807 (2020), Table I.
# Lines a,b = E2 (4d^-1 5s); d,e = E1 (4d^-1 5p); f,g = E1 (4d^-1 4f).
# Line c (19.6547 nm) is excluded: large theory/experiment deviation in paper.
KNOWN_PEAKS: List[KnownPeak] = [
    # Table I, I7+.  upper_2j / lower_2j from jj-coupling assignments in the paper.
    # a: (4d^-1_{5/2} 5s_{1/2})_J=2  E2 -> 4d10 (J=0)
    KnownPeak(
        peak_id="a_4d9_5s_E2",
        exp_nm=26.21,
        paper_fac_nm=26.24,
        upper_config="4d9.5s1",
        lower_config="4d10",
        upper_2j=4,
        lower_2j=0,
        multipole="E2",
        note="(4d-1_5/2 5s_1/2) J=2 -> 4d10",
    ),
    # b: (4d^-1_{3/2} 5s_{1/2})_J=2  E2 -> 4d10 (J=0)
    KnownPeak(
        peak_id="b_4d9_5s_E2",
        exp_nm=25.27,
        paper_fac_nm=25.27,
        upper_config="4d9.5s1",
        lower_config="4d10",
        upper_2j=4,
        lower_2j=0,
        multipole="E2",
        note="(4d-1_3/2 5s_1/2) J=2 -> 4d10",
    ),
    # d: (4d^-1_{3/2} 5p_{1/2})_J=1  E1 -> 4d10 (J=0)
    KnownPeak(
        peak_id="d_4d9_5p_E1",
        exp_nm=19.42,
        paper_fac_nm=19.45,
        upper_config="4d9.5p1",
        lower_config="4d10",
        upper_2j=2,
        lower_2j=0,
        multipole="E1",
        note="(4d-1_3/2 5p_1/2) J=1 -> 4d10",
    ),
    # e: (4d^-1_{3/2} 5p_{3/2})_J=1  E1 -> 4d10 (J=0)
    KnownPeak(
        peak_id="e_4d9_5p_E1",
        exp_nm=19.02,
        paper_fac_nm=19.09,
        upper_config="4d9.5p1",
        lower_config="4d10",
        upper_2j=2,
        lower_2j=0,
        multipole="E1",
        note="(4d-1_3/2 5p_3/2) J=1 -> 4d10",
    ),
    # f: (4d^-1_{5/2} 4f_{5/2})_J=1  E1 -> 4d10 (J=0)
    KnownPeak(
        peak_id="f_4d9_4f_E1",
        exp_nm=16.44,
        paper_fac_nm=16.56,
        upper_config="4d9.4f1",
        lower_config="4d10",
        upper_2j=2,
        lower_2j=0,
        multipole="E1",
        note="(4d-1_5/2 4f_5/2) J=1 -> 4d10",
    ),
    # g: (4d^-1_{3/2} 4f_{5/2})_J=1  E1 -> 4d10 (J=0)
    KnownPeak(
        peak_id="g_4d9_4f_E1",
        exp_nm=15.71,
        paper_fac_nm=15.77,
        upper_config="4d9.4f1",
        lower_config="4d10",
        upper_2j=2,
        lower_2j=0,
        multipole="E1",
        note="(4d-1_3/2 4f_5/2) J=1 -> 4d10",
    ),
]

# Backward-compatible alias.
KNOWN_I7_PEAKS = KNOWN_PEAKS


# ---------------------------------------------------------------------------
# Generic library — no user edits needed below
# ---------------------------------------------------------------------------

def _parse_config_str(config_str: str) -> Dict[str, int]:
    """Parse a FAC short config label into a {shell: occupancy} dict.

    Example: '4d9.5s1' -> {'4d': 9, '5s': 1}
    Recognises shell names of the form <n><l> where l in spdfghik.
    """
    return {
        shell: int(count)
        for shell, count in re.findall(r"(\d+[spdfghik])(\d+)", config_str)
    }


def derive_transition_label(
    upper_config: str,
    lower_config: str,
    base_config: Optional[Dict[str, int]] = None,
) -> Optional[str]:
    """Derive a simple emission transition label from FAC config strings.

    FAC hides shells that are at their "block reference" occupancy in the short
    config label (column 7 of the .en file).  Different blocks may hide
    different shells, so a direct comparison can fail across blocks.  Providing
    *base_config* (the active reference occupancy of the ion) fills in those
    hidden shells before comparing.

    For a single-electron change, returns e.g. '5s→4d' (the 5s electron falls
    to fill the 4d hole, emitting a photon).  Returns None when the change
    involves more than one electron, or when the config strings cannot be
    parsed.

    Parameters
    ----------
    upper_config, lower_config:
        FAC .en column-7 config labels.
    base_config:
        Dict of {shell: max_occupancy} for active shells in the ion ground
        state.  Hidden shells (not in the label) are assumed to be at this
        occupancy.  If None, no reconstruction is attempted.

    Examples
    --------
    >>> derive_transition_label('4d9.5s1', '4d10')
    '5s→4d'
    >>> derive_transition_label('4p5.4f1', '4d10', base_config={'4p':6,'4d':10})
    '4f→4p'
    """
    upper = _parse_config_str(upper_config)
    lower = _parse_config_str(lower_config)

    if base_config:
        # Fill in shells that FAC omitted because they are at reference occupancy.
        # {**base_config, **parsed} keeps the parsed value where present,
        # and the base value for shells that were hidden.
        upper = {**base_config, **upper}
        lower = {**base_config, **lower}

    all_shells = set(upper) | set(lower)

    # shells with more electrons in the upper level (electron sits here)
    gains = {s: upper.get(s, 0) - lower.get(s, 0)
             for s in all_shells if upper.get(s, 0) > lower.get(s, 0)}
    # shells with fewer electrons in the upper level (hole sits here)
    losses = {s: lower.get(s, 0) - upper.get(s, 0)
              for s in all_shells if lower.get(s, 0) > upper.get(s, 0)}

    if sum(gains.values()) == 1 and sum(losses.values()) == 1:
        source = next(iter(gains))   # electron position in upper level
        dest = next(iter(losses))    # hole position in upper level
        return f"{source}→{dest}"   # e.g. "5s→4d"

    return None


def parse_en_table(path: Path) -> Dict[int, Level]:
    """Parse a FAC ASCII .en file.

    Column layout (split by whitespace):
      ILEV  IBASE  ENERGY  P  VNL  2J  <compact>  <short-config>  <jj-label...>
    parts[7] is the short configuration label used for family matching.
    """
    levels: Dict[int, Level] = {}
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) < 8:
                continue
            try:
                ilev = int(parts[0])
                int(parts[1])
                energy = float(parts[2])
                parity = int(parts[3])
                vnl = int(parts[4])
                two_j = int(parts[5])
            except ValueError:
                continue
            levels[ilev] = Level(
                ilev=ilev,
                energy_eV=energy,
                parity=parity,
                vnl=vnl,
                two_j=two_j,
                config=parts[7],
                label=" ".join(parts[8:]),
            )
    return levels


def parse_tr_table(path: Path) -> List[Transition]:
    """Parse a FAC 1.1.5 ASCII .tr file.

    Column order: upper_ilev upper_2J lower_ilev lower_2J dE[eV] gf A[s^-1] gf
    """
    transitions: List[Transition] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) not in (8, 10):
                continue
            try:
                upper_ilev = int(parts[0])
                upper_2j = int(parts[1])
                lower_ilev = int(parts[2])
                lower_2j = int(parts[3])
                energy = float(parts[4])
                gf = float(parts[5])
                a_value = float(parts[6])
            except ValueError:
                continue
            if energy <= 0.0:
                continue
            transitions.append(
                Transition(
                    upper_ilev=upper_ilev,
                    upper_2j=upper_2j,
                    lower_ilev=lower_ilev,
                    lower_2j=lower_2j,
                    energy_eV=energy,
                    gf=gf,
                    a_value=a_value,
                )
            )
    return transitions


def find_candidates(
    transitions: Iterable[Transition],
    levels: Dict[int, Level],
    target_nm: float,
    upper_config: str,
    lower_config: str = "4d10",
    upper_2j: Optional[int] = None,
    lower_2j: Optional[int] = None,
    top_n: int = 5,
) -> List[Candidate]:
    """Return the top_n transitions from upper_config -> lower_config closest to target_nm.

    upper_2j / lower_2j: if not None, only transitions whose level 2J matches
    exactly are considered.  This removes contamination from other J values in
    the same configuration family.
    """
    target_angstrom = target_nm * 10.0
    candidates: List[Candidate] = []
    for transition in transitions:
        upper = levels.get(transition.upper_ilev)
        lower = levels.get(transition.lower_ilev)
        if upper is None or lower is None:
            continue
        if upper.config != upper_config or lower.config != lower_config:
            continue
        if upper_2j is not None and upper.two_j != upper_2j:
            continue
        if lower_2j is not None and lower.two_j != lower_2j:
            continue
        residual = target_angstrom - transition.wavelength_angstrom
        candidates.append(
            Candidate(
                peak_id="",
                target_nm=target_nm,
                paper_fac_nm=0.0,
                multipole="",
                upper_ilev=transition.upper_ilev,
                upper_2j=transition.upper_2j,
                lower_ilev=transition.lower_ilev,
                lower_2j=transition.lower_2j,
                wavelength_nm=transition.wavelength_nm,
                residual_angstrom=residual,
                a_value=transition.a_value,
                gf=transition.gf,
                upper_config=upper.config,
                lower_config=lower.config,
                upper_label=upper.label,
                lower_label=lower.label,
            )
        )
    candidates.sort(key=lambda item: abs(item.residual_angstrom))
    return candidates[:top_n]


def find_known_candidates(
    peaks: List[KnownPeak],
    en_path: Path,
    tr_path: Path,
    top_n: int = 5,
    use_paper_fac_target: bool = False,
) -> List[Candidate]:
    """Find FAC transition candidates for each peak in *peaks*, restricted to
    the expected configuration families.

    Parameters
    ----------
    peaks:
        List of KnownPeak entries defining the target features.
    en_path / tr_path:
        FAC ASCII level and transition tables.
    top_n:
        Maximum candidates per peak, sorted by |residual|.
    use_paper_fac_target:
        If True, match against paper_fac_nm; otherwise against exp_nm.
    """
    levels = parse_en_table(en_path)
    transitions = parse_tr_table(tr_path)
    all_candidates: List[Candidate] = []
    for peak in peaks:
        target_nm = peak.paper_fac_nm if use_paper_fac_target else peak.exp_nm
        raw = find_candidates(
            transitions,
            levels,
            target_nm=target_nm,
            upper_config=peak.upper_config,
            lower_config=peak.lower_config,
            upper_2j=peak.upper_2j,
            lower_2j=peak.lower_2j,
            top_n=top_n,
        )
        for candidate in raw:
            all_candidates.append(
                Candidate(
                    peak_id=peak.peak_id,
                    target_nm=target_nm,
                    paper_fac_nm=peak.paper_fac_nm,
                    multipole=peak.multipole,
                    upper_ilev=candidate.upper_ilev,
                    upper_2j=candidate.upper_2j,
                    lower_ilev=candidate.lower_ilev,
                    lower_2j=candidate.lower_2j,
                    wavelength_nm=candidate.wavelength_nm,
                    residual_angstrom=candidate.residual_angstrom,
                    a_value=candidate.a_value,
                    gf=candidate.gf,
                    upper_config=candidate.upper_config,
                    lower_config=candidate.lower_config,
                    upper_label=candidate.upper_label,
                    lower_label=candidate.lower_label,
                )
            )
    return all_candidates


def find_known_i7_candidates(
    en_path: Path,
    tr_path: Path,
    top_n: int = 5,
    use_paper_fac_target: bool = False,
) -> List[Candidate]:
    """Backward-compatible wrapper: calls find_known_candidates(KNOWN_PEAKS, ...)."""
    return find_known_candidates(KNOWN_PEAKS, en_path, tr_path, top_n, use_paper_fac_target)


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List known-transition candidates by configuration family."
    )
    parser.add_argument("--en", type=Path, required=True, help="FAC ASCII level table (.en).")
    parser.add_argument("--tr", type=Path, required=True, help="FAC ASCII transition table (.tr).")
    parser.add_argument("--top", type=int, default=4, help="Candidates per known peak.")
    parser.add_argument(
        "--target",
        choices=("experiment", "paper-fac"),
        default="experiment",
        help="Use experimental or paper FAC wavelengths as targets.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidates = find_known_candidates(
        KNOWN_PEAKS,
        en_path=args.en,
        tr_path=args.tr,
        top_n=args.top,
        use_paper_fac_target=args.target == "paper-fac",
    )
    print(format_candidates(candidates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
