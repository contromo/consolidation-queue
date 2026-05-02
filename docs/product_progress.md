# Product Progress

## 2026-05-02 — Held-out scope-contamination split added

### What shipped

- added `heldout` support for the scope-contamination oracle family
- added `scope_contamination_clean_v2`, a held-out clean project-scope recency probe
- added `scope_contamination_dirty_broad_claim_v3`, a held-out broad-first ordering probe with explicit contradiction provenance
- pinned the dirty held-out calibration inequalities that make Reflection, CQ, and Naive diverge for the intended reasons

### Why it matters

- clean_v2 checks that the scope-blind transcript baseline still leaks under a held-out surface form
- dirty_v3 checks whether a broad global convention can be prematurely promoted and then block a lower-strength project override
- this extends Phase 2 coverage without changing the shared substrate, policy interfaces, or metric definitions

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes with 53 tests
- held-out scope run (`python3 -m cq.eval.runner --family scope_contamination --scenarios 4 --template-mix heldout --output-json data/runs/scope_contamination_oracle_heldout.json --output-csv data/results/scope_contamination_oracle_heldout_metrics.csv`) shows:
  - `reflection_eager_write_lite`: `leakage=0.50`, `correctness=0.50`, `premature_promotion=0.50`
  - `consolidation_queue_lite`: `leakage=0.00`, `correctness=1.00`, `premature_promotion=0.00`
  - `naive_eager_write_lite`: `leakage=0.50`, `correctness=0.50`, `premature_promotion=0.50`
  - `no_memory_lite`: `leakage=0.00`, `correctness=0.00`, `premature_promotion=0.00`
  - `scope_blind_transcript_rag_lite`: `leakage=0.50`, `correctness=0.50`, `premature_promotion=0.00`
- per-template held-out result:
  - `scope_contamination_clean_v2`: Reflection/CQ/Naive are correct with no leakage; NoMemory has no recall; ScopeBlindTranscriptRAG leaks by recency
  - `scope_contamination_dirty_broad_claim_v3`: Reflection and Naive leak and prematurely promote; CQ answers from scoped pending memory; ScopeBlindTranscriptRAG answers correctly by recency

### Open issues / next

- this is still a broad-claim premature-promotion result, not evidence that CQ has better semantic scope inference
- preference drift and scenario-level failure example extraction remain next Phase 2 work
- a future non-broad-claim scope mechanism is still needed before making broader held-out scope claims

## 2026-05-02 — Broad-claim premature promotion scope slice added

### What shipped

- added the first scope-contamination oracle family as a broad-claim premature-promotion slice
- added `ScopeBlindTranscriptRAGLite`, an oracle-id recency baseline that intentionally ignores scope
- generalized the runner with `--family forced_contradiction|scope_contamination`
- added generic answer correctness, false assertion, leakage, and premature-promotion metrics while preserving contradiction aliases
- updated CSV/dashboard rendering so non-contradiction metrics are visible

### Why it matters

- this extends Phase 2 without changing the shared substrate or giving CQ richer memory than Reflection
- the dirty template isolates staged-vs-eager behavior: the same broad `WORLD_GLOBAL` contaminant is promoted by Reflection and left pending by CQ
- the clean template is deliberately narrow: it validates that the scope-blind transcript baseline leaks under oracle-id recency, not that CQ has special scope reasoning

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes with 44 tests
- mixed scope run (`python3 -m cq.eval.runner --family scope_contamination --scenarios 2 --template-mix mixed`) shows:
  - `reflection_eager_write_lite`: `leakage=0.50`, `correctness=0.50`, `premature_promotion=0.50`
  - `consolidation_queue_lite`: `leakage=0.00`, `correctness=1.00`, `premature_promotion=0.00`
  - `naive_eager_write_lite`: `leakage=0.00`, `correctness=1.00`, `premature_promotion=0.50`
  - `no_memory_lite`: `leakage=0.00`, `correctness=0.00`, `premature_promotion=0.00`
  - `scope_blind_transcript_rag_lite`: `leakage=1.00`, `correctness=0.00`, `premature_promotion=0.00`

