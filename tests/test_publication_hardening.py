import unittest
import tempfile
from pathlib import Path

from cq.eval.publication_hardening import (
    MAX_API_COST_CEILING_USD,
    PAPER_POLICY_TO_RUNNER_KEY,
    POLICY_SET_KEYS,
    STEP3_CQR_SCOPE,
    DistractorFloorRow,
    evaluate_distractor_floor,
    validate_api_model_pin,
    validate_pflc_record,
    validate_pflc_jsonl_lines,
    validate_policy_name_mapping,
)
from cq.eval import publication_hardening_lock as lock
from cq.eval.runner import (
    POLICY_SET_CHOICES,
    POLICY_SET_PHASE_2_5,
    POLICY_SET_PHASE_2_5_FOLLOWUP,
)


SOURCE_SHA = "a" * 64


class PFLCContractTests(unittest.TestCase):
    def test_evidence_record_validates(self) -> None:
        record = {
            "target_kind": "evidence_id",
            "question_id": "q1",
            "source_sha256": SOURCE_SHA,
            "gold_evidence_ids": ["dia-1"],
            "returned_evidence_ids": ["dia-1", "dia-2"],
            "answer_text": "answer",
            "system_label": "amb-locomo-hindsight",
            "manifest_path": "data/results/example_manifest.json",
        }
        self.assertEqual(validate_pflc_record(record), [])

    def test_fact_record_allows_memory_id_readout(self) -> None:
        record = {
            "target_kind": "fact_id",
            "question_id": "q1",
            "source_sha256": SOURCE_SHA,
            "gold_fact_ids": ["fact-1"],
            "returned_memory_ids": ["mem-1"],
            "answer_text": "answer",
            "system_label": "membench-worked-example",
            "manifest_path": "data/results/example_manifest.json",
        }
        self.assertEqual(validate_pflc_record(record), [])

    def test_missing_fact_readout_is_invalid(self) -> None:
        record = {
            "target_kind": "fact_id",
            "question_id": "q1",
            "source_sha256": SOURCE_SHA,
            "gold_fact_ids": ["fact-1"],
            "answer_text": "answer",
            "system_label": "membench-worked-example",
            "manifest_path": "data/results/example_manifest.json",
        }
        self.assertIn(
            "fact_id rows require returned_fact_ids or returned_memory_ids",
            validate_pflc_record(record),
        )

    def test_jsonl_lines_report_line_scoped_errors(self) -> None:
        valid = (
            '{"target_kind":"evidence_id","question_id":"q1",'
            '"source_sha256":"' + SOURCE_SHA + '",'
            '"gold_evidence_ids":["dia-1"],"returned_evidence_ids":[],'
            '"answer_text":"answer","system_label":"system",'
            '"manifest_path":"data/results/manifest.json"}'
        )
        errors = validate_pflc_jsonl_lines([valid, "{bad json", "[]"])
        self.assertEqual(len(errors), 2)
        self.assertIn("line 2: invalid JSON", errors[0])
        self.assertEqual(errors[1], "line 3: record must be a JSON object")


class DistractorFloorTests(unittest.TestCase):
    def test_floor_uses_post_adapter_visible_ids(self) -> None:
        result = evaluate_distractor_floor(
            [
                DistractorFloorRow(
                    case_id="case-1",
                    gold_ids=["gold-1", "gold-2"],
                    policy_visible_ids=[
                        "gold-1",
                        "gold-2",
                        *[f"distractor-{i}" for i in range(20)],
                    ],
                ),
                DistractorFloorRow(
                    case_id="case-2",
                    gold_ids=["gold-3"],
                    policy_visible_ids=["gold-3", *[f"other-{i}" for i in range(10)]],
                ),
            ]
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.average_non_gold_to_gold, 10.0)
        self.assertEqual(result.minimum_case_ratio, 10.0)

    def test_empty_gold_ids_fail_closed(self) -> None:
        result = evaluate_distractor_floor(
            [DistractorFloorRow(case_id="case-1", gold_ids=[], policy_visible_ids=["x"])]
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.case_count, 0)
        self.assertIn("case-1: gold_ids must contain at least one id", result.errors)


