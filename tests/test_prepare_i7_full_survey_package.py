import csv
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from config_loader import load_config
from prepare_i7_full_survey_package import prepare_package


class PrepareI7FullSurveyPackageTests(unittest.TestCase):
    def test_generates_all_template_combinations_for_both_grouping_modes(self):
        config = load_config(Path("survey/configs/i7plus_fac.py"))

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "package"
            metadata = prepare_package(
                config=config,
                output_dir=output_dir,
                input_path=Path("survey/configs/i7plus_fac.py"),
            )

            self.assertEqual(metadata["trial_count"], 1022)

            with (output_dir / "manifest.csv").open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))

            self.assertEqual(len(rows), 1022)
            self.assertEqual(sum(1 for row in rows if row["mode"] == "nm"), 511)
            self.assertEqual(sum(1 for row in rows if row["mode"] == "lk"), 511)

            nm_first = output_dir / rows[0]["trial_dir"] / "trial.py"
            lk_first = output_dir / rows[511]["trial_dir"] / "trial.py"
            self.assertIn("5[s,p,d,f]", nm_first.read_text(encoding="utf-8"))
            self.assertIn("fac.Config('4p6 4d9 5s'", lk_first.read_text(encoding="utf-8"))

            self.assertTrue((output_dir / "run_all.py").exists())
            self.assertTrue((output_dir / "score_known.py").exists())
            self.assertTrue((output_dir / "known.py").exists())
            self.assertTrue((output_dir / "i7plus_fac.py").exists())


if __name__ == "__main__":
    unittest.main()