### Open issues / next

- these results are in-distribution only and should not be cited as generalization evidence until held-out scope templates land
- the dirty result should be described as staged promotion resisting a broad contaminant, not as CQ doing better scope-aware reasoning
- preference drift and scenario-level failure example extraction remain next Phase 2 work

## 2026-05-01 — NoMemory floor baseline and correctness metric added

### What shipped

- added `NoMemoryLite` as the zero-history floor baseline on the oracle contradiction slice
- added `answer_correctness_after_contradiction` alongside the existing strict recovery metric
- updated the runner, CSV, and dashboard summaries to show correctness after recovery
- explicitly deferred `TranscriptRAGLite` until the first scope-contamination patch

### Why it matters

- the contradiction slice now separates “answered the post-contradiction question correctly” from “recovered by invalidating prior memory”
- `NoMemoryLite` makes the lower bound explicit without pretending current-session transcript use is “no memory”
- deferring `TranscriptRAGLite` keeps the current contradiction benchmark sharper instead of adding a transcript baseline that would mostly look good because the corrective turn is still adjacent

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` now passes with 34 tests
- mixed oracle run (`python3 -m cq.eval.runner --scenarios 6 --template-mix mixed`) shows:
  - `reflection_eager_write_lite`: `false_assertion=0.67`, `recovery=0.33`, `correctness=0.33`
  - `consolidation_queue_lite`: `false_assertion=0.00`, `recovery=1.00`, `correctness=1.00`
  - `naive_eager_write_lite`: `false_assertion=0.33`, `recovery=0.67`, `correctness=0.67`
  - `no_memory_lite`: `false_assertion=0.00`, `recovery=0.00`, `correctness=0.00`
- held-out oracle run (`python3 -m cq.eval.runner --scenarios 4 --template-mix heldout`) shows:
  - `no_memory_lite`: `false_assertion=0.00`, `recovery=0.00`, `correctness=0.00`

### Open issues / next

- the next family should be scope contamination, paired with `TranscriptRAGLite`
- preference drift should follow scope contamination
- the contradiction family still needs more independent held-out mechanisms, but only when they sharpen the result

## 2026-04-26 — Held-out contradiction family diversified

### What shipped

- expanded the held-out contradiction split from `dirty_v3`/`dirty_v4` to `dirty_v3` through `dirty_v6`
- added `dirty_v5`, a two-step correction cascade where Naive also recovers
- added `dirty_v6`, a cautious authoritative contradiction where Naive's confidence-first answer selection still hurts
- updated the held-out regression coverage and regenerated the held-out oracle artifacts

### Why it matters

- the held-out contradiction family no longer tests only “old confidence stays above new confidence”
- the new split now includes both:
  - a held-out case where Naive also recovers, so CQ's advantage is not limited to beating Reflection
  - a held-out case where confidence-first durable selection is itself the failure mode
- this makes the contradiction family a sharper probe of what CQ buys beyond simple confidence ranking
- `dirty_v5` is intentionally subtle: Naive recovers there by reinforcing the newer correction durable above the old claim, not by clean contradiction resolution

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` still passes with 29 tests
- held-out oracle run (`python3 -m cq.eval.runner --scenarios 4 --template-mix heldout`) now shows:
  - `reflection_eager_write_lite`: `false_assertion=1.00`, `recovery=0.00`
  - `consolidation_queue_lite`: `false_assertion=0.00`, `recovery=1.00`
  - `naive_eager_write_lite`: `false_assertion=0.75`, `recovery=0.25`
- per-template held-out result:
  - `dirty_v3`: Reflection fails, CQ recovers, Naive fails
  - `dirty_v4`: Reflection fails, CQ recovers, Naive fails
  - `dirty_v5`: Reflection fails, CQ recovers, Naive recovers via reinforcement into the newer correction durable
  - `dirty_v6`: Reflection fails, CQ recovers via pending memory, Naive fails

