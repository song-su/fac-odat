"""FAC ASCII output parsers.

parse_en_table : FAC .en level table  -> {ilev: Level}
parse_tr_table : FAC .tr transition table -> [Transition]

These types are FAC-specific.  The scoring layer (survey.scorer) receives
them through find_known_candidates and treats them as duck-typed containers.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from survey.peaks import HC_EV_ANGSTROM


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


def parse_en_table(path: Path) -> Dict[int, Level]:
    """Parse a FAC 1.1.5 ASCII .en file.

    Column layout (split by whitespace):
      ILEV  IBASE  ENERGY  P  VNL  2J  <compact>  <short-config>  <jj-label...>
    parts[7] is the short configuration label used for family matching.
    """
    levels: Dict[int, Level] = {}
    with Path(path).open("r", encoding="utf-8") as fh:
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
    with Path(path).open("r", encoding="utf-8") as fh:
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
            transitions.append(Transition(
                upper_ilev=upper_ilev,
                upper_2j=upper_2j,
                lower_ilev=lower_ilev,
                lower_2j=lower_2j,
                energy_eV=energy,
                gf=gf,
                a_value=a_value,
            ))
    return transitions
