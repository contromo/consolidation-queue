"""Local cross-judge stability check for LongMemEval QA scoring.

Implements preregistration §6 path 2: when no published reference judge logs
exist, calibrate the primary local judge (``qwen2.5:32b-instruct-q4_K_M``) for
LongMemEval QA scoring by checking its verdict agreement against a second
locked local model (``qwen2.5:7b-instruct-q4_K_M``) on a stratified held-out
set.

Preregistration §6 path ordering (this module is path 2):

1. **Published reference judge logs** (preferred, no API): if any subset of
   LongMemEval reference-judge logs exist as committed artifacts, use them as
   the calibration target. This module's ``stability_report`` accepts a
   ``reference_verdicts`` map for that path.
2. **Local cross-judge** (this module's default): run both 32B and 7B locally
   over (question, gold_answer, candidate_answer) triples and compare verdicts.
   Supports only a "stability" claim, NOT a reference-comparable calibration
   claim.
3. **API judge calibration**: explicitly forbidden here. Requires user
   authorization recorded in the preregistration; no API calls happen in this
   module.

Kill criterion 10 (preregistration §8): realistic-stratum agreement below
``0.85`` or failed synthetic controls escalates to the user before any policy
run. The support floor remains 20 paired/reference cases.

Scaffolding-only by default. The module exposes a callable that runs the
ollama HTTP API, but the CLI defaults to writing a ``--dry-run`` plan; a full
calibration run requires explicit ``--run`` and meaningful wall-clock time on
the 32B model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from string import Template
from urllib.parse import urlparse
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence, Union


DEFAULT_PRIMARY_JUDGE = "qwen2.5:32b-instruct-q4_K_M"
DEFAULT_SECONDARY_JUDGE = "qwen2.5:7b-instruct-q4_K_M"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
JUDGE_AGREEMENT_FLOOR = 0.85
CALIBRATION_SET_SIZE = 20
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

CORRECT_VERDICT = "correct"
INCORRECT_VERDICT = "incorrect"
INDETERMINATE_VERDICT = "indeterminate"


JUDGE_PROMPT_TEMPLATE = Template("""You are scoring a question-answering response.

Question:
$question

Reference answer:
$gold_answer

Candidate answer:
$candidate_answer

