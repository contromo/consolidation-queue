# LongMemEval Externalization Anchor Gate

Date: 2026-05-18

Status: **locked Phase X.-1 gate**.

Decision: **LongMemEval v1 remains the primary controlled-pilot anchor.**
LongMemEval-V2 is verified as a real public release, but it is demoted to
secondary descriptive evidence-exposure work because the public release removes
the gold-side evidence labels needed for matched PFLC scoring.

No CQ, ReflectionEagerWrite, `Mem0Lite`, ablation, or retrieval policy was run
as part of this gate.

## Source Survey

Primary public sources checked:

- LongMemEval-V2 project page:
  <https://xiaowu0162.github.io/longmemeval-v2/>
- LongMemEval-V2 Hugging Face dataset:
  <https://huggingface.co/datasets/xiaowu0162/longmemeval-v2>
- LongMemEval-V2 official repository:
  <https://github.com/xiaowu0162/LongMemEval-V2>
- MemoryAgentBench official repository:
  <https://github.com/HUST-AI-HYZ/MemoryAgentBench>
- BEAM awareness source:
  <https://graphonomous.com/benchmarks/beam>

Downloaded metadata-only files on 2026-05-18, intentionally excluding the
multi-GB trajectory and screenshot archives:

| File | Local path inspected | Rows/lines | SHA256 |
| --- | --- | ---: | --- |
| V2 questions | `/private/tmp/lme_v2_questions.jsonl` | 451 JSONL rows | `0a3ae5ebea938c24d7800e1e0b0828e08ae1646f939a53853b2b8cdc08e292b7` |
| V2 schema | `/private/tmp/lme_v2_schema.md` | 43 lines | `0672cf47cf16c30365648770628b433076bb3f5b73edded673af7dd6d5f3246f` |
| V2 checksums | `/private/tmp/lme_v2_checksums.sha256` | 37 lines | `b17a18daa52873f915808502217c3c5fab39d20638544f986401155c9e8d67a6` |

The downloaded `checksums.sha256` file pins `questions.jsonl` at the same
`0a3ae5...92b7` hash and records `trajectories.jsonl` at
`363cec9a8e87aa8d9101ce4e600aadbf7031d674056ebe4f969e8424abc5f3c6`.

## V2 Verification

Confirmed:

- 451 public questions.
- Two domains: `enterprise` (`211`) and `web` (`240`).
- 29 questions include a question image path; 422 are text-only at the question
  surface.
- `SCHEMA.md` documents `questions.jsonl`, `trajectories.jsonl`, small/medium
  haystack files, question screenshots, and trajectory screenshots.
- The official repository defines the memory interface as `insert(trajectory)`
  plus `query(query, query_image=None)` returning text/image context items.
- The official dataset card says public files intentionally remove
  construction provenance, original task ids, answer-bearing annotation labels,
  URL-pattern labels, and annotation pipeline tags.

Question-type counts from `questions.jsonl`:

| V2 `question_type` | Count | Gate readout |
| --- | ---: | --- |
| `static-environment` | 134 | static recall, not CQ contradiction/update transfer |
| `static-environment-abs` | 55 | abstention/premise boundary, descriptive only |
| `dynamic-environment` | 86 | dynamic tracking; not lockable as contradiction without trajectory-level annotation |
| `dynamic-environment-abs` | 41 | abstention/premise boundary, descriptive only |
| `procedure` | 74 | workflow knowledge, not CQ contradiction/update transfer |
| `procedure-abs` | 32 | abstention/premise boundary, descriptive only |
| `errors-gotchas` | 29 | environment gotchas, not current CQ mechanism transfer |

## Anchor Gate Table

| Anchor | Native artifacts | Gold-side PFLC target | Mechanism-aligned denominator | Multimodality | Adapter burden | Decision |
| --- | --- | --- | ---: | --- | --- | --- |
| LongMemEval v1 oracle | evidence sessions plus `answer_session_ids`; existing 500-case feasibility coding | present for dialog-evidence-id PFLC, but cannot be used in policy input | 72 non-abstention `knowledge-update` cases from `docs/longmemeval_feasibility_memo.md` | text-only in current repo path | high: must construct shared `CandidateUpdate` stream, contradiction edges, canonical ids, scope map, and query contract | **primary controlled pilot** |
| LongMemEval-V2 | 451 questions, 1,870 trajectories, haystacks, screenshots, memory `insert/query` interface | **absent in public release**; answer-bearing annotation labels are stripped | not locked; question-type proxy has no explicit CQ `contradiction_edge` or `preference_correction` label | mixed: 29 question images and trajectory screenshots | higher than v1 for CQ transfer because it still lacks a write-time stream and adds image boundaries | secondary descriptive evidence-exposure only |
| MemoryAgentBench CR / FactConsolidation | public code and benchmark docs; CR named as an ability, FactConsolidation named as a constructed dataset | no newly verified per-question conflict-resolution-id output artifact | not promoted | text-oriented for this gate | unchanged from `docs/qr_canon_memoryagentbench_feasibility.md` | keep descriptive-only |
| BEAM | public benchmark pages describe source conversation ids and per-question scoring breakdowns | survey-only under existing PFLC registration | not evaluated here | text-conversation benchmark | outside this workstream unless separately amended | awareness only; no promotion |

## Predeclared Decision Rule Application

The Phase X.-1 rule says:

- if V2 verifies and gold evidence IDs are absent, V2 supports evidence-exposure
  diagnostics only, not gold PFLC;
- V1 stays primary;
- BEAM remains survey-only regardless.

That branch fires. V2 is real and useful for future methodology, but its public
release does not expose the matched gold-side lookup target needed to score the
same PFLC shape as LoCoMo `evidence` or LongMemEval v1 `answer_session_ids`.

## Locked Scope For The Next Phase

Proceed to `docs/fair_stream_externalization_preregistration.md` with:

- **primary anchor:** LongMemEval v1 oracle controlled pilot;
- **primary denominator before dual-path filtering:** 72 non-abstention
  `knowledge-update` cases already coded as `contradiction_edge`;
- **V2 role:** descriptive appendix/evidence-exposure case study only unless a
  future registered amendment obtains gold-side evidence IDs;
- **multimodality default:** text-only adapter; image-dependent rows are
  excluded or reported descriptively, not passed through a CQ-only field;
- **hard boundary:** no policy execution until the dual-path annotation layer,
  adapter pin, preregistration lock, hidden-answer verifier, and stream-hash
  invariant checks are implemented and passing.