class PublicationHardeningLockTests(unittest.TestCase):
    def test_committed_preregistration_lock_validates(self) -> None:
        observed = lock.validate_publication_hardening_lock()
        self.assertEqual(
            observed,
            "05671290ae8ebcc665c915521128c18c48b13be075ace55472b5931874672590",
        )

    def test_publication_hardening_lock_matches_block_content(self) -> None:
        text = lock.PREREGISTRATION_PATH.read_text(encoding="utf-8")
        declared = lock.declared_publication_hardening_lock(text)
        computed = lock.compute_publication_hardening_lock_sha256(text)
        self.assertEqual(declared, computed)

    def test_temp_preregistration_lock_recomputes_from_protocol_block(self) -> None:
        body = """# temp

publication_hardening_lock_sha256: {sha}

outside text does not affect the lock

<!-- PUBLICATION_HARDENING_PROTOCOL_START -->
locked line
<!-- PUBLICATION_HARDENING_PROTOCOL_END -->
"""
        sha = lock.compute_publication_hardening_lock_sha256(body.format(sha="0" * 64))
        text = body.format(sha=sha)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "publication_hardening.md"
            path.write_text(text, encoding="utf-8")
            self.assertEqual(lock.validate_publication_hardening_lock(path), sha)

    def test_publication_lock_normalizes_crlf_and_block_bom(self) -> None:
        lf_body = """publication_hardening_lock_sha256: {sha}

<!-- PUBLICATION_HARDENING_PROTOCOL_START -->
locked line
<!-- PUBLICATION_HARDENING_PROTOCOL_END -->
"""
        crlf_body = lf_body.replace("locked line", "\ufefflocked line").replace("\n", "\r\n")
        self.assertEqual(
            lock.compute_publication_hardening_lock_sha256(lf_body.format(sha="0" * 64)),
            lock.compute_publication_hardening_lock_sha256(crlf_body.format(sha="0" * 64)),
        )

    def test_publication_lock_mismatch_raises(self) -> None:
        text = """publication_hardening_lock_sha256: {}

<!-- PUBLICATION_HARDENING_PROTOCOL_START -->
locked line
<!-- PUBLICATION_HARDENING_PROTOCOL_END -->
""".format("0" * 64)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "publication_hardening.md"
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(lock.PublicationHardeningLockError):
                lock.validate_publication_hardening_lock(path)

    def test_policy_display_names_map_to_runner_keys(self) -> None:
        self.assertEqual(validate_policy_name_mapping(), [])
        self.assertEqual(PAPER_POLICY_TO_RUNNER_KEY["Mem0 WritePolicy Lite"], "mem0_lite")

    def test_policy_sets_are_existing_runner_choices(self) -> None:
        self.assertEqual(POLICY_SET_KEYS["original_internal_headline"], POLICY_SET_PHASE_2_5)
        self.assertEqual(POLICY_SET_KEYS["cq_multi_followup"], POLICY_SET_PHASE_2_5_FOLLOWUP)
        self.assertEqual(POLICY_SET_KEYS["fresh_archived_cqr_replay"], POLICY_SET_PHASE_2_5)
        self.assertTrue(set(POLICY_SET_KEYS.values()).issubset(set(POLICY_SET_CHOICES)))

    def test_step3_scope_is_not_full_phase4(self) -> None:
        self.assertEqual(
            STEP3_CQR_SCOPE["thesis_families"],
            ("useful_pending_memory", "memory_poisoning"),
        )
        self.assertEqual(STEP3_CQR_SCOPE["minimum_alias_cqr_hits_per_thesis_family"], 5)
        self.assertEqual(STEP3_CQR_SCOPE["policy_set"], POLICY_SET_PHASE_2_5)

    def test_api_model_pin_requires_cache_and_budget(self) -> None:
        valid_pin = {
            "provider": "example-provider",
            "model_id": "example-model",
            "fallback_model_id": "example-fallback",
            "cost_ceiling_usd": 100.0,
            "stability_check": "cached replay plus model/provider sensitivity cell",
            "cache_required": True,
        }
        self.assertEqual(validate_api_model_pin(valid_pin), [])
        invalid_pin = {**valid_pin, "cache_required": False, "cost_ceiling_usd": 0}
        errors = validate_api_model_pin(invalid_pin)
        self.assertIn("cache_required must be true", errors)
        self.assertIn("cost_ceiling_usd must be a positive number", errors)
        too_expensive = {**valid_pin, "cost_ceiling_usd": MAX_API_COST_CEILING_USD + 1}
        self.assertIn(
            "cost_ceiling_usd must be <= {}".format(int(MAX_API_COST_CEILING_USD)),
            validate_api_model_pin(too_expensive),
        )

    def test_api_model_pin_treats_fallback_as_optional(self) -> None:
        # Preregistration says "fallback model id, if any". A pin without
        # fallback_model_id must validate; one with an explicit null must too.
        base_pin = {
            "provider": "example-provider",
            "model_id": "example-model",
            "cost_ceiling_usd": 100.0,
            "stability_check": "cached replay plus model/provider sensitivity cell",
            "cache_required": True,
        }
        self.assertEqual(validate_api_model_pin(base_pin), [])
        with_null_fallback = {**base_pin, "fallback_model_id": None}
        self.assertEqual(validate_api_model_pin(with_null_fallback), [])
        # But a non-string truthy-but-invalid value should still be rejected.
        with_empty_fallback = {**base_pin, "fallback_model_id": ""}
        self.assertIn(
            "fallback_model_id, when provided, must be a non-empty string",
            validate_api_model_pin(with_empty_fallback),
        )


if __name__ == "__main__":
    unittest.main()
