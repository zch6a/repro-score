# Changelog

## 0.1.0 — unreleased

First release.

- `repro-score path/to/repo`: a score out of 100 for a research code repository, item by item with the file and line
  each was decided from and what to add: dependencies and their versions, install and run instructions (and whether
  the scripts the README runs exist), training and evaluation code, trained models and data, random seeds, compute,
  licence and citation, notebooks. Read from the files; nothing is run.
- Text, Markdown (`--markdown`), JSON (`--json`), an SVG badge (`--badge`), `--min-score` for CI.
- A GitHub Action: the report in the job summary, the score as an output.
