# Live construction profile · 2026-09-05

This document describes implemented checks, not a claim that every planned
paper experiment has been executed.

## Generate → verify → publish

1. Collect English article text and a source image. Require a timezone-aware
   publication time no more than 48 hours old; reject future timestamps.
2. Ask Doubao for one event-specific fact, a short verbatim evidence span, and
   a question that uses the image to resolve a referent omitted from the text.
   Attach the report date **before** any verification. The generator's same-call
   self-answer is an evidence-aware shortcut heuristic, not a closed-book run.
3. P0 uses a separate image-aware audit. Image–article match must be 4/4,
   grounding at least 2/4, and other quality scores at least 3/4. Two separately
   prompted Qwen Plus checks must agree on the omitted referent. These latter
   checks use the image description, not independent pixel observations;
   omission checks are not proof of universal image necessity.
4. P1 presents **only image and question**, no tool, source, title, or evidence,
   to each of three models, four times, in separate API requests. One correct
   answer rejects the candidate. Temperature is 0.7 and top-p is 0.95.
5. P2 presents image, question, declared article title, and the gold excerpt to
   the same panel in new requests. One incorrect answer rejects the candidate.
   Temperature is 0.2 and top-p is 0.95. The title is explicitly part of this
   operational oracle; this must not be described as an evidence-only context.
6. Every accepted item retains all 24 panel predictions and verdicts. Early
   stopping saves calls only on rejects. Deduplicate questions and images,
   enforce composition, verify exact source offsets/content hashes, then
   promote atomically only if the complete requested split passes.

The generator shares one panel member. Decisions use fresh requests, but model
families are not independent. A separate held-out model evaluation is required
to establish transfer beyond this construction panel.

## Scoring

`answer_equivalence.py` preserves signs, decimal values, scale, currency, units,
percent versus percentage points, and fiscal/date context. Exact normalized
matches and compatible single quantities can be decided deterministically.
There is **no substring shortcut or global numeric tolerance**. Other answers
go to a logged semantic judge using the question, gold answer, and evidence.
An unresolved verdict is not silently counted as a P1 failure: it rejects the
candidate pending review. The judge is not an independent expert audit.

The `eq-conservative-20260905-v2` code also avoids treating every bare `$` as
USD: explicit currency changes require contextual grading. Earlier September 5
run records retain their original grader version and executed-code hashes;
they are not silently relabeled as runs of newer code.

## Provenance and limits

New records include build time, publication time, source hash, evidence offsets,
question/answer/evidence version hash, actual model IDs and decoding settings,
and private-ledger response IDs. Event grouping currently uses a deterministic
referent/fact/day hash; it is a heuristic, not an expert-validated event cluster.
Private ledgers are hashed when a run is sealed, with summary counts published
under `data/releases/`. They may contain copyrighted full source text and must
not be pushed to a public repository.

Offline validation verifies recorded outcomes; it is not a new independent
model evaluation. No human approval is claimed without rating matrices.
Retrieval-miss and distraction claims need actual agent-visible traces;
construction-panel responses alone do not establish them.

## Rejection vocabulary

| Type | Meaning |
| --- | --- |
| G | Generator refusal, invalid JSON, or malformed question |
| F | Non-fresh fact or invalid/out-of-window timestamp |
| V | Image mismatch, pixel-only question, or unresolved referent |
| E | Evidence not verbatim, unsupported answer, or invalid excerpt |
| N | A P1 closed-book attempt answers correctly |
| S | A P2 gold-evidence attempt answers incorrectly |
| D | Duplicate or composition constraint |
| X | API/parse failure or unresolved grading |

Raw rejection codes are also preserved. Auxiliary score-failure counters can
overlap; never sum them as if they were disjoint rejected items.

## Bounded supplementation and incomplete previews

The optional `supplement_v2.py` command is manual. `alternative-fact` attempts
one different newly reported fact/question for previously rejected articles.
It does not reroll an unchanged failed question until it happens to pass.
`typography-repair` can reuse a real logged proposal rejected because an exact
source span could not be located, repair quote/space normalization, and rerun
all P0/P1/P2 checks. These actions do not relax the admission thresholds.
Every supplement records its source run, eligible article IDs and executed code
hashes. Claims of cross-family generalization still require independent tests.

Example explicit command, using local private ledgers and locally configured keys:

```bash
python src/supplement_v2.py --source-run RUN_ID --mode alternative-fact --output benchmark_v2.retry.json
```

The 200-item release gate is separate from per-item validation. A short build
may be exposed under `data/previews/` with its true count, set-level shortfall,
unreviewed-human status, and a read-only audit. It must never silently replace
`data/benchmark_v2.json`. Source images and questions are deduplicated again
when combining independent supplementary runs.
