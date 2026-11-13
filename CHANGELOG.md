# Changelog

## 0.1.0 — 2026-11-14

First release.

**Scoring a repository**

- `repro-score path/to/repo` or `repro-score github:owner/repo[@ref]` (no clone: the archive is read in a temporary
  folder and deleted): a score out of 100, item by item with the file and line each was decided from and what to add.
  Nothing in the repository is run.
- Eight sections, the first five from Papers with Code's ML Code Completeness Checklist: dependencies and their pinned
  versions, the language version and environment; install and run instructions, and whether the scripts the README
  runs exist; training and evaluation code and their hyperparameters; links to trained models and to data; random
  seeds and deterministic settings; the compute stated (NeurIPS checklist); licence and citation; notebooks saved with
  their outputs and run in order. Items that do not apply are left out of the score.
- Python best; R and Julia dependency files, installs, scripts and seeds too.

**Many repositories, links, CI**

- Several targets, or `--list FILE`: a table (text, CSV, Markdown, JSON) with the mean and median, for a venue's or a
  lab's code.
- `--check-links`: whether the model and data links still answer, listed beside the score, which stays the same
  offline.
- `--markdown`, `--json`, `--badge` (SVG), `--min-score` (exit 1 under it), `--summary-file`, `--json-file`.
- A GitHub Action: the report in the job summary, the score as an output, an optional badge and minimum.

Tried on 45 real research repositories (NeurIPS 2024 code among them). No dependencies; typed.
