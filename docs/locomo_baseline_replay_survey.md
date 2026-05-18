# LoCoMo Published-Output PFLC Survey

Date: 2026-05-18

Status: executed as the post-A.6 LoCoMo artifact gate plus one empirical
published-output PFLC scoring pass.

## Decision

The corrected plan's Phase 0 gate does not end at extended B-3 anymore once
the current Agent Memory Benchmark (AMB) public outputs are included. AMB
publishes per-question LoCoMo run artifacts whose injected context contains
recoverable LoCoMo `dia_id` values. That is enough for a
published-output/context-derived PFLC replay.

The promoted artifact class is narrow:

- it is a public-output diagnostic over AMB LoCoMo runs
- it is not a CQ policy comparison
- it does not preserve CQ's same-candidate-stream invariant
- it scores whether the public run's emitted context exposes LoCoMo gold
  evidence IDs, not whether the memory system uses an internal durable-memory
  ID compatible with CQ

## Phase 0 Artifact Gate

Gate criteria used:

1. Publicly downloadable per-question outputs.
2. Question IDs align with LoCoMo `sample_id` and QA index.
3. Output contains system-emitted retrieved context or identifiers.
4. Retrieved context exposes original LoCoMo `dia_id` values or an equivalent
   session/document ID that can be mapped to them.
5. Gold evidence comes from the official LoCoMo `qa[].evidence` field.
6. Coverage is explicit: full 1,540-question LoCoMo10 or marked partial.
7. Artifact class is labeled `published-output`, `published-output/context-
   derived`, `replay-generated`, or `absent`.

| Candidate | Coverage | Released per-question output | System-side evidence handle | Gate result |
| --- | ---: | --- | --- | --- |
| Mem0 `memory-benchmarks` platform LoCoMo | 1,540 | Yes, committed result JSONs | No. Rows contain question, answer, cutoff judgments, latency, and retrieval count, but no `retrieval.search_results`, memory IDs, or LoCoMo `evidence` IDs. Code can generate them on rerun. | Fail: `absent`; replay-generated possible |
| A-MEM / AgenticMemory | 0 committed result rows | No committed LoCoMo result files found | Evaluation code saves predictions and metrics, not raw context or retrieved IDs. | Fail: `absent`; replay-generated possible |
| Official SNAP LoCoMo RAG | 0 committed prediction rows | No released prediction artifact | Code can save context IDs when rerun; full-context baseline is PFLC-degenerate. | Fail: `absent`; replay-generated possible |
| Backboard LoCoMo benchmark | 1,540 | Yes, answer/judge rows | Saved rows omit `retrieved_memories`; code captures them but does not persist them. | Fail: `absent`; replay-generated possible |
| MemoryLake LoCoMo benchmark | 1,540 | Yes, answer/judge rows | No retrieval, evidence, context, or `dia_id` fields. | Fail: `absent` |
| Engram | No committed output rows | Reproducible code only | Benchmark code can emit per-question retrieval/session recall if run locally, but repo does not commit the run output. | Fail: `replay-generated` only |
| Hindsight benchmark repo aggregates | Aggregate leaderboard rows | Yes, aggregate only | No per-question context in the committed leaderboard JSONs. | Fail by itself |
| AMB Hindsight LoCoMo output | 1,540 | Yes, public gzip via AMB API | Injected context contains source snippets with original `dia_id` values. | Pass: `published-output/context-derived` |
| AMB hybrid-search LoCoMo output | 1,540 | Yes, public gzip via AMB API | Injected context contains source snippets with original `dia_id` values. | Pass: `published-output/context-derived` |
| AMB Cognee LoCoMo output | 152 | Yes, public gzip via AMB API | Injected context contains source snippets with original `dia_id` values. | Partial pass: `published-output/context-derived` |
| External AMB comparison rows for Mem0, Zep, Letta, LangMem, MemoryBank | Aggregate only | No raw output artifact surfaced through AMB | Scores only; no per-question emitted context. | Fail: `absent` |

## Empirical PFLC Replay

Implemented:

- scorer: `scripts/score_locomo_amb_pflc.py`
- per-question rows: `data/results/locomo_amb_pflc_rows.csv`
- summary/manifest: `data/results/locomo_amb_pflc_summary.json`

Scoring rule:

- parse each AMB run's per-question `context`
- split context into `## Memory N` blocks
- extract every emitted LoCoMo `dia_id`
- compare those IDs to the official LoCoMo `qa[].evidence` IDs
- report `any_hit@k` and `all_hit@k` for memory-block cutoffs
  `k = 1, 5, 10, 20, 50, 200`

Headline results:

| Run | Rows | Answer accuracy | All-evidence PFLC@10 | All-evidence PFLC@20 | All-evidence PFLC@50 | Any-evidence PFLC@50 | Avg context tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AMB `locomo-hindsight` | 1,540 | 92.0% | 65.6% | 82.9% | 97.3% | 99.0% | 36,235 |
| AMB `hybrid-search` | 1,540 | 79.1% | 64.7% | 75.5% | 90.3% | 96.2% | 22,156 |
| AMB `cognee` | 152 | 80.3% | 59.2% | 72.4% | 90.8% | 96.1% | 14,724 |

Joint counts at all-evidence PFLC@50:

