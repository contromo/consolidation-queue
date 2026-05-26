import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CQ_MULTI = _load(
    "build_cqmulti_per_row_regression_table",
    REPO_ROOT / "scripts" / "build_cqmulti_per_row_regression_table.py",
)
RANDOM_FLOOR = _load(
    "compute_all_hit_at_50_random_floor",
    REPO_ROOT / "scripts" / "compute_all_hit_at_50_random_floor.py",
)


class CQMultiRegressionTableTests(unittest.TestCase):
    def test_committed_artifacts_regenerate_zero_delta_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = Path(tmpdir) / "cqmulti.tex"
            json_path = Path(tmpdir) / "cqmulti.json"

            rc = CQ_MULTI.main(
                [
                    "--repo-root",
                    str(REPO_ROOT),
                    "--tex-output",
                    str(tex_path),
                    "--json-output",
                    str(json_path),
                ]
            )
            self.assertEqual(rc, 0)

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["max_abs_delta"], 0.0)
            self.assertEqual(len(payload["families"]), 5)
            self.assertTrue(
                all(row["max_abs_delta"] == 0.0 for row in payload["families"])
            )
            self.assertIn("aggregate maximum checked overall delta is 0.000000", tex_path.read_text(encoding="utf-8"))


class AllHitRandomFloorTests(unittest.TestCase):
    def test_closed_form_readout_floor(self) -> None:
        self.assertEqual(RANDOM_FLOOR._closed_form_all_hit(2, 2, 1), 0.0)
        self.assertEqual(RANDOM_FLOOR._closed_form_all_hit(2, 2, 2), 1.0)
        self.assertAlmostEqual(
            RANDOM_FLOOR._closed_form_all_hit(10, 2, 2),
            1 / 45,
            places=12,
        )

    def test_committed_transfer_rows_regenerate_floor_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = Path(tmpdir) / "floor.tex"
            json_path = Path(tmpdir) / "floor.json"

            rc = RANDOM_FLOOR.main(
                [
                    "--repo-root",
                    str(REPO_ROOT),
                    "--tex-output",
                    str(tex_path),
                    "--json-output",
                    str(json_path),
                ]
            )
            self.assertEqual(rc, 0)

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            by_cell = {row["cell_id"]: row for row in payload["cells"]}
            self.assertEqual(by_cell["primary_contract"]["case_count"], 71)
            self.assertEqual(by_cell["primary_contract"]["analytic_readout_1"], 0.0)
            self.assertEqual(by_cell["primary_contract"]["analytic_readout_2"], 1.0)
            self.assertEqual(by_cell["primary_contract"]["analytic_empirical_abs_delta"], 0.0)
            self.assertIn("Random $r{=}2$ & 5-seed", tex_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
