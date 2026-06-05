"""Pd-like I7+ (Z=53, 46 electrons) — physical data only.

Source: Kimura et al., PRA 102, 032807 (2020), Table I.

This module contains the KNOWN spectral features for I7+ and the BASE_CONFIG
needed to reconstruct FAC's hidden shells in config labels.
It has NO dependency on any atomic code (FAC, HULLAC, etc.).

FAC-specific survey configuration (which configurations to include,
OptimizeRadial strategies, scoring parameters) lives in:
  inputs/target_case_v4_I_survey.py
"""
from survey.peaks import KnownPeak
from typing import Dict, List

# FAC hides shells at their block-reference occupancy in short config labels.
# BASE_CONFIG reconstructs them for cross-block transition labelling.
# For I7+: active shells are 4p (max 6) and 4d (max 10).
BASE_CONFIG: Dict[str, int] = {"4p": 6, "4d": 10}

# Table I lines a,b,d,e,f,g (line c excluded: large theory/experiment gap).
# upper_2j / lower_2j from jj-coupling assignments in the paper.
KNOWN_PEAKS: List[KnownPeak] = [
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
