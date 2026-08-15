# Paper draft status

## Current story

The paper is organized around one claim: trustworthy automatic benchmark
construction requires a cooperative but asymmetric **generate--verify**
architecture.

- The generator improves proposal quality through evidence-first construction,
  image-dependent reference, quantitative preference, and same-call
  closed-book self-screening.
- The quality module establishes trust through deterministic checks,
  multimodal alignment audits, and strict P1/P2 panel certification.
- Typed rejection records connect the modules across days: failures improve
  later prompts, but feedback never replaces final certification.

This framing is stronger than a simple generate-then-filter pipeline because it
separates efficiency from validity. Generator improvements reduce how many
candidates require expensive review; the verifier remains the sole admission
authority and preserves a replayable audit ledger.

## Truth boundary

Measured and already implemented:

- 200 validated current items;
- 100% English sources;
- 78.5% numeric or temporal questions;
- exact evidence and numeric-span checks;
- strict image/article and referent-grounding audits;
- three-model x four-sample P1/P2 certification;
- cascade early stopping, atomic validation, demo generation.

Still simulated or planned:

- the 12-agent main-result table and Figure 4;
- the claimed approximately 60% matched cost reduction;
- multi-day stability, human audit, panel-swap/cross-generator robustness;
- distraction/noise stress results;
- automatic daily constitution-memory updates.

## Experiments needed to close the story

1. Run question-first vs evidence-first generation with identical articles and
   report P1/P2 pass rates, human validity, and cost per accepted item.
2. Run full-panel vs cascade evaluation on the same candidates and verify that
   accepted sets are identical while panel calls decrease.
3. Use held-out model families to estimate how well P1/P2 generalize beyond the
   construction panel.
4. Conduct a three-annotator audit of answer correctness, visual grounding,
   evidence sufficiency, and search necessity.
5. Evaluate agents over multiple daily splits with frozen retrieval snapshots,
   confidence intervals, paired significance tests, and trace-based error
   decomposition.
