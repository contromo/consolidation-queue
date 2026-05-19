import json
import tempfile
import unittest
from pathlib import Path

from cq.eval.external.longmemeval.judge_calibration_set import (
    build_calibration_set,
    write_calibration_artifacts,
)


class LongMemEvalJudgeCalibrationSetTests(unittest.TestCase):
    def test_builds_stratified_calibration_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _write_inputs(Path(tmpdir))
            payload, manifest = build_calibration_set(
                agreed_annotations_path=paths["annotations"],
                oracle_json_path=paths["oracle"],
                smoke_summary_path=paths["smoke"],
                source_policy="no_memory_lite",
            )

        self.assertEqual(payload["case_count"], 25)
        self.assertEqual(
            payload["stratum_counts"],
            {
                "control_negative": 5,
                "control_positive": 5,
                "realistic": 15,
            },
        )
        self.assertEqual(payload["source_policy"], "no_memory_lite")
        self.assertEqual(manifest["gold_access"], "gold_loader_only")
        self.assertEqual(manifest["source_policy"], "no_memory_lite")
        realistic = [row for row in payload["cases"] if row["stratum"] == "realistic"]
        self.assertEqual(len(realistic), 15)
        self.assertTrue(all(row["candidate_answer"] == "No memory available." for row in realistic))
        positives = [row for row in payload["cases"] if row["stratum"] == "control_positive"]
        negatives = [row for row in payload["cases"] if row["stratum"] == "control_negative"]
        self.assertTrue(all(row["candidate_answer"] == row["gold_answer"] for row in positives))
        self.assertTrue(all(row["candidate_answer"] == "I do not know." for row in negatives))
        self.assertTrue(all(row["expected_verdict"] == "correct" for row in positives))
        self.assertTrue(all(row["expected_verdict"] == "incorrect" for row in negatives))

    def test_payload_uses_gold_answer_field_only_for_answer_side_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = _write_inputs(Path(tmpdir))
            payload, _manifest = build_calibration_set(
                agreed_annotations_path=paths["annotations"],
                oracle_json_path=paths["oracle"],
                smoke_summary_path=paths["smoke"],
                source_policy="no_memory_lite",
            )

        forbidden_keys = _keys_containing_answer(payload)
        self.assertEqual(forbidden_keys, {"gold_answer", "candidate_answer"})

    def test_writes_byte_stable_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            paths = _write_inputs(tmp)
            output = tmp / "judge_calibration_set.json"
            manifest_path = tmp / "judge_calibration_set_manifest.json"
            first_payload, first_manifest = build_calibration_set(
                agreed_annotations_path=paths["annotations"],
                oracle_json_path=paths["oracle"],
                smoke_summary_path=paths["smoke"],
                source_policy="no_memory_lite",
            )
            write_calibration_artifacts(
                output_json=output,
                manifest_json=manifest_path,
                payload=first_payload,
                manifest=first_manifest,
            )
            first_set = output.read_bytes()
            first_manifest_bytes = manifest_path.read_bytes()

            second_payload, second_manifest = build_calibration_set(
                agreed_annotations_path=paths["annotations"],
                oracle_json_path=paths["oracle"],
                smoke_summary_path=paths["smoke"],
                source_policy="no_memory_lite",
            )
            write_calibration_artifacts(
                output_json=output,
                manifest_json=manifest_path,
                payload=second_payload,
                manifest=second_manifest,
            )

            self.assertEqual(output.read_bytes(), first_set)
            self.assertEqual(manifest_path.read_bytes(), first_manifest_bytes)


def _write_inputs(tmp: Path) -> dict[str, Path]:
    annotations = {
        "annotations": [_annotation_row(index) for index in range(20)],
    }
    oracle = [
        {
            "question_id": "c{:02d}".format(index),
            "question_type": "knowledge-update",
            "question": "Question {}?".format(index),
            "answer": "Gold {}".format(index),
            "answer_session_ids": ["s{:02d}".format(index)],
            "haystack_session_ids": ["s{:02d}".format(index)],
        }
        for index in range(20)
    ]
    smoke = {
        "policy_smoke": {
            "policy_names": ["no_memory_lite"],
            "policies": [
                {
                    "policy_name": "no_memory_lite",
                    "per_scenario": [],
                }
            ],
        }
    }
    paths = {
        "annotations": tmp / "annotations_agreed.json",
        "oracle": tmp / "longmemeval_oracle.json",
        "smoke": tmp / "smoke_summary.json",
    }
    paths["annotations"].write_text(json.dumps(annotations), encoding="utf-8")
    paths["oracle"].write_text(json.dumps(oracle), encoding="utf-8")
    paths["smoke"].write_text(json.dumps(smoke), encoding="utf-8")
    return paths


def _annotation_row(index: int) -> dict:
    case_id = "c{:02d}".format(index)
    return {
        "case_id": case_id,
        "question_type": "knowledge-update",
        "question": "Question {}?".format(index),
        "in_denominator": True,
        "mechanism_code": "contradiction_edge",
        "relevant_canonical_id": "slot-{}".format(index),
        "scope_level": "user_global",
        "scope_key": "longmemeval:user",
        "claim_type": "world_fact",
        "contradiction_edges": [],
        "candidate_events": [
            {
                "event_id": "obs_0",
                "session_id": "s{:02d}".format(index),
                "raw_claim": "Claim {}".format(index),
                "canonical_id": "slot-{}".format(index),
                "claim_type": "world_fact",
                "scope_level": "user_global",
                "scope_key": "longmemeval:user",
                "confidence": 0.7,
                "contradicts_event_ids": [],
            }
        ],
    }


def _keys_containing_answer(value) -> set[str]:
    keys = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if "answer" in key:
                keys.add(key)
            keys |= _keys_containing_answer(nested)
    elif isinstance(value, list):
        for item in value:
            keys |= _keys_containing_answer(item)
    return keys


if __name__ == "__main__":
    unittest.main()
