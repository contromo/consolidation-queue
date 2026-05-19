# LongMemEval Reference Judge Log Survey

Date: 2026-05-19

## Decision

`path_1_logs_absent`

No official LongMemEval per-case reference judge verdict log was found that can
be mapped directly to the 71-case agreed CQ externalization denominator. Phase
X.3.5 therefore proceeds through preregistration §6 path 2: local cross-judge
stability with the stratified synthetic-control correctness floor.

## Sources Checked

| Source | URL | Finding |
| --- | --- | --- |
| Official LongMemEval repository | <https://github.com/xiaowu0162/LongMemEval> | Repository exposes code, setup instructions, retrieval/generation/evaluation scripts, and dataset download links. The root file list contains `assets`, `data/custom_history`, `src`, requirements, and README, but no committed judged-output directory such as `judged_*.json`, `eval_outputs/`, or `outputs/scores/`. |
| Official README dataset/evaluation instructions | <https://github.com/xiaowu0162/LongMemEval> | The README documents the released fields, including `answer`, `haystack_session_ids`, and `answer_session_ids`, and instructs users to run `src/evaluation/evaluate_qa.py`, which writes local `[hypothesis].log` files. It does not publish an official reference verdict file. |
| HuggingFace cleaned dataset | <https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/tree/main> | File listing contains `.gitattributes`, `README.md`, `longmemeval_m_cleaned.json`, `longmemeval_oracle.json`, and `longmemeval_s_cleaned.json`; no judged-output companion is listed. |
| arXiv page | <https://arxiv.org/abs/2410.10813> | Paper page links the public code/data release but does not expose supplementary judged-output artifacts through arXiv. |
| Web search for official and third-party judged logs | Queries for LongMemEval judged/eval-output/verdict artifacts | Search surfaced third-party benchmark result repositories and aggregate reports, but no official per-case reference judge log suitable for path-1 calibration. |
| Backboard LongMemEval results | <https://github.com/Backboard-io/Backboard-longmemEval-results> | Repository reports aggregate and cross-evaluator accuracy and describes generated `runs/` artifacts, but it is a third-party system result, not an official LongMemEval reference judge log. It is not used as path-1 calibration. |

## Notes

- This survey is intentionally artifact-gate oriented. Aggregate leaderboard
  rows, third-party per-system results, and scripts that can generate local
  judge logs do not satisfy path 1 unless they publish stable per-case verdicts
  that can be matched to the agreed case ids.
- The local path-2 calibration set is built separately in
  `data/external/longmemeval/judge_calibration_set.json` and records both
  realistic policy-answer rows and synthetic correctness controls.
