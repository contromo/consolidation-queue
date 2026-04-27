from __future__ import annotations

from typing import List

from cq.schemas.scenario import EventKind, Scenario


def render_scenario_transcript(scenario: Scenario) -> List[str]:
    lines = []
    for event in scenario.sorted_events():
        if event.kind == EventKind.OBSERVATION:
            lines.append("T{} OBSERVE: {}".format(event.turn_index, event.text))
        else:
            lines.append("T{} ASK: {}".format(event.turn_index, event.text))
    return lines
