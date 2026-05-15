from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List


def render_dashboard(run_data: Dict[str, object]) -> str:
    parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'><title>Consolidation Queue Dashboard</title>",
        "<style>",
        "body{font-family:Menlo,Consolas,monospace;margin:24px;background:#f7f4ec;color:#1f1b16;}",
        "h1,h2,h3{margin-bottom:8px;}",
        ".card{background:white;border:1px solid #d6cfbf;border-radius:10px;padding:16px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,0.04);}",
        "table{border-collapse:collapse;width:100%;margin-top:8px;}",
        "th,td{border:1px solid #ddd4c4;padding:8px;text-align:left;vertical-align:top;}",
        "th{background:#efe7d6;}",
        "code{background:#f1ebdf;padding:1px 4px;border-radius:4px;}",
        "details{margin:12px 0;}",
        ".summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;}",
        ".metric{background:#fbf8f1;border:1px solid #ddd4c4;border-radius:8px;padding:12px;}",
        ".timeline-turn{border:1px solid #ddd4c4;border-radius:8px;padding:12px;margin:12px 0;background:#fcfaf5;}",
        ".timeline-turn h4{margin:0 0 8px 0;}",
        ".timeline-meta{margin:6px 0 0 0;color:#5d5345;}",
        ".badge{display:inline-block;padding:2px 6px;border-radius:999px;background:#e7dcc6;margin-right:6px;}",
        ".failure-floor td{background:#f4f1ea;color:#5d5345;}",
        "</style></head><body>",
        "<h1>Consolidation Queue Dashboard</h1>",
        "<div class='card'><strong>Experiment:</strong> {}<br><strong>Scenarios:</strong> {}</div>".format(
            html.escape(str(run_data["experiment"])),
            html.escape(str(run_data["scenario_count"])),
        ),
    ]
    if "template_mix" in run_data:
        parts.append(
            "<div class='card'><strong>Template mix:</strong> {}</div>".format(
                html.escape(str(run_data["template_mix"]))
            )
        )

    for policy in run_data["policies"]:
        summary = policy["summary"]
        parts.append("<div class='card'>")
        parts.append("<h2>{}</h2>".format(html.escape(summary["policy_name"])))
        parts.append("<h3>Overall</h3>")
        parts.append(_render_summary_metrics(summary))
        if policy.get("summary_by_template_kind"):
            parts.append("<h3>By Template Kind</h3>")
            for template_kind, kind_summary in policy["summary_by_template_kind"].items():
                parts.append("<p><strong>{}</strong></p>".format(html.escape(template_kind)))
                parts.append(_render_summary_metrics(kind_summary))
        if policy.get("summary_by_template_split"):
            parts.append("<h3>By Template Split</h3>")
            for template_split, split_summary in policy["summary_by_template_split"].items():
                parts.append("<p><strong>{}</strong></p>".format(html.escape(template_split)))
                parts.append(_render_summary_metrics(split_summary))
        if policy.get("summary_by_template_id"):
            parts.append("<h3>By Template ID</h3>")
            for template_id, template_summary in policy["summary_by_template_id"].items():
                parts.append("<p><strong>{}</strong></p>".format(html.escape(template_id)))
                parts.append(_render_summary_metrics(template_summary))
        parts.append("<h3>Failure Examples</h3>")
        parts.append(_render_failure_examples(policy.get("failure_examples", []), summary["policy_name"], True))

        for scenario in policy["scenarios"]:
            parts.append(
                "<details class='card' id='scenario-{}-{}'><summary>{}</summary>".format(
                    html.escape(summary["policy_name"]),
                    html.escape(scenario["scenario_id"]),
                    html.escape(scenario["scenario_id"]),
                )
            )
            parts.append(
                "<p><strong>Template:</strong> {}<br><strong>Kind:</strong> {}<br><strong>Split:</strong> {}<br><strong>Description:</strong> {}</p>".format(
                    html.escape(str(scenario["scenario"].get("template_id", ""))),
                    html.escape(str(scenario["scenario"].get("template_kind", ""))),
                    html.escape(str(scenario["scenario"].get("template_split", ""))),
                    html.escape(str(scenario["scenario"].get("description", ""))),
                )
            )
            parts.append("<h3>Failure Examples</h3>")
            parts.append(_render_failure_examples(scenario.get("failure_examples", []), summary["policy_name"], False))
            parts.append("<h3>Transcript</h3><pre>{}</pre>".format(html.escape("\n".join(scenario["transcript"]))))
            parts.append("<h3>Timeline</h3>")
            parts.append(_render_timeline(summary["policy_name"], scenario))
            parts.append("<h3>Question Traces</h3>")
            parts.append(_render_table(scenario["question_traces"]))
            parts.append("<h3>Candidate Memories</h3>")
            parts.append(_render_table(scenario["store_snapshot"]["candidate_memories"]))
            parts.append("<h3>Durable Memories</h3>")
            parts.append(_render_table(scenario["store_snapshot"]["durable_memories"]))
            parts.append("<h3>Lifecycle Events</h3>")
            parts.append(_render_table(scenario["store_snapshot"]["lifecycle_events"]))
            parts.append("</details>")
        parts.append("</div>")

    parts.append("</body></html>")
    return "".join(parts)


