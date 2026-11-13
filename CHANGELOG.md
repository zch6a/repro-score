# Changelog

## 0.1.0 — unreleased

First release.

- `repro-score path/to/repo`: a score out of 100 for a research code repository, item by item with the file and line
  each was decided from and what to add: dependencies and their versions, install and run instructions (and whether
  the scripts the README runs exist), training and evaluation code, trained models and data, random seeds, compute,
  licence and citation, notebooks. Read from the files; nothing is run.
- Text, Markdown (`--markdown`), JSON (`--json`), an SVG badge (`--badge`), `--min-score` for CI.
- A GitHub Action: the report in the job summary, the score as an output.
- `github:owner/repo[@ref]` and GitHub URLs, scored without cloning; several repositories, or `--list FILE`, give a
  table (text, CSV, Markdown, JSON) with the mean and median.
- `--check-links`: whether the model and data links still answer, listed beside the score.
- R and Julia: dependency files and versions, install commands, scripts, seeds, `test/` folders.
- `--summary-file` (appends the Markdown report, for `$GITHUB_STEP_SUMMARY`) and `--json-file`: the Action runs the tool once.
- Files in UTF-16 (PowerShell's `pip freeze >`) or with a BOM, and notebooks up to 50 MB, are read.
