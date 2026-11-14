<div align="center">

# repro-score

**Can someone reproduce your paper from your code?** A score out of 100 for a research code repository, item by
item, each with the file and line it was decided from and what to add — read from the files, without running
anything.

<a href="https://github.com/zch6a/repro-score/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/zch6a/repro-score/actions/workflows/ci.yml/badge.svg"></a>
<img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue">
<img alt="No dependencies" src="https://img.shields.io/badge/dependencies-none-2ea44f">
<a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-blue"></a>

**English** · [简体中文](README.zh-CN.md)

</div>

---

Papers with Code looked at more than 200 machine-learning repositories and wrote down what the reproducible ones have
in common: the dependencies, the training code, the evaluation code, the trained models, and a README with the
results and the commands that produce them (their [ML Code Completeness
Checklist](https://github.com/paperswithcode/releasing-research-code)). The NeurIPS paper checklist asks the same, and
for the compute. repro-score checks a repository for all of it, before you release it or before you try to reproduce
someone else's.

```bash
uvx --from git+https://github.com/zch6a/repro-score repro-score path/to/repo
uvx --from git+https://github.com/zch6a/repro-score repro-score github:owner/repo     # without cloning it
```

```
repro-score: paper-code: 65/100
Dependencies  11/20
  ✓ a file listing the dependencies  7/7
      requirements.txt
  ~ versions pinned (2 of 5 requirements)  4/7
      requirements.txt:3: numpy>=1.24
      requirements.txt:4: pyyaml
      requirements.txt:5: tqdm
      → pin each package to the version you ran (pip freeze, conda env export, or a lock file)
  ✗ the Python (or language) version stated  0/3
      → say which Python version it ran on (requires-python, python= in environment.yml, or the README)
  ✗ a container or environment file  0/3
      → add a Dockerfile or a conda environment.yml so the whole environment, not only the Python packages, can be rebuilt
Instructions  17/20
  ✓ a README (156 words)  3/3
      README.md
  ✓ install commands  5/5
      README.md:9: pip install -r requirements.txt
  ~ commands to run (4 in code blocks)  3/6
      README.md:23: runs scripts/eval_all.sh, which is not in the repository
      README.md:15: python train.py --config configs/cifar10.yaml
      README.md:16: python train.py --config configs/cifar100.yaml
      → the README runs files that are not in the repository: add them or fix the commands
  ✓ a table of results  6/6
      README.md:30: | CIFAR-10 | 94.1 | 4.2 |
      README.md:31: | CIFAR-100 | 76.8 | 4.3 |
Training and evaluation code  15/15
  ✓ training code  6/6
      train.py
  ✓ evaluation code  6/6
      eval.py
  ✓ hyperparameters in configs or arguments  3/3
      configs/cifar10.yaml
      configs/cifar100.yaml
Models and data  7/15
  ✗ trained models to download  0/8
      → release the trained models (a Hugging Face, Zenodo or GitHub release link) so the results can be checked without retraining
  ✓ where the data comes from  7/7
      README.md:34: https://www.cs.toronto.edu/~kriz/cifar.html
Randomness  6/10
  ✓ random seeds set  6/6
      train.py:15: random.seed(args.seed)
  ✗ deterministic settings  0/4
      → where it matters, make GPU kernels deterministic (torch.use_deterministic_algorithms(True), cudnn.deterministic)
Compute  0/5
  ✗ the hardware it ran on  0/3
      → say which GPUs (or TPUs) and how many the experiments used
  ✗ how long it takes, or how much memory  0/2
      → say how long training and evaluation take, and how much GPU memory they need
Licence and citation  6/10
  ✓ a licence (MIT)  6/6
      LICENSE: MIT
  ✗ how to cite it  0/4
      → add a CITATION.cff, or the paper's BibTeX in the README
Notebooks: does not apply
```

That is the made-up repository in [examples/paper-code](examples/paper-code). `--brief` leaves the evidence out,
`--markdown` gives a table (for a pull request or a job summary), `--json` the whole report, `--badge score.svg` a
badge, and `--min-score 60` exits 1 below 60. In Python (`pip install git+https://github.com/zch6a/repro-score`):
`repro_score.score_repo(Path("repo"))` returns the report, with `.score`, `.items` and `.json()`.

## Many repositories at once

```bash
repro-score --list repos.txt --csv > scores.csv     # one per line: folders, github:owner/repo[@ref], GitHub URLs
```

One row each — the score and each section's points — then the mean and median: the reproducibility of a venue's
code releases, a lab's repositories, or a reading list. A GitHub repository is downloaded as an archive to a
temporary folder (300 MB at most, 2 GB unpacked, 3 seconds between downloads, no token), read, and deleted; one that
cannot be downloaded is reported in its row. Text, `--csv`, `--markdown` or `--json`.

## Dead links: `--check-links`

The models and data links it counted are asked whether they still answer (HEAD, or a one-byte GET where HEAD is
refused; at most 40 links, a second apart on the same host): each is ok, dead (a 404, 410 or 5xx), unreachable, or
unclear (a sign-in page, a bot check, a rate limit). Dead links are listed beside the score, which does not count
them, so the score stays the same offline.

## Before a release: `repro-score release`

A release is written down in many places, and they drift: the tag says v1.2.0, CITATION.cff still says 1.1.0, the
README shows a Zenodo DOI that CITATION.cff does not have. `repro-score release` reads them all and says what
disagrees, each value with its file and line (exit 1 when something does):

```console
$ repro-score release .
repro-score release: open_clip
  version:
    4.2.2                    src/open_clip/version.py:1  (__version__)
    v0.1                     CITATION.cff:31  (CITATION.cff version)
    4.2.1                    HISTORY.md:1  (CHANGELOG newest)
    v4.2.2                   .git  (newest of 59 version tag(s))
  date:
    2021-07-28               CITATION.cff:33  (CITATION.cff date-released)
  doi:
    10.5281/zenodo.5143773   CITATION.cff:32  (CITATION.cff)
    10.5281/zenodo.5143773   README.md:690  (README (Zenodo))

  ✗ the version is not the same everywhere: 4.2.2 in src/open_clip/version.py, .git; but v0.1 in CITATION.cff:31 (CITATION.cff version); 4.2.1 in HISTORY.md:1 (CHANGELOG newest)
  · CITATION.cff's date-released (2021-07-28) is probably for its own version, not the newest tag v4.2.2
```

That is open_clip as it was on 2026-11-14. What it reads: the package's version (`pyproject.toml`, `setup.py`,
`setup.cfg`, `package.json` at the top; `__version__`), an agent plugin's `plugin.json`, `CITATION.cff` (version,
date-released, doi, and the fields the format requires), `.zenodo.json`, `codemeta.json`, the newest CHANGELOG entry
(an "Unreleased" one is skipped), a model card's version, Zenodo DOIs in the README, and the newest version tag (from
`.git/refs/tags` and `.git/packed-refs`, without running git; pre-releases left out). A development version
(`1.16.0.dev0` after `v1.15.0`) is noted, not compared; when every file agrees on a version newer than the last tag,
the release is noted as not tagged yet.