def _render_summary_metrics(summary: Dict[str, object]) -> str:
    parts = ["<div class='summary'>"]
    preferred = (
        ("Useful recall", "useful_recall_before_contradiction"),
        ("Pending use", "used_pending_before_contradiction"),
        ("Early durable commit", "durable_commit_before_contradiction"),
        ("False assertion", "false_assertion_after_contradiction"),
        ("Recovery", "contradiction_recovery_rate"),
        ("Correctness", "answer_correctness_after_contradiction"),
        ("Avg time to demotion", "average_time_to_demotion"),
        ("Answer correctness", "answer_correctness"),
        ("False assertion rate", "false_assertion_rate"),
        ("Leakage rate", "leakage_rate"),
        ("Premature promotion rate", "premature_promotion_rate"),
        ("Poison promotion rate", "poison_promotion_rate"),
        ("Clean durable displacement rate", "clean_durable_displacement_rate"),
        ("Useful recall", "useful_recall"),
        ("Pending use", "used_pending"),
        ("Durable commit", "durable_commit"),
    )
    rendered = set()
    for label, key in preferred:
        if key not in summary:
            continue
        rendered.add(key)
        parts.append(
            "<div class='metric'><strong>{}</strong><br>{:.2f}</div>".format(
                html.escape(label),
                float(summary[key]),
            )
        )
    for key in sorted(summary.keys()):
        if key in rendered or key in {"policy_name", "scenario_count"}:
            continue
        value = summary[key]
        if isinstance(value, (int, float)):
            parts.append(
                "<div class='metric'><strong>{}</strong><br>{:.2f}</div>".format(
                    html.escape(key.replace("_", " ").title()),
                    float(value),
                )
            )
    parts.append("</div>")
    return "".join(parts)


def _render_failure_examples(examples: List[Dict[str, object]], policy_name: str, include_link: bool) -> str:
    if not examples:
        return "<p><em>No failure examples</em></p>"
    parts = [
        "<table><thead><tr>",
        "<th>Failure</th><th>Subtype</th><th>Reason</th><th>Scenario</th>",
        "<th>Template</th><th>Split</th><th>Phase</th><th>Answer</th><th>Involved Claims</th>",
    ]
    if include_link:
        parts.append("<th>Link</th>")
    parts.append("</tr></thead><tbody>")
    for example in examples:
        row_class = " class='failure-floor'" if example.get("failure_subtype") == "no_memory_floor" else ""
        parts.append("<tr{}>".format(row_class))
        parts.append("<td><pre>{}</pre></td>".format(html.escape(str(example.get("failure_type", "")))))
        parts.append("<td><pre>{}</pre></td>".format(html.escape(str(example.get("failure_subtype", "")))))
        parts.append("<td><pre>{}</pre></td>".format(html.escape(str(example.get("reason", "")))))
        parts.append("<td><pre>{}</pre></td>".format(html.escape(str(example.get("scenario_id", "")))))
        parts.append("<td><pre>{}</pre></td>".format(html.escape(str(example.get("template_id", "")))))
        parts.append("<td><pre>{}</pre></td>".format(html.escape(str(example.get("template_split", "")))))
        parts.append("<td><pre>{}</pre></td>".format(html.escape(str(example.get("question_phase", "")))))
        parts.append("<td><pre>{}</pre></td>".format(html.escape(str(example.get("answer_text", "")))))
        parts.append("<td><pre>{}</pre></td>".format(html.escape(_render_failure_claims(example))))
        if include_link:
            anchor = "scenario-{}-{}".format(policy_name, example.get("scenario_id", ""))
            parts.append(
                "<td><a href='#{}'>context</a></td>".format(
                    html.escape(anchor, quote=True)
                )
            )
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _render_failure_claims(example: Dict[str, object]) -> str:
    claims = {
        "candidates": example.get("candidate_claims", {}),
        "durables": example.get("durable_claims", {}),
    }
    if not claims["candidates"] and not claims["durables"]:
        return "none"
    return json.dumps(claims, indent=2, sort_keys=True)


