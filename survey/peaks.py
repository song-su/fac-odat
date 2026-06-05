"""Physical spectral data types — no dependency on any atomic code.

KnownPeak describes one spectral feature in terms of its atomic physics
(upper/lower level, J values, multipole order, reference wavelengths).
derive_transition_label converts FAC short config labels to a human-readable
emission label such as "5s→4d".
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional

HC_EV_ANGSTROM = 12398.419843320026


@dataclass(frozen=True)
class KnownPeak:
    """One known spectral feature to score against.

    Fields
    ------
    peak_id        : unique label used in output tables
    exp_nm         : experimental wavelength (nm)
    paper_fac_nm   : FAC theoretical wavelength from the reference paper (nm)
    upper_config   : FAC .en column-7 config label of the upper level
    lower_config   : FAC .en column-7 config label of the lower level
    upper_2j       : 2*J of the upper level (from paper jj assignment)
    lower_2j       : 2*J of the lower level
    multipole      : "E1", "E2", "M1", …
    note           : free-text description
    """
    peak_id: str
    exp_nm: float
    paper_fac_nm: float
    upper_config: str
    lower_config: str
    upper_2j: int
    lower_2j: int
    multipole: str
    note: str


def _parse_config_str(config_str: str) -> Dict[str, int]:
    """Parse a FAC short config label into {shell: occupancy}.

    Example: '4d9.5s1' -> {'4d': 9, '5s': 1}
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
    """Derive a simple emission label from FAC config strings.

    FAC hides shells at their block-reference occupancy.  Providing
    *base_config* (the active-shell reference occupancy) fills them back in
    before comparing upper and lower levels.

    Returns e.g. '5s→4d' for a single-electron change; None otherwise.

    Examples
    --------
    >>> derive_transition_label('4d9.5s1', '4d10')
    '5s→4d'
    >>> derive_transition_label('4p5.4f1', '4d10', {'4p': 6, '4d': 10})
    '4f→4p'
    """
    upper = _parse_config_str(upper_config)
    lower = _parse_config_str(lower_config)

    if base_config:
        upper = {**base_config, **upper}
        lower = {**base_config, **lower}

    all_shells = set(upper) | set(lower)
    gains = {s: upper.get(s, 0) - lower.get(s, 0)
             for s in all_shells if upper.get(s, 0) > lower.get(s, 0)}
    losses = {s: lower.get(s, 0) - upper.get(s, 0)
              for s in all_shells if lower.get(s, 0) > upper.get(s, 0)}

    if sum(gains.values()) == 1 and sum(losses.values()) == 1:
        source = next(iter(gains))
        dest = next(iter(losses))
        return f"{source}→{dest}"
    return None
