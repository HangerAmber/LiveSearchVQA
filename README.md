# LiveSearchVQA

**An on-demand, generate--verify benchmark for diagnosing the web-search
capability of multimodal agents.**

[Public demo](https://hangeramber.github.io/LiveSearchVQA/demo.html)

## What is released

The current v3 release contains 200 open-ended VQA items built from
image-bearing news published within 48 hours. Each record includes a short
answer, verbatim evidence, source provenance, image-alignment audits, and the
complete closed-book/oracle certification trace.

Measured properties of the 2026-08-18 build:

- 200 items, 200 unique images, and 200 unique questions;
- 171/200 (85.5%) English-language sources;
- 155/200 (77.5%) numeric or temporal questions;
- 29 source domains and six broad categories;
- image--article match at least 4/4 and question--image grounding at least 2/4;
- three certification models, four samples per condition;
- offline validator: PASS with zero errors and zero warnings.

The primary release is **data/benchmark_v2.json**; **data/benchmark.json** is
the legacy v1 multiple-choice split.

Every replaced v2 release is preserved under **data/archive_v2/YYYY-MM-DD.json**.
The public demo exposes a dated-snapshot selector and loads the selected
200-item split together with its original images and certification traces.

## Two-module pipeline

### Generator module

1. Crawl recent English-first RSS/news sources and obtain article text plus a
   genuine content image.
2. Select a new, event-specific evidence sentence before writing the question.
3. Construct an image-dependent English question, preferring numeric or
   temporal facts.
4. Perform a same-call closed-book self-check and reject obvious violations.

### Quality module

1. Validate freshness, exact evidence, answer span, language, and question form.
2. Audit image--article match and whether the image resolves the omitted
   referent in the question.
3. Certify P1 (all closed-book attempts fail) and P2 (all oracle attempts
   succeed) with a three-model x four-sample panel.
4. Deduplicate, enforce composition constraints, validate atomically, then
   promote the build and regenerate the demo.

Closed-book certification uses OR rejection and stops on the first correct
answer. Oracle certification uses AND admission and stops on the first failure.
Early stopping reduces work on rejected candidates but every released item
still carries the complete P1/P2 certificate.

## Run locally

Create a repository-local **.env** file with ARK_API_KEY and QWEN_API_KEY, then
run:

    python src/crawler.py
    python src/generate_v2.py 200
    python src/validate_v2.py --input benchmark_v2.next.json --target 200 --promote
    python src/build_demo.py

Or execute the safe on-demand orchestration:

    python src/daily.py

The workflow runs only when explicitly invoked, stages output first, validates
all release invariants, and only then replaces the public split. The GitHub
Actions workflow is manual-only (`workflow_dispatch`) and has no schedule.

## Paper

The ICLR-style draft is in **paper/main.tex**. It now presents the benchmark as
a cooperative generator--quality system and includes four vector figures in
**paper/figures/**.

Experimental results explicitly marked in blue are simulated draft
placeholders. The current-build audit table is measured from the released JSON
and validation report. Replace all placeholders with reproducible evaluation
logs before submission.
