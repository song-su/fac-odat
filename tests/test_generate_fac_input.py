import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scripts.generate_fac_input import build_fac_script, expand_template


L_SYMBOL_MAP = {str(key): value for key, value in {
    0: "s",
    1: "p",
    2: "d",
    3: "f",
    4: "g",
    5: "h",
    6: "i",
    7: "k",
}.items()}


class GenerateFacInputTests(unittest.TestCase):
    def test_nl_defaults_to_principal_quantum_number_groups(self):
        template = {
            "id": "hole_4d9_nl",
            "prefix": "4p6 4d9",
            "active": "nl",
            "n": [5, 6],
            "l": [0, 1, 2, 3],
        }

        self.assertEqual(
            expand_template(template, L_SYMBOL_MAP),
            [
                ("hole_4d9_nl", "4p6 4d9 5[s,p,d,f]"),
                ("hole_4d9_nl", "4p6 4d9 6[s,p,d,f]"),
            ],
        )

    def test_nl_can_split_each_angular_subshell_into_its_own_group(self):
        template = {
            "id": "hole_4d9_nl",
            "prefix": "4p6 4d9",
            "active": "nl",
            "group_by": "l",
            "n": [5, 6],
            "l": [0, 1, 2, 3],
        }

        self.assertEqual(
            expand_template(template, L_SYMBOL_MAP),
            [
                ("hole_4d9_nl", "4p6 4d9 5s"),
                ("hole_4d9_nl", "4p6 4d9 5p"),
                ("hole_4d9_nl", "4p6 4d9 5d"),
                ("hole_4d9_nl", "4p6 4d9 5f"),
                ("hole_4d9_nl", "4p6 4d9 6s"),
                ("hole_4d9_nl", "4p6 4d9 6p"),
                ("hole_4d9_nl", "4p6 4d9 6d"),
                ("hole_4d9_nl", "4p6 4d9 6f"),
            ],
        )

    def test_mk_can_split_each_k_subshell_into_its_own_group(self):
        template = {
            "id": "hole_mk",
            "prefix": "4f13",
            "active": "mk",
            "group_by": "k",
            "m": [5, 6],
            "k": [0, 1, 2],
        }

        self.assertEqual(
            expand_template(template, L_SYMBOL_MAP),
            [
                ("hole_mk", "4f13 5s"),
                ("hole_mk", "4f13 5p"),
                ("hole_mk", "4f13 5d"),
                ("hole_mk", "4f13 6s"),
                ("hole_mk", "4f13 6p"),
                ("hole_mk", "4f13 6d"),
            ],
        )

    def test_angular_split_still_filters_invalid_l_for_n(self):
        template = {
            "id": "hole_4d9_nl",
            "prefix": "4p6 4d9",
            "active": "nl",
            "group_by": "l",
            "n": [4],
            "l": [0, 1, 2, 3, 4],
        }

        self.assertEqual(
            expand_template(template, L_SYMBOL_MAP),
            [
                ("hole_4d9_nl", "4p6 4d9 4s"),
                ("hole_4d9_nl", "4p6 4d9 4p"),
                ("hole_4d9_nl", "4p6 4d9 4d"),
                ("hole_4d9_nl", "4p6 4d9 4f"),
            ],
        )

    def test_build_script_can_split_nl_and_mk_in_the_same_input(self):
        config = {
            "target": {"reference_peaks": [], "conversion": {"hc_eV_angstrom": 1.0, "nm_to_angstrom": 10.0}},
            "ion": {"element": "I", "Z": 53, "charge_state": 7, "K": 46},
            "fac_input": {
                "output_prefix": "I46",
                "potential_file": "I7.pot",
                "parallel": {"nproc": 12},
                "set_uta": 0,
                "closed_shells": [],
            },
            "configuration_space": {
                "generated_group_prefix": {"bound": "n"},
                "l_symbol_map": L_SYMBOL_MAP,
                "templates": {
                    "bound": [
                        {"id": "ground", "prefix": "4p6 4d10", "active": None},
                        {
                            "id": "nl_family",
                            "prefix": "4p6 4d9",
                            "active": "nl",
                            "group_by": "l",
                            "n": [5],
                            "l": [0, 1],
                        },
                        {
                            "id": "mk_family",
                            "prefix": "4f13",
                            "active": "mk",
                            "group_by": "k",
                            "m": [6],
                            "k": [0, 1],
                        },
                    ]
                },
            },
            "radial_potential": {
                "optimize_radial_groups": ["ground", "nl_family", "mk_family"],
                "save_potential": False,
            },
            "calculation_steps": {
                "run_structure": True,
                "run_transition_table": False,
                "transition_table": {"fac_multipole": 0},
            },
        }

        script = build_fac_script(config)

        self.assertIn("fac.Config('4p6 4d9 5s', group='n3')", script)
        self.assertIn("fac.Config('4p6 4d9 5p', group='n4')", script)
        self.assertIn("fac.Config('4f13 6s', group='n5')", script)
        self.assertIn("fac.Config('4f13 6p', group='n6')", script)
        self.assertIn("fac.OptimizeRadial(['n2', 'n3', 'n4', 'n5', 'n6'])", script)


if __name__ == "__main__":
    unittest.main()