Measured on 12 well-known research repositories (PEFT, TRL, Accelerate, lm-evaluation-harness, LitGPT, open_clip,
Ultralytics, OLMo, DSPy, PyG, Flax, xFormers; the code as GitHub serves it, the tags from GitHub's API): 7 agree (2 of
them with a release written down but not tagged), and the 5 disagreements are real: Ultralytics' CITATION.cff says
8.0.0 at 8.4.212, open_clip's says v0.1 at 4.2.2, LitGPT's pyproject.toml is one behind its tag, PyG tagged 2.8.1 with
no CHANGELOG entry, Flax's CHANGELOG stops at 0.8.2. The first version also compared sub-packages' own manifests
(`benchmark/setup.py`), development versions, an odd old tag (`v0.03` among `v0.0.37`) and Zenodo badge URLs; fixed.
On this toolkit's own repositories it found four whose Claude Code `plugin.json` had stayed at the previous version.

## What it checks

| Section | Points | What counts |
|---|---|---|
| Dependencies | 20 | a requirements, environment or pyproject file (packages named only in a README `pip install` count for part); versions pinned (a lock file, or `==` for 80% of them); the Python version; a Dockerfile or conda environment |
| Instructions | 20 | a README; install commands; commands that run the code, in code blocks, whose scripts exist in the repository; a table of results |
| Training and evaluation code | 15 | training scripts; evaluation scripts (unit tests are not); hyperparameters in config files or command-line defaults |
| Models and data | 15 | links to the trained models (Hugging Face, Zenodo, GitHub releases, Drive, weights files) or code that loads them; where each dataset comes from (links, download scripts, a library that fetches it) |
| Randomness | 10 | seeds set in the code (`torch.manual_seed`, `np.random.seed`, `seed_everything`...); deterministic GPU settings |
| Compute | 5 | the GPUs or TPUs it ran on; how long it takes, or the memory it needs |
| Licence and citation | 10 | a licence, recognised by its wording (MIT, Apache, BSD, GPL, Creative Commons, OpenRAIL...); a CITATION.cff or the BibTeX |
| Notebooks | 5 | saved with their outputs, and run top to bottom |

