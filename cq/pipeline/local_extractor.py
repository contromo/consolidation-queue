from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from cq.eval.component_eval import CandidateComponentPrediction
from cq.eval.runner import (
    FORCED_CONTRADICTION,
    TEMPLATE_MIXES_BY_FAMILY,
    generate_scenarios,
)
from cq.schemas.memory import jsonable
from cq.schemas.scenario import EventKind, Scenario


WEAK_MODE = "weak"
POSITIVE_CONTROL_MODE = "positive_control"
EXTRACTOR_MODES = (WEAK_MODE, POSITIVE_CONTROL_MODE)


@dataclass(frozen=True)
class TranscriptEventInput:
    event_id: str
    event_kind: str
    turn_index: int
    text: str


@dataclass(frozen=True)
class TranscriptScenarioInput:
    scenario_id: str
    events: List[TranscriptEventInput]


_COMPANY = r"[A-Z][A-Za-z]+"
# Positive-control patterns mirror the forced-contradiction observation
# templates in cq/simulator/scenario_generator.py; update both when template
# wording changes.
_FORCED_CONTRADICTION_PATTERNS: Sequence[Tuple[str, re.Pattern[str]]] = (
    ("positive", re.compile(r"^(?P<buyer>{c}) acquired (?P<target>{c})\.$".format(c=_COMPANY))),
    (
        "positive",
        re.compile(
            r"^(?P<buyer>{c}) completed the acquisition of (?P<target>{c})\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "positive",
        re.compile(r"^(?P<target>{c}) was acquired by (?P<buyer>{c})\.$".format(c=_COMPANY)),
    ),
    (
        "positive",
        re.compile(
            r"^(?P<buyer>{c}) later confirmed the acquisition of (?P<target>{c})\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "positive",
        re.compile(
            r"^A follow-up report repeats that (?P<buyer>{c}) completed the acquisition of (?P<target>{c})\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "negative",
        re.compile(
            r"^A trusted filing says (?P<buyer>{c})'s acquisition talks with (?P<target>{c}) collapsed\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "negative",
        re.compile(
            r"^A regulator filing says (?P<buyer>{c}) did not acquire (?P<target>{c}); the talks ended\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "negative",
        re.compile(
            r"^Later reporting says the (?P<buyer>{c})-(?P<target>{c}) acquisition did not happen\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "negative",
        re.compile(
            r"^A credible but not definitive filing suggests (?P<buyer>{c})'s acquisition of (?P<target>{c}) may have fallen through\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "negative",
        re.compile(
            r"^A follow-up report indicates (?P<buyer>{c}) likely did not complete the acquisition of (?P<target>{c})\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "negative",
        re.compile(
            r"^Later reporting casts substantial doubt on whether (?P<buyer>{c}) acquired (?P<target>{c})\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "negative",
        re.compile(
            r"^A later clarification confirms (?P<buyer>{c}) did not complete the acquisition of (?P<target>{c})\.$".format(
                c=_COMPANY
            )
        ),
    ),
)


def sanitize_scenario_for_extraction(scenario: Scenario) -> TranscriptScenarioInput:
    return TranscriptScenarioInput(
        scenario_id=scenario.scenario_id,
        events=[
            TranscriptEventInput(
                event_id=event.event_id,
                event_kind=event.kind.value,
                turn_index=event.turn_index,
                text=event.text,
            )
            for event in scenario.sorted_events()
        ],
    )


def extract_predictions_for_scenario(
    transcript_scenario: TranscriptScenarioInput,
    mode: str,
) -> List[CandidateComponentPrediction]:
    if not isinstance(transcript_scenario, TranscriptScenarioInput):
        raise TypeError("Extractor input must be TranscriptScenarioInput")
    if mode == WEAK_MODE:
        return []
    if mode == POSITIVE_CONTROL_MODE:
        return _positive_control_forced_contradiction(transcript_scenario)
    raise ValueError("Unsupported extractor mode: {}".format(mode))


def extract_predictions_by_scenario(
    transcript_scenarios: Sequence[TranscriptScenarioInput],
    mode: str,
) -> Dict[str, List[CandidateComponentPrediction]]:
    return {
        transcript_scenario.scenario_id: extract_predictions_for_scenario(
            transcript_scenario,
            mode,
        )
        for transcript_scenario in transcript_scenarios
    }


def build_extractor_output(
    *,
    family: str,
    scenario_count: int,
    template_mix: str,
    mode: str,
) -> Dict[str, object]:
    scenarios = generate_scenarios(family, scenario_count, template_mix)
    transcript_scenarios = [sanitize_scenario_for_extraction(scenario) for scenario in scenarios]
    if mode == POSITIVE_CONTROL_MODE and family != FORCED_CONTRADICTION:
        raise ValueError("positive_control mode is only defined for forced_contradiction")
    return {
        "mode": mode,
        "family": family,
        "template_mix": template_mix,
        "requested_scenario_count": scenario_count,
        "scenario_count": len(transcript_scenarios),
        "input_contract": "transcript_only",
        "scenario_predictions": jsonable(
            extract_predictions_by_scenario(transcript_scenarios, mode)
        ),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write transcript-only component predictions for local extractor smoke tests."
    )
    parser.add_argument("--family", default=FORCED_CONTRADICTION, choices=sorted(TEMPLATE_MIXES_BY_FAMILY))
    parser.add_argument("--scenarios", type=int, default=25)
    parser.add_argument("--template-mix", default="mixed")
    parser.add_argument("--mode", choices=EXTRACTOR_MODES, default=WEAK_MODE)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)

    try:
        output = build_extractor_output(
            family=args.family,
            scenario_count=args.scenarios,
            template_mix=args.template_mix,
            mode=args.mode,
        )
    except ValueError as error:
        parser.error(str(error))

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("Wrote {}".format(output_path))
    return 0


def _positive_control_forced_contradiction(
    transcript_scenario: TranscriptScenarioInput,
) -> List[CandidateComponentPrediction]:
    predictions: List[CandidateComponentPrediction] = []
    positive_events_by_canonical: Dict[str, List[str]] = {}
    for event in sorted(transcript_scenario.events, key=lambda item: item.turn_index):
        if event.event_kind != EventKind.OBSERVATION.value:
            continue
        parsed = _parse_forced_contradiction_observation(event.text)
        if parsed is None:
            continue
        polarity, buyer, target = parsed
        canonical_id = _forced_contradiction_canonical_id(buyer, target)
        contradicts_event_ids = []
        if polarity == "negative":
            contradicts_event_ids = list(positive_events_by_canonical.get(canonical_id, []))
        prediction = CandidateComponentPrediction(
            event_id=event.event_id,
            candidate_id="",
            canonical_id=canonical_id,
            claim_type="world_fact",
            scope_level="world_global",
            scope_key="global",
            contradicts_event_ids=contradicts_event_ids,
            raw_claim=event.text,
            confidence=1.0,
        )
        predictions.append(prediction)
        if polarity == "positive":
            positive_events_by_canonical.setdefault(canonical_id, []).append(event.event_id)
    return predictions


def _parse_forced_contradiction_observation(
    text: str,
) -> Optional[Tuple[str, str, str]]:
    for polarity, pattern in _FORCED_CONTRADICTION_PATTERNS:
        match = pattern.match(text)
        if match:
            return polarity, match.group("buyer"), match.group("target")
    return None


def _forced_contradiction_canonical_id(buyer: str, target: str) -> str:
    return "world-fact-{}-{}-acquisition-status".format(
        buyer.lower(),
        target.lower(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
