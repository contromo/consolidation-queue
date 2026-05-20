import json
import tempfile
import unittest
from pathlib import Path

from cq.eval.external.longmemeval import adapter
from cq.eval.external.longmemeval.preregistration_lock import (
    validate_fair_stream_externalization_lock,
)
from cq.schemas.memory import CandidateUpdate, ClaimType, ScopeLevel
from cq.schemas.scenario import EventKind, TaskFamily


class LongMemEvalAdapterTests(unittest.TestCase):
    def test_adapter_builds_hidden_answer_scenario_and_stream(self) -> None:
        scenario, stream = adapter.adapt_annotation(_annotation_row())

        self.assertEqual(scenario.scenario_id, "longmemeval_case-1")
        self.assertEqual(scenario.task_family, TaskFamily.LONGMEMEVAL_EXTERNAL)
        self.assertEqual([event.kind for event in scenario.oracle_events], [
            EventKind.OBSERVATION,
            EventKind.OBSERVATION,
            EventKind.QUESTION,
        ])
        question = scenario.oracle_events[-1].question
        self.assertIsNotNone(question)
        self.assertEqual(question.relevant_canonical_id, "lme-personal-best-time-charity-5k-run")
        self.assertEqual(question.gold_candidate_ids, [])
        self.assertEqual(question.forbidden_candidate_ids, [])
        self.assertTrue(scenario.latent_truth_graph["hidden_answer_protocol"])

        self.assertEqual(
            [candidate.candidate_id for candidate in stream.candidates],
            [
                "longmemeval_case-1::obs_0::0",
                "longmemeval_case-1::obs_1::0",
            ],
        )
        self.assertEqual(stream.candidates[0].claim_type, ClaimType.WORLD_FACT)
        self.assertEqual(stream.candidates[0].scope_level, ScopeLevel.USER_GLOBAL)
        self.assertEqual(stream.candidates[0].verification_score, 0.7)
        self.assertEqual(stream.candidates[1].contradicts, ["longmemeval_case-1::obs_0::0"])
        self.assertEqual(
            stream.source_session_id_by_candidate_id,
            {
                "longmemeval_case-1::obs_0::0": "s1",
                "longmemeval_case-1::obs_1::0": "s2",
            },
        )
        first_source_id = stream.candidates[0].provenance[0].source_id
        self.assertIn("opaque-session-", first_source_id)
        self.assertNotIn("s1", first_source_id)
        self.assertNotIn("answer_", first_source_id)
        self.assertEqual(stream.drops, [])

    def test_candidate_update_remains_mutable_for_adapter_edge_resolution(self) -> None:
        params = getattr(CandidateUpdate, "__dataclass_params__", None)

        self.assertIsNotNone(params)
        self.assertFalse(params.frozen)

        _, stream = adapter.adapt_annotation(_annotation_row())
        stream.candidates[0].contradicts = ["manual_edge"]

        self.assertEqual(stream.candidates[0].contradicts, ["manual_edge"])

    def test_adapter_stream_hash_is_deterministic_and_policy_invariant(self) -> None:
        annotations = [_annotation_row("case-1"), _annotation_row("case-2")]

        first_scenarios, first_streams = adapter.adapt_annotations(annotations)
        second_scenarios, second_streams = adapter.adapt_annotations(annotations)
        report = adapter.candidate_stream_hash_report(
            first_streams,
            ["consolidation_queue_lite", "reflection_eager_write_lite", "mem0_lite"],
        )

        self.assertEqual(
            [scenario.scenario_id for scenario in first_scenarios],
            [scenario.scenario_id for scenario in second_scenarios],
        )
        self.assertEqual(
            {
                key: stream.candidate_stream_sha256
                for key, stream in first_streams.items()
            },
            {
                key: stream.candidate_stream_sha256
                for key, stream in second_streams.items()
            },
        )
        self.assertEqual(report["candidate_stream_hash_mismatches"], [])

    def test_adapter_drops_malformed_candidate_events(self) -> None:
        row = _annotation_row()
        row["candidate_events"][0]["raw_claim"] = ""

        _, stream = adapter.adapt_annotation(row)

        self.assertEqual(len(stream.candidates), 1)
        self.assertEqual(stream.drops[0]["reason"], "empty_raw_claim")

    def test_committed_adapter_pin_validates_and_mismatches_fail(self) -> None:
        pin = adapter.validate_adapter_pin()

        self.assertEqual(pin["candidate_adapter_sha256"], adapter.live_adapter_sha256())
        self.assertEqual(
            pin["preregistration_lock_sha256"],
            validate_fair_stream_externalization_lock(),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            pin_path = Path(tmpdir) / "pin.json"
            pin_path.write_text(
                json.dumps(
                    {
                        "candidate_adapter_sha256": "0" * 64,
                        "preregistration_lock_sha256": validate_fair_stream_externalization_lock(),
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(adapter.LongMemEvalAdapterError):
                adapter.validate_adapter_pin(pin_path=pin_path)

    def test_dry_run_summary_validates_pin_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            annotations_path = Path(tmpdir) / "annotations.json"
            annotations_path.write_text(
                json.dumps({"annotations": [_annotation_row()]}),
                encoding="utf-8",
            )
            pin_path = Path(tmpdir) / "pin.json"
            pin_path.write_text(
                json.dumps(
                    {
                        "candidate_adapter_sha256": "0" * 64,
                        "preregistration_lock_sha256": validate_fair_stream_externalization_lock(),
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(adapter.LongMemEvalAdapterError):
                adapter.build_dry_run_summary(
                    annotations_path=annotations_path,
                    adapter_pin_path=pin_path,
                )

            summary = adapter.build_dry_run_summary(
                annotations_path=annotations_path,
                adapter_pin_path=pin_path,
                validate_pin=False,
            )

        self.assertEqual(summary["scenario_count"], 1)

    def test_load_agreed_annotations_rejects_answer_side_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "annotations.json"
            row = _annotation_row()
            row["answer"] = "25:50"
            path.write_text(json.dumps({"annotations": [row]}), encoding="utf-8")

            with self.assertRaises(adapter.LongMemEvalAdapterError) as context:
                adapter.load_agreed_annotations(path)

        self.assertIn("Forbidden answer-side keys", str(context.exception))

    def test_dry_run_summary_respects_case_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "annotations.json"
            path.write_text(
                json.dumps({"annotations": [_annotation_row("case-2"), _annotation_row("case-1")]}),
                encoding="utf-8",
            )

            summary = adapter.build_dry_run_summary(annotations_path=path, case_limit=1)

        self.assertEqual(summary["scenario_count"], 1)
        self.assertEqual(summary["candidate_count"], 2)
        self.assertTrue(summary["candidate_stream_hash_invariant_passed"])


def _annotation_row(case_id: str = "case-1") -> dict:
    return {
        "case_id": case_id,
        "question_type": "knowledge-update",
        "question": "What was my personal best time in the charity 5K run?",
        "in_denominator": True,
        "mechanism_code": "contradiction_edge",
        "relevant_canonical_id": "lme-personal-best-time-charity-5k-run",
        "scope_level": "user_global",
        "scope_key": "longmemeval:user",
        "claim_type": "world_fact",
        "contradiction_edges": [],
        "candidate_events": [
            {
                "event_id": "obs_0",
                "session_id": "s1",
                "session_index": 0,
                "session_date": "2023/05/25",
                "turn_index": 0,
                "raw_claim": "My personal best time in the charity 5K run is 27:12.",
                "canonical_id": "lme-personal-best-time-charity-5k-run",
                "claim_type": "world_fact",
                "scope_level": "user_global",
                "scope_key": "longmemeval:user",
                "confidence": 0.7,
                "contradicts_event_ids": [],
            },
            {
                "event_id": "obs_1",
                "session_id": "s2",
                "session_index": 1,
                "session_date": "2023/05/27",
                "turn_index": 0,
                "raw_claim": "I am hoping to beat my personal best time of 25:50.",
                "canonical_id": "lme-personal-best-time-charity-5k-run",
                "claim_type": "world_fact",
                "scope_level": "user_global",
                "scope_key": "longmemeval:user",
                "confidence": 0.7,
                "contradicts_event_ids": ["obs_0"],
            },
        ],
    }


if __name__ == "__main__":
    unittest.main()
