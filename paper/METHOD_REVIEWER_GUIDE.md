# Method and evaluation guide

This English guide describes the current operational protocol. The earlier
LaTeX draft in this directory is historical; consult `docs/manuscript.pdf` and
`docs/PROTOCOL.md` for the current manuscript and implementation boundary.

## Generation and certification

The generator proposes evidence-first, visually grounded questions. P0 checks
image/source agreement and reference grounding. P1 requires every sampled
construction-panel answer without web access to be incorrect; P2 requires every
sampled answer with the declared gold context to be correct. Generator heuristics
can improve yield but cannot replace these acceptance checks.

Same-call generator self-screening is evidence-aware, not an independent
closed-book test. The live panel has three model entries from two providers;
the generator shares one member. Separate requests do not imply independent
model families. Certificates are finite and panel-relative.

## Answer equivalence

Exact normalized matches and compatible single quantities are checked
deterministically. Signs, units, scale, currency and date/period context matter.
There is no global numeric tolerance or substring shortcut. Ambiguous cases
use a logged semantic judge with the declared evidence; unresolved judgments
cannot count as P1 failures. A bare dollar sign is not automatically USD.

The operational oracle includes the declared article title and evidence, so it
must not be described as evidence-only. API errors, empty responses and parse
failures are not valid certification successes.

## Held-out transfer

A held-out model has not participated in generation or certification. Freeze
the construction panel and dataset, then measure closed-book accuracy of these
additional models. Low held-out leakage supports transfer beyond the panel;
it is not a universal or permanent guarantee of search necessity.

## Funnel and cost

Report articles, generated candidates, P0 pass, P1 pass, P2 pass, and released
items from one auditable run manifest. Include conditional pass rates, rejection
types, calls, tokens, retries, latency and actual billed costs. A 200-item target
must be distinguished from achieved yield. Logical early stopping can save
calls on rejected items; accepted items still require the complete panel.

Top-level rejection types are G (generation), F (freshness), V (visual grounding),
E (evidence), N (P1), S (P2), D (duplicates/composition), and X (operational or
unresolved-scoring errors). Auxiliary counters can overlap.

## Human review and error diagnosis

The planned five-expert audit evaluates answer correctness, evidence sufficiency,
image/source agreement, reference grounding, search necessity and acceptability.
Report per-item majority decisions and agreement measures from actual ratings.
Do not label example agreement values as observed results.

An oracle-versus-search accuracy gap does not identify its cause. Distinguish
missing evidence, distraction by conflicting evidence, utilization errors and
operational failures using the content actually visible to each agent. A causal
distraction test holds the correct evidence fixed and adds matched distractors.

## Evaluation logic and current status

Benchmark validity establishes the measurement conditions. Agent comparisons,
held-out transfer, retrieval traces and controlled distraction then address
search capability. Generation/certification ablations, visual interventions,
cost and cross-date checks explain the instrument's properties and limitations.

The working manuscript contains explicitly identified synthetic demonstrations.
They remain distinct from the real construction records. The September 5 attempt
yielded 121 items, not 200; human review and held-out evaluation remain pending.
The English-only August 18 artifact is a subset, not a new construction run.
