# Paper draft status

## Current story

The paper is organized around one claim: trustworthy automatic benchmark
construction requires a cooperative but asymmetric **generate--verify**
architecture and produces **certificate-carrying benchmark items**.

- The generator improves proposal quality through evidence-first construction,
  image-dependent reference, quantitative preference, and same-call
  closed-book self-screening.
- The quality module establishes trust through deterministic checks,
  multimodal alignment audits, and strict P1/P2 panel certification.
- Typed rejection records connect explicitly triggered builds: failures
  improve later prompts, but feedback never replaces final certification.

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
- automatic constitution-memory updates between explicitly triggered builds.

## ICLR / Overleaf status

- The manuscript follows the current ICLR 2027 anonymity, nine-page main-text,
  reproducibility, ethics, and required AI-use expectations.
- As of 2026-08-17, the ICLR 2027 author page links to `iclr2027.zip`, but the
  official Master-Template repository has not published that file. The
  Overleaf bundle therefore uses the latest available unmodified official
  style (`iclr2026_conference.sty`) for draft compilation.
- When the official 2027 kit is released, replace the official style/BST files
  and change the two `iclr2026_conference` references in `main.tex`; do not
  modify the conference style itself.
- Blue numbers and Figure 4 remain simulated planning values and must be
  replaced by reproducible logs before submission.

## Experiments needed to close the story

1. Run question-first vs evidence-first generation with identical articles and
   report P1/P2 pass rates, human validity, and cost per accepted item.
2. Run full-panel vs cascade evaluation on the same candidates and verify that
   accepted sets are identical while panel calls decrease.
3. Use held-out model families to estimate how well P1/P2 generalize beyond the
   construction panel.
4. Conduct a three-annotator audit of answer correctness, visual grounding,
   evidence sufficiency, and search necessity.
5. Evaluate agents over multiple dated builds with frozen retrieval snapshots,
   confidence intervals, paired significance tests, and trace-based error
   decomposition.