The score is the points over the points that apply: a repository with no notebooks, or no code at all, is not marked
down for them. The first five sections are the Papers with Code checklist (dependencies; training code; evaluation
code; pre-trained models; results with the commands); the compute is the NeurIPS checklist's question on it.

## In CI: a GitHub Action

```yaml
- uses: actions/checkout@v7
- uses: zch6a/repro-score@v0    # or a release tag (v0.1.0), or a commit, to pin it
  with:
    min-score: 60          # optional: fail under 60
    badge: docs/repro-score.svg   # optional
```

The report goes to the job summary; the score is the step's `score` output. The action reads the repository and runs
none of its code.

## Limits

- It reads; it does not run. A README can name a script that exists and still fails; a link it counts can be dead
  unless you check them (`--check-links`). The score says what a repository gives a reader, not that its results
  reproduce.
- It is for a paper's code. A library (a package others build on) has no training run, results table or models to
  release, and scores low on those items, rightly for reproducing a paper but not as a judgement of the library.
- It knows Python projects best. R and Julia get their own dependency files and versions (`DESCRIPTION`,
  `renv.lock`, `Project.toml`, `Manifest.toml`), install commands (`install.packages`, `Pkg.add`), scripts
  (`source("run.R")`, `include("run.jl")`) and seeds (`set.seed`, `Random.seed!`); other languages, less.
- Words decide some items (training and evaluation scripts by their names and arguments, data by the words near a
  link): a script called `run.py` that trains, with no `--is_training` or `--do_train` argument, is not seen as training
  code unless the README's command says so.

## Also in this toolkit

[fig-check](https://github.com/zch6a/fig-check) checks a paper's figures as they will print ·
[submit-check](https://github.com/zch6a/submit-check) checks a submission against the venue's rules ·
[exp-tables](https://github.com/zch6a/exp-tables) makes results tables with significance ·
[gpu-budget](https://github.com/zch6a/gpu-budget) works out GPU memory, time and cost.

## Part of research-kit

One of thirteen open research tools, from reading papers to after publication. All of them, in the order of
the work, with one Claude Code plugin marketplace for their skills: [research-kit](https://github.com/zch6a/research-kit)
· [site](https://zch6a.github.io/research-kit/).

## License

MIT. The checklist it follows is Papers with Code's (MIT licensed).
