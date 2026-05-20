"""Build the stratified LongMemEval judge calibration set.

This is a scoring-side helper for Phase X.3.5. It may read gold answers through
``gold_loader`` because the output is consumed only by judge calibration; it
must not be imported by policy, adapter, verifier, or annotation code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from cq.eval.end_to_end_eval import execute_scenario
from cq.eval.external.longmemeval.adapter import (
    DEFAULT_ANNOTATIONS_PATH,
    adapt_annotation,
    load_agreed_annotations,
)
from cq.eval.external.longmemeval.gold_loader import load_gold_cases
from cq.eval.runner import POLICY_SET_PHASE_2_5, _policies_for_family
from cq.schemas.memory import jsonable
from cq.schemas.scenario import TaskFamily


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT / "data" / "external" / "longmemeval" / "judge_calibration_set.json"
)
DEFAULT_MANIFEST_PATH = (
    REPO_ROOT
    / "data"
    / "external"
    / "longmemeval"
    / "judge_calibration_set_manifest.json"
)
DEFAULT_REALISTIC_COUNT = 15
DEFAULT_CONTROL_CASE_COUNT = 5
DEFAULT_SOURCE_POLICY = "consolidation_queue_lite"
DEFAULT_NEGATIVE_SENTINEL = "I do not know."
DEFAULT_SEED = 1729


class JudgeCalibrationSetError(ValueError):
    pass


def build_calibration_set(
    *,
    agreed_annotations_path: str | Path = DEFAULT_ANNOTATIONS_PATH,
    oracle_json_path: str | Path,
    smoke_summary_path: str | Path,
    source_policy: str = DEFAULT_SOURCE_POLICY,
    seed: int = DEFAULT_SEED,
    realistic_count: int = DEFAULT_REALISTIC_COUNT,
    control_case_count: int = DEFAULT_CONTROL_CASE_COUNT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    annotations = load_agreed_annotations(agreed_annotations_path)
    annotations_by_case_id = {
        str(row["case_id"]): row for row in sorted(annotations, key=lambda item: str(item["case_id"]))
    }
    case_ids = sorted(annotations_by_case_id)
    needed = realistic_count + control_case_count
    if len(case_ids) < needed:
        raise JudgeCalibrationSetError(
            "Need at least {} agreed cases, found {}".format(needed, len(case_ids))
        )
    realistic_case_ids = case_ids[:realistic_count]
    control_case_ids = case_ids[realistic_count:needed]

    smoke_summary = _load_json_object(smoke_summary_path)
    _validate_source_policy_in_smoke(smoke_summary, source_policy)
    policy_answers = _policy_answers_by_case_id(
        [annotations_by_case_id[case_id] for case_id in realistic_case_ids],
        source_policy=source_policy,
    )
    gold_by_case = {
        case.case_id: case
        for case in load_gold_cases(oracle_json_path)
        if case.case_id in set(realistic_case_ids + control_case_ids)
    }
    missing_gold = sorted(set(realistic_case_ids + control_case_ids) - set(gold_by_case))
    if missing_gold:
        raise JudgeCalibrationSetError(
            "Gold oracle is missing selected case ids: {}".format(", ".join(missing_gold))
        )

    cases = []
    for case_id in realistic_case_ids:
        gold = gold_by_case[case_id]
        cases.append(
            {
                "case_id": case_id,
                "source_case_id": case_id,
                "question": gold.question,
                "gold_answer": gold.answer,
                "candidate_answer": policy_answers[case_id],
                "stratum": "realistic",
                "expected_verdict": None,
                "source_policy": source_policy,
            }
        )
    for case_id in control_case_ids:
        gold = gold_by_case[case_id]
        cases.append(
            {
                "case_id": "{}::control_positive".format(case_id),
                "source_case_id": case_id,
                "question": gold.question,
                "gold_answer": gold.answer,
                "candidate_answer": gold.answer,
                "stratum": "control_positive",
                "expected_verdict": "correct",
                "source_policy": "synthetic_gold_identity",
            }
        )
        cases.append(
            {
                "case_id": "{}::control_negative".format(case_id),
                "source_case_id": case_id,
                "question": gold.question,
                "gold_answer": gold.answer,
                "candidate_answer": DEFAULT_NEGATIVE_SENTINEL,
                "stratum": "control_negative",
                "expected_verdict": "incorrect",
                "source_policy": "synthetic_negative_sentinel",
            }
        )

    payload = {
        "mode": "longmemeval_judge_calibration_set",
        "selection_strategy": "sorted_agreed_case_ids",
        "seed": seed,
        "source_policy": source_policy,
        "realistic_case_count": realistic_count,
        "control_case_count": control_case_count,
        "case_count": len(cases),
        "stratum_counts": _stratum_counts(cases),
        "cases": cases,
    }
    manifest = {
        "artifact": "longmemeval_judge_calibration_set",
        "artifact_class": "phase_x3_5_judge_calibration_set",
        "selection_strategy": payload["selection_strategy"],
        "seed": seed,
        "source_policy": source_policy,
        "realistic_case_ids": realistic_case_ids,
        "control_case_ids": control_case_ids,
        "case_count": len(cases),
        "stratum_counts": payload["stratum_counts"],
        "inputs": {
            "agreed_annotations_path": _repo_relative(Path(agreed_annotations_path)),
            "agreed_annotations_sha256": sha256_file(agreed_annotations_path),
            "oracle_json_path": str(oracle_json_path),
            "oracle_json_sha256": sha256_file(oracle_json_path),
            "smoke_summary_path": _repo_relative(Path(smoke_summary_path)),
            "smoke_summary_sha256": sha256_file(smoke_summary_path),
        },
        "gold_access": "gold_loader_only",
        "realistic_candidate_answer_source": (
            "dedicated_policy_execution"
            if not _smoke_has_answer_text(smoke_summary, source_policy, realistic_case_ids)
            else "smoke_summary_answer_text"
        ),
    }
    return payload, manifest


def write_calibration_artifacts(
    *,
    output_json: str | Path,
    manifest_json: str | Path,
    payload: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    output_path = Path(output_json)
    manifest_path = Path(manifest_json)
    _write_json(output_path, payload)
    manifest_with_output = dict(manifest)
    manifest_with_output["outputs"] = {
        "calibration_set_path": _repo_relative(output_path),
        "calibration_set_sha256": sha256_file(output_path),
        "calibration_set_bytes": output_path.stat().st_size,
    }
    _write_json(manifest_path, manifest_with_output)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _policy_answers_by_case_id(
    annotation_rows: Sequence[Mapping[str, Any]],
    *,
    source_policy: str,
) -> dict[str, str]:
    policy_cls = _policy_class_by_name(source_policy)
    answers = {}
    for row in annotation_rows:
        scenario, _stream = adapt_annotation(row)
        record = execute_scenario(policy_cls, scenario)
        traces = list(record.get("question_traces") or [])
        trace = traces[0] if traces else {}
        answer_text = str(trace.get("answer_text") if isinstance(trace, Mapping) else "")
        case_id = str(row["case_id"])
        if not answer_text:
            raise JudgeCalibrationSetError(
                "Policy {} produced no answer_text for case {}".format(
                    source_policy,
                    case_id,
                )
            )
        answers[case_id] = answer_text
    return answers


def _policy_class_by_name(source_policy: str):
    policies = _policies_for_family(
        TaskFamily.LONGMEMEVAL_EXTERNAL.value,
        policy_set=POLICY_SET_PHASE_2_5,
    )
    for policy_cls in policies:
        if policy_cls.policy_name == source_policy:
            return policy_cls
    raise JudgeCalibrationSetError(
        "Unknown source policy {!r}. Available: {}".format(
            source_policy,
            ", ".join(policy.policy_name for policy in policies),
        )
    )


def _validate_source_policy_in_smoke(
    smoke_summary: Mapping[str, Any],
    source_policy: str,
) -> None:
    policy_smoke = smoke_summary.get("policy_smoke")
    if not isinstance(policy_smoke, Mapping):
        raise JudgeCalibrationSetError("Smoke summary is missing policy_smoke")
    policy_names = policy_smoke.get("policy_names")
    if not isinstance(policy_names, list) or source_policy not in policy_names:
        raise JudgeCalibrationSetError(
            "Smoke summary does not include source policy {!r}".format(source_policy)
        )


def _smoke_has_answer_text(
    smoke_summary: Mapping[str, Any],
    source_policy: str,
    case_ids: Sequence[str],
) -> bool:
    policy_smoke = smoke_summary.get("policy_smoke")
    policies = policy_smoke.get("policies") if isinstance(policy_smoke, Mapping) else []
    scenario_ids = {"longmemeval_{}".format(case_id) for case_id in case_ids}
    for policy in policies if isinstance(policies, list) else []:
        if not isinstance(policy, Mapping) or policy.get("policy_name") != source_policy:
            continue
        rows = policy.get("per_scenario")
        if not isinstance(rows, list):
            return False
        answer_rows = {
            row.get("scenario_id"): row
            for row in rows
            if isinstance(row, Mapping) and isinstance(row.get("answer_text"), str)
        }
        return all(scenario_id in answer_rows for scenario_id in scenario_ids)
    return False


def _stratum_counts(cases: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in cases:
        stratum = str(row.get("stratum") or "")
        counts[stratum] = counts.get(stratum, 0) + 1
    return dict(sorted(counts.items()))


def _load_json_object(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise JudgeCalibrationSetError("Expected JSON object in {}".format(path))
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(jsonable(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the stratified LongMemEval judge calibration set.",
    )
    parser.add_argument("--agreed-annotations", default=str(DEFAULT_ANNOTATIONS_PATH))
    parser.add_argument("--oracle-json", required=True)
    parser.add_argument("--smoke-summary", required=True)
    parser.add_argument("--source-policy", default=DEFAULT_SOURCE_POLICY)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--manifest-json", default=str(DEFAULT_MANIFEST_PATH))
    args = parser.parse_args(argv)

    payload, manifest = build_calibration_set(
        agreed_annotations_path=args.agreed_annotations,
        oracle_json_path=args.oracle_json,
        smoke_summary_path=args.smoke_summary,
        source_policy=args.source_policy,
        seed=args.seed,
    )
    write_calibration_artifacts(
        output_json=args.output_json,
        manifest_json=args.manifest_json,
        payload=payload,
        manifest=manifest,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