def _render_table(rows: List[Dict[str, object]]) -> str:
    if not rows:
        return "<p><em>No rows</em></p>"
    columns = []
    for row in rows:
        for key in row.keys():
            if key not in columns:
                columns.append(key)
    parts = ["<table><thead><tr>"]
    for column in columns:
        parts.append("<th>{}</th>".format(html.escape(column)))
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for column in columns:
            value = row.get(column, "")
            if isinstance(value, (list, dict)):
                rendered = json.dumps(value, indent=2)
            else:
                rendered = str(value)
            parts.append("<td><pre>{}</pre></td>".format(html.escape(rendered)))
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _render_timeline(policy_name: str, scenario: Dict[str, object]) -> str:
    turns = _build_timeline_turns(scenario)
    parts = ["<div class='timeline'>"]
    for turn in turns:
        parts.append(
            "<div class='timeline-turn' id='scenario-{}-{}-turn-{}'>".format(
                html.escape(policy_name),
                html.escape(scenario["scenario_id"]),
                html.escape(str(turn["turn_index"])),
            )
        )
        parts.append(
            "<h4>T{} {}</h4>".format(
                html.escape(str(turn["turn_index"])),
                html.escape(str(turn["kind"]).replace("_", " ")),
            )
        )
        parts.append(
            "<p><strong>{}</strong></p><p class='timeline-meta'>{}</p>".format(
                html.escape(str(turn["text"])),
                html.escape(str(turn["timestamp"])),
            )
        )
        if turn["rows"]:
            parts.append("<table><thead><tr><th>Timestamp</th><th>Event</th><th>Object</th><th>Text</th><th>Markers</th></tr></thead><tbody>")
            for row in turn["rows"]:
                parts.append("<tr>")
                parts.append("<td><pre>{}</pre></td>".format(html.escape(str(row["timestamp"]))))
                parts.append("<td><pre>{}</pre></td>".format(html.escape(str(row["event_type"]))))
                parts.append("<td><pre>{}</pre></td>".format(html.escape(str(row["object_id"]))))
                parts.append("<td><pre>{}</pre></td>".format(html.escape(str(row["text"]))))
                parts.append("<td>{}</td>".format(_render_badges(row["markers"])))
                parts.append("</tr>")
            parts.append("</tbody></table>")
        else:
            parts.append("<p><em>No grouped events</em></p>")
        parts.append("</div>")
    parts.append("</div>")
    return "".join(parts)


def _render_badges(markers: List[str]) -> str:
    if not markers:
        return "<em>none</em>"
    return "".join("<span class='badge'>{}</span>".format(html.escape(marker)) for marker in markers)


def _build_timeline_turns(scenario: Dict[str, object]) -> List[Dict[str, object]]:
    oracle_events = sorted(
        scenario["scenario"]["oracle_events"],
        key=lambda event: event["turn_index"],
    )
    lifecycle_events = sorted(
        scenario["store_snapshot"]["lifecycle_events"],
        key=lambda event: _parse_timestamp(event["timestamp"]),
    )
    question_traces = {trace["question_id"]: trace for trace in scenario["question_traces"]}
    lifecycle_index = 0
    turns = []

    for index, oracle_event in enumerate(oracle_events):
        start_timestamp = _oracle_event_timestamp(oracle_event)
        end_timestamp = None
        if index + 1 < len(oracle_events):
            end_timestamp = _oracle_event_timestamp(oracle_events[index + 1])

        rows = []
        while lifecycle_index < len(lifecycle_events):
            lifecycle_event = lifecycle_events[lifecycle_index]
            lifecycle_timestamp = _parse_timestamp(lifecycle_event["timestamp"])
            if lifecycle_timestamp < start_timestamp:
                lifecycle_index += 1
                continue
            if end_timestamp is not None and lifecycle_timestamp >= end_timestamp:
                break
            lifecycle_index += 1
            if lifecycle_event["event_type"] == "answer_generated":
                continue
            rows.append(_timeline_row_from_lifecycle(lifecycle_event))

        if oracle_event["kind"] == "question" and oracle_event.get("question"):
            question = oracle_event["question"]
            trace = question_traces.get(question["question_id"])
            if trace is not None:
                rows.append(_timeline_row_from_answer(trace))

        turns.append(
            {
                "turn_index": oracle_event["turn_index"],
                "kind": oracle_event["kind"],
                "text": oracle_event["text"],
                "timestamp": start_timestamp.isoformat(),
                "rows": rows,
            }
        )

    return turns


