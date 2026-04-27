# CQ-Agent-lite

This policy uses the same substrate as the eager baseline, but introduces a pending layer.

For each candidate, it may:

- keep the candidate pending
- use pending memory at answer time with caution
- promote after sufficient evidence or strong contradiction resolution
- contest older candidates when newer evidence arrives
- demote active durable memory if a stronger contradiction wins

The first slice is tuned for oracle forced-contradiction scenarios and is intentionally conservative about early durable promotion for world facts.
