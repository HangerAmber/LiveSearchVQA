# LiveSearchVQA: A Daily Self-Refreshing VQA Benchmark for Diagnosing the Web-Search Capability of Multimodal Agents

## 1. Motivation & gap

Web search is now a core capability of VLM agents, yet no benchmark measures
it reliably:

- **Static VQA benchmarks** (OK-VQA, InfoSeek, MMSearch...) leak into training
  data within months — high scores conflate memorization with search.
- **LiveVQA (2025)** builds VQA from news but releases static snapshots; it
  does not refresh daily and does not localize *where* the search agent fails.
- **Dyn-VQA / FreshQA** target answer drift, but rely on manual curation and
  infrequent updates (FreshQA is text-only).

**Gap:** a fully automated, *daily* refreshed VQA benchmark that (a) is
contamination-free by construction and (b) attributes an agent's error to a
specific stage of the search loop.

## 2. Core contributions (paper highlights)

1. **Contamination-free by construction.** Questions are built only from
   news published < 48 h before evaluation. No model checkpoint can contain
   the answers. The benchmark never "expires": the pipeline emits a new
   200-question split every day; historical splits form a longitudinal record.

2. **Three-way diagnostic protocol.** Each item ships with gold answer,
   verbatim evidence, source URL and timestamps. Each agent is scored under:
   - *Closed-book* (no search) — ≈ 0 by construction (enforced by filtering);
   - *With-search* (agent searches freely) — headline score;
   - *Oracle-evidence* (gold snippet given) — upper bound.

   The gap decomposes error into the three failure modes the community cares
   about: **retrieval failure** (evidence never retrieved: crawl imprecise or
   incomplete), **distraction failure** (evidence present in the agent's
   context, answer still wrong — over-retrieval noise), and **utilization
   failure** (wrong even with oracle evidence). A *distraction stress test*
   variant injects k topically-related but irrelevant retrieved passages.

3. **Fully automated construction with self-verifying filters** (no human in
   the loop, ~US$2/day of API cost):
   - Stage A: VLM generates image-grounded MCQs from (image, fresh article);
   - Stage B *anti-memorization filter*: a strong VLM answers closed-book;
     items it gets right are discarded (58% of generated items on 2026-07-14
     — showing how much of "fresh" news is actually guessable, itself an
     interesting measurement);
   - Stage C *answerability filter*: the VLM must answer correctly given the
     gold evidence, guaranteeing every kept item is solvable end-to-end;
   - option positions reshuffled to remove generator position bias.

4. **Longitudinal capability tracking.** Because the same pipeline runs daily,
   the benchmark doubles as a time series: how does agent accuracy vary with
   event recency (6 h vs 48 h), topic, language of source, question type?

## 3. Pipeline (implemented in this repo)

```
20+ RSS channels (CN+EN, tech/politics/sports/finance/world...)
 → freshness enforcement (pubDate or URL-embedded date, <48 h)
 → article text + news image extraction (og:image + content-region heuristics)
 → Stage A/B/C generation & filtering (Doubao Seed 2.0 Pro)
 → 200-item daily split + interactive HTML explorer
```

First build (2026-07-14): 200 questions from 126 articles across 7 sources;
6 question types (numerical 83, factual 45, temporal 28, identification 15,
cross-modal 15, causal 14); acceptance rate 40%; closed-book filter removed
58% of generated candidates; oracle-filter removed 1.4%.

## 4. Planned experiments (for the paper)

1. **Main table:** 8–10 agents (GPT-5/o-series + search, Gemini + grounding,
   Qwen-VL + search tools, open-source agent frameworks with SerpAPI/Bing)
   under the three settings; report accuracy + error decomposition.
2. **Distraction curve:** accuracy vs. number of injected noisy passages.
3. **Recency curve:** accuracy vs. article age at evaluation time.
4. **Cross-generator robustness:** regenerate a split with a different VLM
   (e.g. GPT) and show ranking stability → benchmark is not generator-biased.
5. **Human validation:** a 100-item audit for answer correctness, image
   grounding, and option fairness (report agreement ≥ 95%).
6. **Contamination probe:** evaluate a model on same-day vs. 6-month-old
   splits to quantify how fast "live" items decay into memorized knowledge.

## 5. Risks & mitigations

- *Generator bias / circularity* (same model generates and filters):
  mitigated by cross-generator experiment (4) and human audit (5).
- *Topical skew* toward tech (CN feeds dominate): add more EN world-news
  channels; stratified sampling per category when selecting the daily 200.
- *Source link rot*: archive article HTML + image at crawl time (already
  stored locally).
- *MCQ guessability*: closed-book filter bounds it; also report the
  open-ended (no options) variant as a harder track.