Decide whether the candidate answer is correct relative to the reference answer
for this question. Ignore stylistic differences; focus on whether the candidate
conveys the same factual content as the reference. Reply with the single word
"correct" or "incorrect" on the first line, with no additional text.""")


@dataclass(frozen=True)
class CalibrationCase:
    case_id: str
    question: str
    gold_answer: str
    candidate_answer: str
    stratum: str = "realistic"
    expected_verdict: Optional[str] = None
    source_case_id: Optional[str] = None
    source_policy: Optional[str] = None


@dataclass(frozen=True)
class JudgeVerdict:
    case_id: str
    model_id: str
    verdict: str
    raw_response: str


class JudgeStabilityError(RuntimeError):
    pass


def render_judge_prompt(case: CalibrationCase) -> str:
    return JUDGE_PROMPT_TEMPLATE.substitute(
        question=case.question.strip(),
        gold_answer=case.gold_answer.strip(),
        candidate_answer=case.candidate_answer.strip(),
    )


def parse_verdict(raw_response: str) -> str:
    if raw_response is None:
        return INDETERMINATE_VERDICT
    first_line = raw_response.strip().splitlines()[0].lower() if raw_response.strip() else ""
    cleaned = re.sub(r"[^a-z]", "", first_line)
    if cleaned.startswith("correct"):
        return CORRECT_VERDICT
    if cleaned.startswith("incorrect"):
        return INCORRECT_VERDICT
    return INDETERMINATE_VERDICT


def load_calibration_set(path: Union[str, Path]) -> list[CalibrationCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise JudgeStabilityError("Calibration payload missing 'cases' list in {}".format(path))
    cases = []
    for row in rows:
        if not isinstance(row, dict):
            raise JudgeStabilityError("Calibration rows must be objects")
        cases.append(
            CalibrationCase(
                case_id=str(row.get("case_id") or ""),
                question=str(row.get("question") or ""),
                gold_answer=str(row.get("gold_answer") or ""),
                candidate_answer=str(row.get("candidate_answer") or ""),
                stratum=str(row.get("stratum") or "realistic"),
                expected_verdict=_optional_verdict(row.get("expected_verdict")),
                source_case_id=_optional_text(row.get("source_case_id")),
                source_policy=_optional_text(row.get("source_policy")),
            )
        )
    return cases


def stability_report(
    verdicts_primary: Sequence[JudgeVerdict],
    verdicts_secondary: Sequence[JudgeVerdict],
    *,
    primary_model_id: str,
    secondary_model_id: str,
    minimum_agreement: float = JUDGE_AGREEMENT_FLOOR,
    minimum_case_count: int = CALIBRATION_SET_SIZE,
    reference_verdicts: Optional[Mapping[str, str]] = None,
    calibration_cases: Optional[Sequence[CalibrationCase]] = None,
) -> dict[str, object]:
    primary_by_case = {v.case_id: v for v in verdicts_primary}
    secondary_by_case = {v.case_id: v for v in verdicts_secondary}
    calibration_by_case = {
        case.case_id: case for case in (calibration_cases or [])
    }
    overlap = sorted(set(primary_by_case) & set(secondary_by_case))
    paired_rows = []
    cross_judge_matches = 0
    indeterminate_count = 0
    reference_matches = 0
    reference_present = 0
    for case_id in overlap:
        primary = primary_by_case[case_id]
        secondary = secondary_by_case[case_id]
        calibration_case = calibration_by_case.get(case_id)
        cross_match = primary.verdict == secondary.verdict
        cross_judge_matches += int(cross_match)
        if INDETERMINATE_VERDICT in (primary.verdict, secondary.verdict):
            indeterminate_count += 1
        reference_verdict = (reference_verdicts or {}).get(case_id)
        if reference_verdict is not None:
            reference_present += 1
            reference_matches += int(primary.verdict == reference_verdict)
        paired_rows.append(
            {
                "case_id": case_id,
                "primary_verdict": primary.verdict,
                "secondary_verdict": secondary.verdict,
                "cross_judge_match": cross_match,
                "reference_verdict": reference_verdict,
                "stratum": calibration_case.stratum if calibration_case else None,
                "expected_verdict": (
                    calibration_case.expected_verdict if calibration_case else None
                ),
                "source_case_id": (
                    calibration_case.source_case_id if calibration_case else None
                ),
            }
        )
    paired_total = len(paired_rows)
    cross_judge_agreement = cross_judge_matches / paired_total if paired_total else 0.0
    stratum_metrics = _stratum_metrics(paired_rows)
    synthetic_floor = _synthetic_correctness_floor(stratum_metrics)
    reference_agreement = (
        reference_matches / reference_present if reference_present else None
    )
    primary_label = (
        "reference_calibration"
        if reference_verdicts is not None
        else "judge_stability_local_cross_check"
    )
    if reference_verdicts is not None:
        primary_agreement = reference_agreement
    else:
        realistic_metrics = stratum_metrics.get("realistic", {})
        primary_agreement = realistic_metrics.get(
            "cross_judge_agreement",
            cross_judge_agreement,
        )
    support_count = (
        reference_present
        if reference_verdicts is not None
        else paired_total
    )
    support_count_check_passed = support_count >= minimum_case_count
    agreement_threshold_met = (
        support_count_check_passed and primary_agreement >= minimum_agreement
        if primary_agreement is not None
        else False
    )
    threshold_met = agreement_threshold_met and synthetic_floor["passed"]
    return {
        "primary_model_id": primary_model_id,
        "secondary_model_id": secondary_model_id,
        "minimum_agreement": minimum_agreement,
        "minimum_case_count": minimum_case_count,
        "calibration_path": primary_label,
        "paired_total": paired_total,
        "support_count": support_count,
        "support_count_check_passed": support_count_check_passed,
        "indeterminate_count": indeterminate_count,
        "cross_judge_matches": cross_judge_matches,
        "cross_judge_agreement": cross_judge_agreement,
        "reference_verdicts_present": reference_present,
        "reference_matches": reference_matches,
        "reference_agreement": reference_agreement,
        "primary_agreement": primary_agreement,
        "agreement_threshold_met": agreement_threshold_met,
        "stratum_metrics": stratum_metrics,
        "synthetic_correctness_floor": synthetic_floor,
        "kill_criterion_10_triggered": not threshold_met,
        "paired_rows": paired_rows,
    }


def _optional_text(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_verdict(value: object) -> Optional[str]:
    if value is None or value == "":
        return None
    text = str(value)
    if text not in {CORRECT_VERDICT, INCORRECT_VERDICT}:
        raise JudgeStabilityError(
            "expected_verdict must be '{}' or '{}', got {!r}".format(
                CORRECT_VERDICT,
                INCORRECT_VERDICT,
                value,
            )
        )
    return text


def _stratum_metrics(paired_rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for row in paired_rows:
        stratum = str(row.get("stratum") or "unlabeled")
        grouped.setdefault(stratum, []).append(row)
    metrics = {}
    for stratum, rows in sorted(grouped.items()):
        expected_rows = [row for row in rows if row.get("expected_verdict")]
        cross_matches = sum(1 for row in rows if row.get("cross_judge_match"))
        primary_expected_matches = sum(
            1
            for row in expected_rows
            if row.get("primary_verdict") == row.get("expected_verdict")
        )
        secondary_expected_matches = sum(
            1
            for row in expected_rows
            if row.get("secondary_verdict") == row.get("expected_verdict")
        )
        metrics[stratum] = {
            "support_count": len(rows),
            "cross_judge_matches": cross_matches,
            "cross_judge_agreement": cross_matches / len(rows) if rows else 0.0,
            "expected_verdict_count": len(expected_rows),
            "primary_expected_matches": primary_expected_matches,
            "primary_expected_accuracy": (
                primary_expected_matches / len(expected_rows)
                if expected_rows
                else None
            ),
            "secondary_expected_matches": secondary_expected_matches,
            "secondary_expected_accuracy": (
                secondary_expected_matches / len(expected_rows)
                if expected_rows
                else None
            ),
        }
    return metrics


def _synthetic_correctness_floor(
    stratum_metrics: Mapping[str, object],
) -> dict[str, object]:
    checked_strata = ("control_positive", "control_negative")
    floors = {}
    failures = []
    any_expected = False
    for stratum in checked_strata:
        metrics = stratum_metrics.get(stratum)
        if not isinstance(metrics, Mapping):
            floors[stratum] = {
                "applicable": False,
                "passed": True,
                "primary_expected_matches": 0,
                "secondary_expected_matches": 0,
                "expected_verdict_count": 0,
            }
            continue
        expected_count = int(metrics.get("expected_verdict_count") or 0)
        primary_matches = int(metrics.get("primary_expected_matches") or 0)
        secondary_matches = int(metrics.get("secondary_expected_matches") or 0)
        any_expected = any_expected or expected_count > 0
        primary_passed = expected_count == 0 or primary_matches >= max(0, expected_count - 1)
        secondary_passed = expected_count == 0 or secondary_matches >= max(0, expected_count - 1)
        passed = primary_passed and secondary_passed
        floors[stratum] = {
            "applicable": expected_count > 0,
            "passed": passed,
            "primary_passed": primary_passed,
            "secondary_passed": secondary_passed,
            "primary_expected_matches": primary_matches,
            "secondary_expected_matches": secondary_matches,
            "expected_verdict_count": expected_count,
            "maximum_errors_per_judge": 1 if expected_count else 0,
        }
        if not passed:
            failures.append(stratum)
    return {
        "applicable": any_expected,
        "passed": not failures,
        "failed_strata": failures,
        "strata": floors,
    }


def run_judge(
    cases: Iterable[CalibrationCase],
    *,
    model_id: str,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    request_timeout_seconds: float = 600.0,
    temperature: float = 0.0,
) -> list[JudgeVerdict]:
    """Send each calibration case through the ollama judge model.

    Network call — only runs when the CLI is invoked with ``--run``.
    """

    _validate_loopback_base_url(base_url)
    verdicts = []
    for case in cases:
        prompt = render_judge_prompt(case)
        response = _ollama_generate(
            base_url=base_url,
            model_id=model_id,
            prompt=prompt,
            decoding_params={"temperature": temperature, "num_predict": 16},
            request_timeout_seconds=request_timeout_seconds,
        )
        verdicts.append(
            JudgeVerdict(
                case_id=case.case_id,
                model_id=model_id,
                verdict=parse_verdict(response),
                raw_response=response,
            )
        )
    return verdicts


def _ollama_generate(
    *,
    base_url: str,
    model_id: str,
    prompt: str,
    decoding_params: Mapping[str, object],
    request_timeout_seconds: float,
) -> str:
    url = "{}/api/generate".format(base_url.rstrip("/"))
    payload = {
        "model": model_id,
        "prompt": prompt,
        "stream": False,
        "options": dict(decoding_params),
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=request_timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise JudgeStabilityError(
            "Ollama request failed ({}) with status {} {}: {}".format(
                url,
                exc.code,
                exc.reason,
                _http_error_body_snippet(exc),
            )
        ) from exc
    except urllib.error.URLError as exc:
        raise JudgeStabilityError(
            "Ollama request failed ({}): {}".format(url, exc)
        ) from exc
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise JudgeStabilityError("Ollama response was not JSON: {}".format(exc)) from exc
    if isinstance(parsed, dict) and isinstance(parsed.get("error"), str):
        raise JudgeStabilityError(
            "Ollama response contained error: {}".format(parsed["error"])
        )
    text = parsed.get("response") if isinstance(parsed, dict) else None
    if not isinstance(text, str):
        raise JudgeStabilityError("Ollama response missing 'response' string")
    return text


def _http_error_body_snippet(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:
        body = ""
    if not body:
        return "<empty response body>"
    return body[:500]


def _validate_loopback_base_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise JudgeStabilityError("Ollama base URL must be an HTTP(S) URL")
    if parsed.hostname not in LOOPBACK_HOSTS:
        raise JudgeStabilityError(
            "Ollama base URL must use a loopback host unless the "
            "preregistration records an external judge exception"
        )


def write_json(path: Union[str, Path], payload: Mapping[str, object]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def verdict_artifact_row(verdict: JudgeVerdict) -> dict[str, object]:
    raw_bytes = verdict.raw_response.encode("utf-8")
    return {
        "case_id": verdict.case_id,
        "verdict": verdict.verdict,
        "raw_response_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "raw_response_bytes": len(raw_bytes),
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run LongMemEval local cross-judge stability check.",
    )
    parser.add_argument(
        "--calibration-json",
        required=True,
        help="Calibration set JSON with 'cases' list of {case_id, question, gold_answer, candidate_answer}.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Stability report output path.",
    )
    parser.add_argument(
        "--primary-model",
        default=DEFAULT_PRIMARY_JUDGE,
        help="Primary judge model id (default qwen2.5:32b-instruct-q4_K_M).",
    )
    parser.add_argument(
        "--secondary-model",
        default=DEFAULT_SECONDARY_JUDGE,
        help="Secondary judge model id (default qwen2.5:7b-instruct-q4_K_M).",
    )
    parser.add_argument(
        "--reference-verdicts-json",
        help=(
            "Optional JSON map of case_id -> 'correct'/'incorrect' from a "
            "published reference judge (preferred calibration path)."
        ),
    )
    parser.add_argument(
        "--minimum-agreement",
        type=float,
        default=JUDGE_AGREEMENT_FLOOR,
        help="Kill criterion 10 floor (default 0.85).",
    )
    parser.add_argument(
        "--minimum-case-count",
        type=int,
        default=CALIBRATION_SET_SIZE,
        help="Minimum paired/reference cases required before the agreement floor can pass.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Actually invoke ollama judges. Without this flag, writes a dry-run plan.",
    )
    args = parser.parse_args(argv)

    cases = load_calibration_set(args.calibration_json)
    if len(cases) < CALIBRATION_SET_SIZE:
        print(
            "WARNING: calibration set has {} cases (minimum support floor is {}).".format(
                len(cases),
                CALIBRATION_SET_SIZE,
            )
        )
    if not args.run:
        plan = {
            "mode": "dry_run",
            "calibration_case_count": len(cases),
            "primary_model": args.primary_model,
            "secondary_model": args.secondary_model,
            "minimum_agreement": args.minimum_agreement,
            "minimum_case_count": args.minimum_case_count,
            "ollama_base_url": args.base_url,
            "reference_verdicts_provided": bool(args.reference_verdicts_json),
            "note": (
                "Dry-run only. Pass --run to invoke ollama; expect minutes "
                "per case on the 32B model."
            ),
        }
        write_json(args.output_json, plan)
        return 0

    reference_verdicts = None
    if args.reference_verdicts_json:
        reference_verdicts = json.loads(
            Path(args.reference_verdicts_json).read_text(encoding="utf-8")
        )
        if not isinstance(reference_verdicts, dict):
            raise JudgeStabilityError("Reference verdicts must be a JSON object")

    verdicts_primary = run_judge(cases, model_id=args.primary_model, base_url=args.base_url)
    verdicts_secondary = run_judge(cases, model_id=args.secondary_model, base_url=args.base_url)
    report = stability_report(
        verdicts_primary,
        verdicts_secondary,
        primary_model_id=args.primary_model,
        secondary_model_id=args.secondary_model,
        minimum_agreement=args.minimum_agreement,
        minimum_case_count=args.minimum_case_count,
        reference_verdicts=reference_verdicts,
        calibration_cases=cases,
    )
    report["primary_verdicts"] = [
        verdict_artifact_row(verdict) for verdict in verdicts_primary
    ]
    report["secondary_verdicts"] = [
        verdict_artifact_row(verdict) for verdict in verdicts_secondary
    ]
    write_json(args.output_json, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
