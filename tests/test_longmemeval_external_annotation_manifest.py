import json
import tempfile
import unittest
from pathlib import Path

from cq.eval.external.longmemeval import annotation_manifest
from cq.eval.external.longmemeval.preregistration_lock import (
    validate_fair_stream_externalization_lock,
)


class LongMemEvalAnnotationManifestTests(unittest.TestCase):
    def test_manifest_records_input_output_hashes_and_gate_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            oracle = _write(tmp / "oracle.json", '[{"question_id": "case"}]\n')
            feasibility = _write(tmp / "feasibility.csv", "question_id,label\ncase,contradiction_edge\n")
            path_a = _write(tmp / "a.json", '{"annotations": []}\n')
            path_b = _write(tmp / "b.json", '{"annotations": []}\n')
            agreed = _write(tmp / "agreed.json", '{"annotations": []}\n')
            divergence = _write(
                tmp / "divergence.json",
                json.dumps(
                    {
                        "summary": {
                            "agreement_count": 1,
                            "comparable_in_denominator_count": 1,
                        }
                    },
                    sort_keys=True,
                )
                + "\n",
            )
            verifier = _write(
                tmp / "verifier.json",
                json.dumps(
                    {
                        "verifier_passed": True,
                        "audit_summary_present": True,
                        "hidden_answer_check_passed": True,
                        "agreement_rate_check_passed": True,
                        "binomial_check_passed": True,
                    },
                    sort_keys=True,
                )
                + "\n",
            )

            manifest = annotation_manifest.build_manifest(
                oracle_json=oracle,
                feasibility_csv=feasibility,
                path_a_json=path_a,
                path_b_json=path_b,
                agreed_json=agreed,
                divergence_json=divergence,
                verifier_json=verifier,
                preregistration_lock_sha256="abc",
            )

        self.assertEqual(manifest["preregistration_lock_sha256"], "abc")
        self.assertEqual(manifest["audit_summary"]["agreement_count"], 1)
        self.assertTrue(manifest["verifier_summary"]["verifier_passed"])
        self.assertIn("oracle_json_sha256", manifest["inputs"])
        self.assertIn("annotations_path_a_json_sha256", manifest["outputs"])

    def test_committed_manifest_uses_live_preregistration_lock(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "external"
            / "longmemeval"
            / "annotations_manifest.json"
        )
        manifest = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            manifest["preregistration_lock_sha256"],
            validate_fair_stream_externalization_lock(),
        )


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
