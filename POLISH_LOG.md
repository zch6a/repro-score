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

### 2026-11-13 — polishing round 1

**Many repositories, and GitHub ones without cloning** (the plan's "a venue's papers' code"): `github:owner/repo[@ref]`
and GitHub URLs are downloaded as archives (GitHub's public archive endpoint, no token, 300 MB cap, 3 s between
downloads) into a temporary folder, extracted with tarfile's data filter, read and deleted. Several targets or
`--list FILE` give a table, one row each with the sections' points, then the mean and median; text, CSV, Markdown,
JSON. A repository that cannot be downloaded is reported in its row, not fatal.

**`--check-links`**: every model and data link the docs give (not only the three shown as evidence), HEAD then a
one-byte GET where HEAD is refused; ok, dead, unreachable, or unclear (401/403/405/429: sign-in pages, bot checks,
rate limits). At most 40, a second apart per host. Dead links are listed beside the score, which does not count them,
so a score is the same offline and online. Tried on DINO: 40 of its 70 links checked, all answer.

**R and Julia**, tried on Seurat and DiffEqFlux.jl: their language versions (`Depends: R (>= …)`, `julia = …` in
`[compat]`), install commands (`install.packages`, `remotes::install_github`, `BiocManager::install`, `Pkg.add`,
`] add`), scripts (`source("run.R")`, `include("run.jl")`, checked to exist) are read now. **Found**: their `test/`
folders (Julia's, R's `tests/testthat`) were not taken for tests, so a test's `Random.seed!` counted as the
experiments' seed; documentation and paper links (docs.*, readthedocs, arXiv, DOIs) next to the word "data" counted as
data links, and a `data.html` page matched the data-host pattern. Both libraries still score low, rightly for
reproducing a paper; the README now says a library is not judged as a library.

**Fifteen real repositories in one run** (the nine from development, and DINO, improved-diffusion, SimCLR,
Detectron2, Seurat, DiffEqFlux.jl; scored from GitHub, nothing kept): scores 34–91, mean 64.3, median 64; the
development fixes held (no score moved except where a fix applied).

Tests: 49 (downloads and link checks faked: a tarball with a symbolic link and a `../` path, which are not
extracted; statuses from a fake opener). ruff, ruff format, mypy clean.

Next: polishing round 2 (an independent review of the checks; the Action tried in a real workflow on a repository
of its own; the social card).
### 2026-11-13 — polishing round 2

**An independent review** (a reviewer given the code, not my conclusions; every finding reproduced first, a
regression test each in `tests/test_review.py`):

- Crashes: a notebook cell whose `source` is not text (`[null]`, a number); a JSON number too long for `int()`
  (Python 3.11+'s digit limit); a server's malformed reply (`BadStatusLine`, `IncompleteRead`) in `--check-links` and
  in downloads. All now read as "nothing there" or "unreachable".
- Wrong scores: notebooks over 2 MB (the ones saved with outputs) were not read — up to 50 MB now (Stable Diffusion's
  notebooks section applies now); UTF-16 files (PowerShell 5's `pip freeze >`) and BOMs were misread; a pyproject
  dependency with extras (`uvicorn[standard]==0.23`) ended the list early; a pyproject or setup.cfg holding only tool
  settings counted as a dependency file (Segment Anything: 10 → 6, rightly: its setup.py lists nothing); an
  environment marker (`python_version < "3.7"`) passed as the Python version; `conda install -c conda-forge` took
  `conda-forge` for a package; a bare `git+…@<commit>` counted as unpinned; Hugging Face's settings pages, any `.zip`,
  installers ("Download Anaconda"), PyPI pages, and data URLs in `requirements-dev.txt` counted as models or data;
  `cd src && python train.py`, `(env) $` prompts, and a `cd` line before a command were not followed; a licence it does
  not recognise had full points (now part, with advice); data-splitting scripts counted as training and evaluation code;
  a closing fence inside a longer fence ended the block; `**https://…**` kept the asterisks in the URL.
- Slow: three patterns backtracked quadratically on long lines (20k spaces: 3.6 s); patterns now search the first
  4,000 characters of a line, and each document is split once for link context, not once per link.
- Downloads: the compressed size was capped, not what it unpacks to (a 300 MB archive can expand to terabytes): 2 GB
  now; Python 3.10 before 3.10.12 has no tarfile data filter, so paths are also checked by hand there. A batch whose
  every download fails exits 2.
- The Action ran the tool three times (three downloads for a `github:` path) and used the runner's `python3`: one run
  now (`--summary-file`, `--json-file`), uv's Python, and `--` before the path.
- The example's sentence about its datasets now says "datasets" (it said only "downloaded", which no longer counts by
  itself, as the review asked); the README's output is regenerated.

Fifteen real repositories scored again: only the two scores above moved.

**Social card**: `scripts/social-card.html`, rendered with headless Chrome (no network, its own profile, deleted after)
to `docs/social-preview.png`. Setting it as the repository's preview is a repository setting for its owner.

Tests: 78. ruff, ruff format, mypy clean.

Next: polishing round 3 (the Action used from another repository's workflow by its tag after the release; CLI and
JSON review; packaging check of the wheel).