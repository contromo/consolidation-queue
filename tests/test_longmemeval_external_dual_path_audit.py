import unittest

from cq.eval.external.longmemeval import dual_path_audit as audit


class LongMemEvalDualPathAuditTests(unittest.TestCase):
    def test_audit_classifies_agreement_and_disagreements(self) -> None:
        path_a = {
            "agree": {
                "case_id": "agree",
                "relevant_canonical_id": "current-home",
                "scope_level": "user_global",
                "scope_key": "user",
                "contradiction_edges": [["e1", "e2"]],
            },
            "canon": {
                "case_id": "canon",
                "relevant_canonical_id": "a",
                "scope_level": "user_global",
                "scope_key": "user",
                "contradiction_edges": [["e1", "e2"]],
            },
            "edge": {
                "case_id": "edge",
                "relevant_canonical_id": "same",
                "scope_level": "user_global",
                "scope_key": "user",
                "contradiction_edges": [["e1", "e2"]],
            },
            "scope": {
                "case_id": "scope",
                "relevant_canonical_id": "same",
                "scope_level": "user_global",
                "scope_key": "user",
                "contradiction_edges": [],
            },
            "missing-b": {
                "case_id": "missing-b",
                "relevant_canonical_id": "same",
                "scope_level": "user_global",
                "scope_key": "user",
                "contradiction_edges": [],
            },
        }
        path_b = {
            "agree": {
                "case_id": "agree",
                "relevant_canonical_id": "current-home",
                "scope_level": "user_global",
                "scope_key": "user",
                "contradiction_edges": [["e2", "e1"]],
            },
            "canon": {
                "case_id": "canon",
                "relevant_canonical_id": "b",
                "scope_level": "user_global",
                "scope_key": "user",
                "contradiction_edges": [["e1", "e2"]],
            },
            "edge": {
                "case_id": "edge",
                "relevant_canonical_id": "same",
                "scope_level": "user_global",
                "scope_key": "user",
                "contradiction_edges": [["e3", "e4"]],
            },
            "scope": {
                "case_id": "scope",
                "relevant_canonical_id": "same",
                "scope_level": "project",
                "scope_key": "p",
                "contradiction_edges": [],
            },
            "missing-a": {
                "case_id": "missing-a",
                "relevant_canonical_id": "same",
                "scope_level": "user_global",
                "scope_key": "user",
                "contradiction_edges": [],
            },
        }

        report, agreed = audit.audit_annotation_maps(path_a, path_b)
        rows = {row["case_id"]: row for row in report["rows"]}

        self.assertEqual(rows["agree"]["status"], audit.AGREE)
        self.assertEqual(rows["canon"]["status"], audit.DISAGREE_CANONICAL_ID)
        self.assertEqual(rows["edge"]["status"], audit.DISAGREE_CONTRADICTION_EDGES)
        self.assertEqual(rows["scope"]["status"], audit.DISAGREE_SCOPE)
        self.assertEqual(rows["missing-a"]["status"], audit.MISSING_PATH_A)
        self.assertEqual(rows["missing-b"]["status"], audit.MISSING_PATH_B)
        self.assertEqual(len(agreed), 1)
        self.assertEqual(agreed[0]["case_id"], "agree")
        self.assertEqual(report["summary"]["comparable_in_denominator_count"], 4)
        self.assertEqual(report["summary"]["agreement_count"], 1)
        self.assertTrue(report["summary"]["bucket_c_dual_path_divergence_triggered"])

    def test_out_of_denominator_agreement_does_not_enter_agreed_subset(self) -> None:
        path_a = {
            "case": {
                "case_id": "case",
                "in_denominator": False,
                "relevant_canonical_id": "same",
                "scope_level": "user_global",
                "scope_key": "user",
                "contradiction_edges": [],
            }
        }
        path_b = dict(path_a)
        report, agreed = audit.audit_annotation_maps(path_a, path_b)
        self.assertEqual(report["rows"][0]["status"], audit.AGREE)
        self.assertEqual(agreed, [])
        self.assertEqual(report["summary"]["comparable_in_denominator_count"], 0)


if __name__ == "__main__":
    unittest.main()

