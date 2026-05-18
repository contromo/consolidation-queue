from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Union


FORBIDDEN_KEYS = {
    "answer",
    "answers",
    "gold_answer",
    "reference_answer",
    "answer_session_ids",
}


def binomial_upper_tail(successes: int, trials: int, probability: float) -> float:
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("successes must be between 0 and trials")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be between 0 and 1")
    return sum(
        math.comb(trials, k) * (probability**k) * ((1.0 - probability) ** (trials - k))
        for k in range(successes, trials + 1)
    )


def forbidden_answer_key_paths(payload: Any, *, prefix: str = "") -> list[str]:
    paths = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = "{}.{}".format(prefix, key) if prefix else str(key)
            if key in FORBIDDEN_KEYS:
                paths.append(path)
            paths.extend(forbidden_answer_key_paths(value, prefix=path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            path = "{}[{}]".format(prefix, index) if prefix else "[{}]".format(index)
            paths.extend(forbidden_answer_key_paths(value, prefix=path))
    return paths


def build_verifier_report(
    annotations: Iterable[Mapping[str, Any]],
    *,
    audit_summary: Optional[Mapping[str, Any]] = None,
    chance_agreement: float = 0.5,
    alpha: float = 0.05,
    min_agreement_rate: float = 0.75,
) -> dict[str, Any]:
    annotation_rows = list(annotations)
    forbidden_paths = forbidden_answer_key_paths(annotation_rows)
    if audit_summary:
        trials = int(audit_summary.get("comparable_in_denominator_count") or 0)
        successes = int(audit_summary.get("agreement_count") or 0)
    else:
        trials = len(annotation_rows)
        successes = len(annotation_rows)
    agreement_rate = successes / trials if trials else 0.0
    p_value = binomial_upper_tail(successes, trials, chance_agreement) if trials else 1.0
    return {
        "annotation_count": len(annotation_rows),
        "agreement_count": successes,
        "comparable_in_denominator_count": trials,
        "agreement_rate": agreement_rate,
        "chance_agreement": chance_agreement,
        "binomial_upper_tail_p_value": p_value,
        "alpha": alpha,
        "min_agreement_rate": min_agreement_rate,
        "forbidden_answer_key_paths": forbidden_paths,
        "hidden_answer_check_passed": not forbidden_paths,
        "agreement_rate_check_passed": agreement_rate >= min_agreement_rate if trials else False,
        "binomial_check_passed": p_value <= alpha if trials else False,
        "verifier_passed": (
            not forbidden_paths
            and bool(trials)
            and agreement_rate >= min_agreement_rate
            and p_value <= alpha
        ),
    }


def load_annotations(path: Union[str, Path]) -> list[Mapping[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("annotations", "cases", "records", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise ValueError("No annotation list in {}".format(path))


def load_audit_summary(path: Optional[Union[str, Path]]) -> Optional[Mapping[str, Any]]:
    if path is None:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("summary"), dict):
        raise ValueError("No summary object in {}".format(path))
    return payload["summary"]


def write_json(path: Union[str, Path], payload: Mapping[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify LongMemEval external annotations.")
    parser.add_argument("--annotations-json", required=True, help="Agreed annotation JSON.")
    parser.add_argument("--output-json", required=True, help="Verifier report output JSON.")
    parser.add_argument("--audit-report-json", help="Optional dual-path audit report JSON.")
    parser.add_argument("--chance-agreement", type=float, default=0.5)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--min-agreement-rate", type=float, default=0.75)
    args = parser.parse_args(argv)
    report = build_verifier_report(
        load_annotations(args.annotations_json),
        audit_summary=load_audit_summary(args.audit_report_json),
        chance_agreement=args.chance_agreement,
        alpha=args.alpha,
        min_agreement_rate=args.min_agreement_rate,
    )
    write_json(args.output_json, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
