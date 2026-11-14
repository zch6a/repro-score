# Changelog

## 0.2.0 — 2026-11-14

- **`repro-score release [FOLDER]`**: do the places that state a release agree? The package's version (top-level
  manifests, `__version__`), a plugin's `plugin.json`, CITATION.cff (and its required fields), .zenodo.json,
  codemeta.json, the newest CHANGELOG entry, a model card, Zenodo DOIs in the README, and the newest version tag (read
  from `.git` without running git). Development versions are noted, not compared; a release written down but not
  tagged is noted. Exit 1 on a disagreement; `--json`.
- Measured on 12 well-known research repositories: 5 real disagreements found (stale CITATION.cff versions, a
  CHANGELOG behind its tags, a pyproject.toml behind its tag), none false after the fixes the measurement prompted.

## 0.1.1 — 2026-11-14

- The agent skill's frontmatter is valid YAML again: its description held a `: `, which YAML reads as a new key, so
  the whole frontmatter failed to parse and the skill loaded without its description (`claude plugin validate`
  reported it). The values are quoted now.

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
