# Polish log

### 2026-11-13 — development

**Why it exists**: whether a paper's code can be reproduced is mostly decided by what the repository gives a reader
— pinned dependencies, the commands, the trained models, the data — and that can be checked before anyone tries.
Papers with Code's ML Code Completeness Checklist (from more than 200 ML repositories; MIT licensed) and the NeurIPS
checklist's questions on code and compute say what to look for. Similar tools exist (rrdoctor, a hackathon's
RepoAudit, an early "repro-check" package); none gives each item's evidence as a file and line, checks that the
README's commands name scripts that exist, or ships a GitHub Action with a badge.

**What it does**: reads a repository's files (no code run, no links fetched, symbolic links not followed) and scores
eight sections — dependencies, instructions, training and evaluation code, models and data, randomness, compute,
licence and citation, notebooks — out of 100 over the items that apply. Text, Markdown, JSON, an SVG badge,
`--min-score`; a composite GitHub Action whose inputs reach the script as environment variables.

**Sources** (read on 2026-11-13): the Papers with Code checklist's five items, quoted in the module docstring and
README; the NeurIPS checklist's compute and "exact command and environment" guidance (its 2026 page answered 500; the
2022 and 2021 guidelines and papers' answers were read instead).

**Tried on nine well-known research repositories** (downloaded as tarballs to the scratchpad, never run, deleted
after: nanoGPT, Segment Anything, Stable Diffusion, ControlNet, CLIP, BERT, MAE, DDPM, GCN; scores 33–91, each report
read line by line). **Found and fixed**:

1. ControlNet's commands are indented Markdown code blocks: not seen (instructions 3/20); indented blocks read now.
2. A conda environment's `pip:` sub-list header was counted as a requirement.
3. Stable Diffusion's CreativeML OpenRAIL-M licence was not recognised; OpenRAIL, CC BY-SA/NC-SA, Llama added.
4. nanoGPT names its packages only in a README `pip install` line: 0/20 for dependencies; they count for part now,
   and their pins are checked.
5. Training found from README commands was evidence without the command (`README.md:908`); `run_pretraining.py`
   (BERT) was missed (`-ing` forms).
6. `tools/test_net.py` (Detectron's evaluation script) was taken for a unit test by its name: a file is a unit test
   when it is in tests/ or written for pytest/unittest.
7. A missing script in a folder that does not exist was excused by the rule meant for `python -m` modules of
   installed packages.
8. A dataset page linked on the line after "downloaded by torchvision" did not count as data: a link near words about
   data does, as does code that loads a dataset through a library.
9. Evidence lines were cut at their start, losing the match: a window around the match is shown.

Some low scores are right and stay: Segment Anything and CLIP release no training code.

`examples/paper-code` is made up; a test checks the README's output against it and CI runs the Action on it (its
score and badge, and that a minimum it does not reach fails the step).

Tests: 39 (with doctests). ruff, ruff format, mypy clean.

Next: polishing round 1 (`--check-links` to find dead model and data links, opt-in and rate-limited; scoring a list
of repositories at once, for a venue's papers; a look at more real repositories, R and Julia among them).
