import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.known import (
    find_candidates,
    parse_en_table,
    parse_tr_table,
)


class KnownTransitionTests(unittest.TestCase):
    def test_filters_known_family_to_ground_transitions(self):
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            en_path = tmp / "sample.en"
            tr_path = tmp / "sample.tr"

            en_path.write_text(
                "\n".join(
                    [
                        "  ILEV  IBASE    ENERGY       P   VNL         2J",
                        "     0     -1  0.00000000E+00 0   402          0 4*18                             4d10                                             4d+6(0)0",
                        "     3     -1  5.11985607E+01 0   500          2 4*17.5*1                         4d9.5s1                                          4d-3(3)3.5s+1(1)2",
                        "    30     -1  8.20059810E+01 1   403          8 4*18                             4d9.4f1                                          4d+5(5)5.4f-1(5)8",
                        "   230     -1  1.29255332E+02 0   501          8 4*16.5*2                         4d8.5p2                                          4d+4(8)8.5p-1(1)7.5p+1(3)8",
                    ]
                ),
                encoding="utf-8",
            )
            tr_path.write_text(
                "\n".join(
                    [
                        "FAC 1.1.5",
                        "   230          8     30          8  4.724935E+01  1.693593E-04  1.822921E+06  1.693593E-04",
                        "     3          2      0          0  5.119856E+01  5.281536E-13  2.002461E-02  5.281536E-13",
                    ]
                ),
                encoding="utf-8",
            )

            levels = parse_en_table(en_path)
            transitions = parse_tr_table(tr_path)
            candidates = find_candidates(
                transitions,
                levels,
                target_nm=26.21,
                upper_config="4d9.5s1",
                lower_config="4d10",
                top_n=5,
            )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].upper_ilev, 3)
        self.assertEqual(candidates[0].lower_ilev, 0)
        self.assertEqual(candidates[0].upper_config, "4d9.5s1")


if __name__ == "__main__":
    unittest.main()
