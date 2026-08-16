# LiveSearchVQA Overleaf package

## Upload and compile

1. Upload the supplied ZIP with **New Project -> Upload Project**.
2. Set `main.tex` as the main document if Overleaf does not detect it.
3. Use the **pdfLaTeX** compiler. Overleaf's normal recompile action runs the
   required LaTeX/BibTeX passes automatically.

All figure PDFs, the bibliography, and the unmodified official ICLR style
dependencies are included, so the project has no external file dependency.

## Conference-style note

This draft targets the ICLR 2027 submission cycle. On 2026-08-17 the official
author page pointed to `iclr2027.zip`, but that archive was not yet present in
the official `ICLR/Master-Template` repository. For reproducible draft
compilation, this package uses the latest officially available style,
`iclr2026_conference.sty`, without modification.

Once ICLR publishes the 2027 kit:

1. Replace `iclr2026_conference.sty` and `iclr2026_conference.bst` with the
   official 2027 files (and any accompanying official dependencies).
2. Change the two occurrences of `iclr2026_conference` in `main.tex` to
   `iclr2027_conference`.
3. Recompile and confirm that the main text stays within the official page
   limit. Do not edit either official style file.

## Draft truth boundary

- Table 2 reports measured properties of the released 200-item build.
- Blue numbers in the abstract, Table 3, the cost expectation, and Figure 4
  are simulated placeholders retained to specify the intended hypotheses and
  analysis. They are not submission-ready empirical results.
- The workflow is on-demand only; the manuscript does not require or schedule
  automatic API-backed data generation.