def _timeline_row_from_lifecycle(event: Dict[str, object]) -> Dict[str, object]:
    details = event.get("details", {})
    markers = []
    if event["event_type"] == "candidate_observed":
        state = details.get("state")
        if state:
            markers.append(state)
    if event["event_type"] == "observation_ignored":
        markers.append("ignored")
    if event["event_type"] == "candidate_state_changed":
        new_state = details.get("new_state")
        if new_state:
            markers.append(str(new_state))
    if event["event_type"] == "candidate_corroboration_counted":
        markers.append("corroboration")
    if event["event_type"] == "contradiction_registered":
        markers.append("contradiction")
    if event["event_type"] == "memory_promoted":
        markers.append("durable")
    if event["event_type"] == "memory_reinforced":
        markers.extend(["reinforced", "durable"])
    if event["event_type"] == "memory_demoted":
        markers.append("demoted")

    text = _timeline_event_text(event)
    return {
        "timestamp": event["timestamp"],
        "event_type": event["event_type"],
        "object_id": event["object_id"],
        "text": text,
        "markers": markers,
    }


def _timeline_event_text(event: Dict[str, object]) -> str:
    details = event.get("details", {})
    if event["event_type"] == "candidate_corroboration_counted":
        counted = ", ".join(str(source_id) for source_id in details.get("counted_source_ids", []))
        duplicate = ", ".join(str(source_id) for source_id in details.get("duplicate_source_ids", []))
        capped = ", ".join(str(source_id) for source_id in details.get("capped_source_ids", []))
        ignored = ", ".join(str(source_id) for source_id in details.get("ignored_source_ids", []))
        return (
            "counted_source_ids=[{}] duplicate_source_ids=[{}] "
            "capped_source_ids=[{}] ignored_source_ids=[{}]"
        ).format(counted, duplicate, capped, ignored)
    return (
        details.get("claim")
        or details.get("reason")
        or details.get("source_candidate_id")
        or ""
    )


def _timeline_row_from_answer(trace: Dict[str, object]) -> Dict[str, object]:
    markers = []
    if trace.get("used_pending"):
        markers.append("pending")
    elif trace.get("used_memory_ids"):
        markers.append("durable")
    return {
        "timestamp": trace["created_at"],
        "event_type": "answer",
        "object_id": trace["answer_id"],
        "text": trace["answer_text"],
        "markers": markers,
    }


def _oracle_event_timestamp(event: Dict[str, object]) -> datetime:
    if event["kind"] == "observation" and event.get("candidate") is not None:
        return _parse_timestamp(event["candidate"]["created_at"])
    if event["kind"] == "question" and event.get("question") is not None:
        return _parse_timestamp(event["question"]["asked_at"])
    raise ValueError("Oracle event is missing timestamp data: {}".format(event["event_id"]))


def _parse_timestamp(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).replace(tzinfo=None)


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Serve or render the local CQ dashboard.")
    parser.add_argument("run_json", help="Path to a run artifact JSON file.")
    parser.add_argument("--port", type=int, default=8000, help="Local port for the dashboard.")
    parser.add_argument("--write-html", help="Write static HTML instead of serving.")
    args = parser.parse_args(argv)

    run_path = Path(args.run_json)
    run_data = json.loads(run_path.read_text(encoding="utf-8"))
    html_text = render_dashboard(run_data)

    if args.write_html:
        output_path = Path(args.write_html)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_text, encoding="utf-8")
        print("Wrote {}".format(output_path))
        return 0

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_text.encode("utf-8"))

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    print("Serving http://127.0.0.1:{}".format(args.port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
