# ReflectionEagerWrite-lite

This baseline uses the shared substrate and performs a single immediate commit decision for each candidate.

For each candidate, it may:

- promote immediately if there is no active durable memory in scope
- reinforce an existing durable memory if the claim supports it
- demote and overwrite an existing durable memory if a stronger contradiction arrives
- ignore or contest a weaker contradictory candidate

It does not support:

- pending use without durable promotion
- delayed consolidation windows
- offline promotion passes
- explicit demotion queues