### Open issues / next

- the held-out contradiction family is better, but it still needs more independent mechanisms before it should carry strong conclusions by itself
- `NoMemory` and `TranscriptRAG` remain unimplemented
- preference drift and scope contamination are still the next benchmark families to add

## 2026-04-26 — Naive eager baseline added

### What shipped

- added `NaiveEagerWriteLite` as a third oracle-mode baseline on the shared substrate
- updated the default runner to compare `ReflectionEagerWriteLite`, `ConsolidationQueueLite`, and `NaiveEagerWriteLite`
- normalized `forced_contradiction_dirty_v2` so it forbids both old candidate ids, matching `dirty_v4`
- hardened the dashboard timeline by sorting lifecycle events before oracle-turn bucketing
- extended regression coverage to pin Naive behavior by template and verify the demotion event lands in the correct held-out turn bucket

### Why it matters

- the benchmark now separates three policies instead of two: staged promotion, reflected eager write, and append-only eager write
- `NaiveEagerWriteLite` isolates what Reflection's overwrite-margin is buying and where it hurts
- the key result is template-specific: Reflection fails on `dirty_v2`, while Naive recovers because it keeps both durables active and answers from the higher-confidence new durable

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes with 28 tests
- mixed oracle run (`python3 -m cq.eval.runner --scenarios 6 --template-mix mixed`) shows:
  - `reflection_eager_write_lite`: `false_assertion=0.67`, `recovery=0.33`
  - `consolidation_queue_lite`: `false_assertion=0.00`, `recovery=1.00`
  - `naive_eager_write_lite`: `false_assertion=0.33`, `recovery=0.67`
- per-template mixed result:
  - `dirty_v1`: Reflection fails, CQ recovers, Naive fails
  - `dirty_v2`: Reflection fails, CQ recovers, Naive recovers
- held-out oracle run (`python3 -m cq.eval.runner --scenarios 4 --template-mix heldout`) shows Naive matches Reflection and loses on both `dirty_v3` and `dirty_v4`
- saved artifacts:
  - `data/runs/forced_contradiction_oracle.json`
  - `data/runs/forced_contradiction_oracle_heldout.json`
  - `data/results/forced_contradiction_oracle_metrics.csv`
  - `data/results/forced_contradiction_oracle_heldout_metrics.csv`

### Open issues / next

- the held-out contradiction family still needs more independent mechanisms because `dirty_v2` and `dirty_v4` are both corroborated-old/sub-margin contradiction cases
- `NoMemory` and `TranscriptRAG` remain unimplemented
- preference drift and scope contamination are still the next benchmark families to add

## 2026-04-26 — Phase 1 contradiction slice hardened

### What shipped

- expanded the forced-contradiction oracle family from one clean path into multiple dirty variants plus held-out templates
- added per-template-kind, per-template-split, and per-template-id summaries
- added a static dashboard timeline grouped by oracle turn
- tightened regression coverage around dirty-template rotation, held-out behavior, summary slicing, and dashboard rendering

### Why it matters

- the contradiction benchmark stopped being a clean-path demo and became a real policy comparison
- CQ's advantage is now visible on dirty and held-out cases rather than only as “pending use versus early durable commit”
- saved traces make failure modes inspectable instead of hiding them inside aggregate scores

### Evidence

- the current mixed/held-out artifacts still preserve the core two-policy result:
  - Reflection fails on the dirty contradiction templates
  - CQ recovers on all shipped contradiction templates
- dashboard outputs:
  - `data/results/dashboard.html`
  - `data/results/dashboard_heldout.html`

### Open issues / next

- the contradiction family still needs more held-out mechanisms before the held-out split should carry much interpretive weight
- the repo still lacked a simpler eager baseline at this stage, which is why `NaiveEagerWriteLite` was added next
