---
name: repro-score
description: Check how well a research code repository lets someone reproduce its paper, with repro-score: dependencies and pinned versions, install and run instructions (and whether the scripts they run exist), training and evaluation code, links to trained models and data, random seeds, compute, licence, citation, notebooks. Reads files only, runs nothing. Use when the user is about to release a paper's code, asks whether a repository is reproducible or what it is missing, or wants a reproducibility badge or CI check.
license: MIT
compatibility: Needs Python 3.10+ and uv. Runs repro-score with uvx from GitHub (git+https://github.com/zch6a/repro-score) unless installed. Reads local files only; no network.
metadata:
  homepage: https://github.com/zch6a/repro-score
---

# Checking a research repository with repro-score

```bash
uvx --from git+https://github.com/zch6a/repro-score repro-score path/to/repo
```

- Read the report to the user section by section, worst first: each missing item has an arrow line saying what to
  add. Point at the evidence lines (file:line) rather than retelling them.
- Offer to fix what can be fixed from the repository itself, and only with the user's go-ahead: pin the versions
  they ran (from their environment, not guessed), add the commands the README lacks, fix a command whose script does
  not exist, add a CITATION.cff from the paper's details. Do not invent results, links, hardware or licences: ask.
- For CI, the GitHub Action: `uses: zch6a/repro-score@v0` with `min-score:`; `--badge docs/repro-score.svg` makes a
  badge for the README.
- It does not run code or open links: a high score means the repository gives readers what they need, not that the
  results reproduce.