| Run | Correct + PFLC hit | Correct + PFLC miss | Wrong + PFLC hit | Wrong + PFLC miss |
| --- | ---: | ---: | ---: | ---: |
| AMB `locomo-hindsight` | 1,383 | 34 | 116 | 7 |
| AMB `hybrid-search` | 1,114 | 104 | 276 | 46 |
| AMB `cognee` | 109 | 13 | 29 | 1 |

## Interpretation

This is stronger than the earlier B-3 artifact-blocked posture, but not in the
way the original plan hoped. The public AMB context makes empirical PFLC
scoring possible, and the first result is not a lookup-contract collapse:
Hindsight reaches all-evidence PFLC@50 of 97.3 percent.

The result still matters because it separates three phenomena that aggregate
LoCoMo answer accuracy conflates:

- evidence exposure: whether the generated context contains the gold dialog IDs
- evidence rank and context budget: whether those IDs appear early or only
  after tens of memory blocks and tens of thousands of tokens
- answer generation/judging: whether the answer is correct once the evidence is
  present

For example, `hybrid-search` has 276 wrong answers where all gold evidence is
already present by PFLC@50. That is not a retrieval contract failure; it is an
answering, reasoning, prompt, or judging failure under a large injected context.
Conversely, it has 104 correct answers where all gold evidence is missing by
PFLC@50, which flags answer success not fully backed by the LoCoMo evidence
contract as scored here.

The most reviewer-useful claim is therefore not "public memory systems fail
PFLC." It is:

> Once per-question context is published, PFLC decomposes LoCoMo scores into
> evidence exposure, evidence rank/context saturation, and answer-generation
> residuals. Without those artifacts, the same decomposition is impossible.

## Source Lock

Local source snapshots used during the survey:

- `mem0ai/memory-benchmarks`: `4b61c5d31b9c668a12b4f5e78064248a02c82d2b`
- `WujiangXu/AgenticMemory`: `0c8039f28fdcc08189a23c07a3437d9d2482f9c2`
- `snap-research/locomo`: `3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376`
- `Backboard-io/Backboard-Locomo-Benchmark`: `164d45c06f860d832bbe598f0dde0ea66b05f384`
- `memorylake-ai/memorylake-locomo-benchmark`: `4ede2a6a37eebc6897c585a7a7bb1cffa287b8b6`
- `Nitin-Gupta1109/engram`: `68e8ade65fc5631d4eda34b0ac40fffa17fd53d8`
- `vectorize-io/hindsight-benchmarks`: `cd11de89b0b517b5229467a58b7e86c981a9c62c`

Primary input hashes:

- official LoCoMo `locomo10.json`: `79fa87e90f04081343b8c8debecb80a9a6842b76a7aa537dc9fdf651ea698ff4`
- AMB Hindsight run gzip: `2c70253b80555de105d19ceaca6cea3fd10a0ddee030623991f597bc8007dc1c`
- AMB hybrid-search run gzip: `2b26fbec092e59dddc979b9e8ae92c5e09a6af3591d24e7264c5014fb632d4db`
- AMB Cognee run gzip: `e71811ef87b28cc7b267576dc1f5453cd6e9b8d577d5d221e50ea0aaf588c111`

Committed artifact hashes:

- `scripts/score_locomo_amb_pflc.py`: `92106277b79ebd864e67bafd16ecb1d93aeb2bfcec08b70384ae610c9836530b`
- `data/results/locomo_amb_pflc_rows.csv`: `16ee6eaf006ea2a11e7148b9aeeb27cea75ce56eada23794e48784fba0ae1ea6`
- `data/results/locomo_amb_pflc_summary.json`: `065db2439b6741f66a71e1b2a03813badcd5cc609baa76cba91038055852ca85`

Public URLs:

- AMB run index: <https://agentmemorybenchmark.ai/api/results>
- AMB catalog: <https://agentmemorybenchmark.ai/api/catalog>
- AMB Hindsight run resolver: <https://agentmemorybenchmark.ai/api/run-url?file=outputs%2Flocomo%2Flocomo-hindsight%2Frag%2Flocomo10.json.gz>
- AMB hybrid-search run resolver: <https://agentmemorybenchmark.ai/api/run-url?file=outputs%2Flocomo%2Fhybrid-search%2Frag%2Flocomo10.json.gz>
- AMB Cognee run resolver: <https://agentmemorybenchmark.ai/api/run-url?file=outputs%2Flocomo%2Fcognee%2Frag%2Flocomo10.json.gz>

## Non-Claims

- This does not update any CQ, ReflectionEagerWrite, or `Mem0Lite` policy
  verdict.
- This does not compare memory policies under a shared upstream candidate
  stream.
- This does not prove AMB/Hindsight's internal memory representation is
  policy-facing in the CQ sense; it only proves the published per-question
  context exposes recoverable LoCoMo evidence IDs.
- This does not rescue Mem0, A-MEM, MemoryBank, Zep, Letta, or LangMem from
  artifact-blocked status; their public rows inspected here still lack
  per-question emitted evidence handles.
- PFLC@50 should not be read as evidence of compact retrieval. The full
  Hindsight run averages 36,235 context tokens and hundreds of emitted dialog
  IDs per question, so the stricter PFLC@10 and PFLC@20 cutoffs carry the
  rank-sensitivity signal.
