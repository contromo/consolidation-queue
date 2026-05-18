from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple, Union


AGREE = "agree"
DISAGREE_CANONICAL_ID = "disagree_canonical_id"
DISAGREE_CONTRADICTION_EDGES = "disagree_contradiction_edges"
DISAGREE_SCOPE = "disagree_scope"
MISSING_PATH_A = "missing_path_a"
MISSING_PATH_B = "missing_path_b"


def load_annotation_map(path: Union[str, Path]) -> dict[str, dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = None
        for key in ("annotations", "cases", "records", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = value
                break
        if rows is None:
            raise ValueError("No annotations/cases/records/data list in {}".format(path))
    else:
        raise ValueError("Unsupported annotation payload in {}".format(path))
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Annotation rows must be objects in {}".format(path))
        case_id = _case_id(row)
        if not case_id:
            raise ValueError("Annotation row is missing case_id/question_id/id in {}".format(path))
        if case_id in result:
            raise ValueError("Duplicate annotation case_id {!r} in {}".format(case_id, path))
        result[case_id] = row
    return result


def audit_annotation_maps(
    path_a: Mapping[str, Mapping[str, Any]],
    path_b: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = []
    agreed = []
    for case_id in sorted(set(path_a) | set(path_b)):
        a = path_a.get(case_id)
        b = path_b.get(case_id)
        row = _audit_row(case_id, a, b)
        rows.append(row)
        if row["status"] == AGREE and bool(row["in_denominator"]):
            agreed.append(_canonical_public_annotation(case_id, a))
    report = {
        "summary": _summary(rows),
        "rows": rows,
    }
    return report, agreed


def classify_pair(a: Mapping[str, Any], b: Mapping[str, Any]) -> tuple[str, list[str]]:
    disagreements = []
    if _canonical_id(a) != _canonical_id(b):
        disagreements.append("relevant_canonical_id")
    if _normalized_edges(a) != _normalized_edges(b):
        disagreements.append("contradiction_edges")
    if _scope(a) != _scope(b):
        disagreements.append("scope")
    if not disagreements:
        return AGREE, []
    if "relevant_canonical_id" in disagreements:
        return DISAGREE_CANONICAL_ID, disagreements
    if "contradiction_edges" in disagreements:
        return DISAGREE_CONTRADICTION_EDGES, disagreements
    return DISAGREE_SCOPE, disagreements


def write_json(path: Union[str, Path], payload: Mapping[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _audit_row(
    case_id: str,
    a: Optional[Mapping[str, Any]],
    b: Optional[Mapping[str, Any]],
) -> dict[str, Any]:
    if a is None:
        return {"case_id": case_id, "status": MISSING_PATH_A, "in_denominator": False}
    if b is None:
        return {"case_id": case_id, "status": MISSING_PATH_B, "in_denominator": False}
    status, fields = classify_pair(a, b)
    in_denominator = bool(a.get("in_denominator", True)) and bool(b.get("in_denominator", True))
    return {
        "case_id": case_id,
        "status": status,
        "in_denominator": in_denominator,
        "disagreement_fields": fields,
        "path_a_in_denominator": bool(a.get("in_denominator", True)),
        "path_b_in_denominator": bool(b.get("in_denominator", True)),
        "path_a_relevant_canonical_id": _canonical_id(a),
        "path_b_relevant_canonical_id": _canonical_id(b),
        "path_a_scope": list(_scope(a)),
        "path_b_scope": list(_scope(b)),
        "path_a_contradiction_edges": [list(edge) for edge in _normalized_edges(a)],
        "path_b_contradiction_edges": [list(edge) for edge in _normalized_edges(b)],
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    comparable = [
        row
        for row in rows
        if row["status"] not in {MISSING_PATH_A, MISSING_PATH_B} and row.get("in_denominator")
    ]
    agreement_count = sum(1 for row in comparable if row["status"] == AGREE)
    disagreement_count = len(comparable) - agreement_count
    status_counts = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    return {
        "case_count": len(rows),
        "comparable_in_denominator_count": len(comparable),
        "agreement_count": agreement_count,
        "disagreement_count": disagreement_count,
        "agreement_rate": agreement_count / len(comparable) if comparable else 0.0,
        "divergence_rate": disagreement_count / len(comparable) if comparable else 0.0,
        "status_counts": status_counts,
        "bucket_c_dual_path_divergence_triggered": (
            disagreement_count / len(comparable) > 0.25 if comparable else False
        ),
    }


def _canonical_public_annotation(case_id: str, row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "question_type": str(row.get("question_type") or ""),
        "question": str(row.get("question") or ""),
        "in_denominator": bool(row.get("in_denominator", True)),
        "mechanism_code": str(row.get("mechanism_code") or ""),
        "relevant_canonical_id": _canonical_id(row),
        "scope_level": _scope(row)[0],
        "scope_key": _scope(row)[1],
        "claim_type": str(row.get("claim_type") or ""),
        "contradiction_edges": [list(edge) for edge in _normalized_edges(row)],
        "candidate_events": _canonical_candidate_events(row),
    }


def _case_id(row: Mapping[str, Any]) -> str:
    return str(row.get("case_id") or row.get("question_id") or row.get("id") or "")


def _canonical_id(row: Mapping[str, Any]) -> str:
    return str(row.get("relevant_canonical_id") or row.get("canonical_id") or "")


def _scope(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("scope_level") or ""), str(row.get("scope_key") or ""))


def _normalized_edges(row: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    edges = row.get("contradiction_edges") or []
    normalized = []
    for edge in edges:
        pair = _edge_pair(edge)
        if pair is not None:
            normalized.append(tuple(sorted(pair)))
    return tuple(sorted(set(normalized)))


def _canonical_candidate_events(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    events = row.get("candidate_events") or []
    if not isinstance(events, list):
        return []
    cleaned = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        cleaned.append(
            {
                "event_id": str(event.get("event_id") or ""),
                "session_id": str(event.get("session_id") or ""),
                "session_index": event.get("session_index"),
                "session_date": str(event.get("session_date") or ""),
                "turn_index": event.get("turn_index"),
                "raw_claim": str(event.get("raw_claim") or ""),
                "canonical_id": str(event.get("canonical_id") or ""),
                "claim_type": str(event.get("claim_type") or ""),
                "scope_level": str(event.get("scope_level") or ""),
                "scope_key": str(event.get("scope_key") or ""),
                "confidence": event.get("confidence"),
                "contradicts_event_ids": [
                    str(event_id)
                    for event_id in event.get("contradicts_event_ids") or []
                ],
            }
        )
    return sorted(cleaned, key=_event_sort_key)


def _event_sort_key(event: Mapping[str, Any]) -> tuple[int, str]:
    index = event.get("session_index")
    sortable_index = index if isinstance(index, int) else 10**9
    return (sortable_index, str(event.get("event_id") or ""))


def _edge_pair(edge: Any) -> Optional[Tuple[str, str]]:
    if isinstance(edge, dict):
        left = edge.get("source_event_id") or edge.get("source") or edge.get("from")
        right = edge.get("target_event_id") or edge.get("target") or edge.get("to")
        if left and right:
            return (str(left), str(right))
    if isinstance(edge, (list, tuple)) and len(edge) == 2:
        return (str(edge[0]), str(edge[1]))
    return None


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Audit LongMemEval dual-path annotations.")
    parser.add_argument("--path-a", required=True, help="Path A annotation JSON.")
    parser.add_argument("--path-b", required=True, help="Path B annotation JSON.")
    parser.add_argument("--agreed-out", required=True, help="Output JSON for agreed annotations.")
    parser.add_argument("--divergence-out", required=True, help="Output JSON for divergence report.")
    args = parser.parse_args(argv)

    report, agreed = audit_annotation_maps(
        load_annotation_map(args.path_a),
        load_annotation_map(args.path_b),
    )
    write_json(args.divergence_out, report)
    write_json(args.agreed_out, {"annotations": agreed, "summary": report["summary"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
