"""The checks: what a repository gives someone who wants to reproduce its paper, read from its files.

The sections follow Papers with Code's ML Code Completeness Checklist (dependencies, training code, evaluation code,
pre-trained models, a README with results and the commands that produce them) and the NeurIPS paper checklist's
questions on code, data and compute; randomness, licence and notebooks are added. Each item is points out of a maximum,
with the files and lines it was decided from.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .repo import Repo


@dataclass
class Evidence:
    path: str
    line: int | None = None
    text: str = ""

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else self.path
        return f"{where}: {self.text}" if self.text else where


@dataclass
class Item:
    id: str
    section: str
    title: str
    points: float
    max: float
    evidence: list[Evidence] = field(default_factory=list)
    advice: str = ""  # what to add, when points < max
    applies: bool = True  # False: not applicable (no notebooks, no code), left out of the score

    @property
    def status(self) -> str:
        if not self.applies:
            return "n/a"
        return "pass" if self.points >= self.max else "partial" if self.points > 0 else "missing"


SECTIONS = {
    "deps": "Dependencies",
    "run": "Instructions",
    "code": "Training and evaluation code",
    "artifacts": "Models and data",
    "randomness": "Randomness",
    "compute": "Compute",
    "legal": "Licence and citation",
    "notebooks": "Notebooks",
}

CODE = (".py", ".r", ".jl", ".m", ".lua", ".scala", ".cpp", ".cu", ".c", ".rs", ".go", ".java", ".ipynb", ".sh")
DOCS = (".md", ".markdown", ".rst", ".txt")


# --- reading helpers -------------------------------------------------------------------------------------------------


def lines_matching(text: str, pattern: re.Pattern[str], width: int = 90) -> list[tuple[int, str]]:
    """(line number, the line, or the part of a long line around the match).

    >>> s = lines_matching("x" * 200 + " trained on 8 A100 GPUs " + "y" * 200, re.compile(r"A100"))[0][1]
    >>> "trained on 8 A100 GPUs" in s, s[0], s[-1], len(s) <= 92
    (True, '…', '…', True)
    """
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        m = pattern.search(line)
        if not m:
            continue
        s = line.strip()
        if len(s) > width:
            m = pattern.search(s)
            mid = (m.start() + m.end()) // 2 if m else 0
            start = max(0, min(mid - width // 2, len(s) - width))
            s = ("…" if start else "") + s[start : start + width].strip() + ("…" if start + width < len(s) else "")
        out.append((i, s))
    return out


def code_blocks(text: str) -> list[tuple[int, str]]:
    """The lines inside a README's code blocks (Markdown fences, indented Markdown blocks after a blank line, and
    reStructuredText `::` blocks), with their line numbers.

    >>> code_blocks("Run:\\n\\n```bash\\n$ python train.py\\n```\\n"), code_blocks("Then\\n\\n    python demo.py\\n")
    ([(4, 'python train.py')], [(3, 'python demo.py')])
    """
    out: list[tuple[int, str]] = []
    lines = text.splitlines()
    fence: str | None = None
    rst_block = False
    indented = False  # a Markdown code block indented four spaces, after a blank line
    previous = ""
    for i, line in enumerate(lines, 1):
        s = line.strip()
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            fence = None if fence and m.group(1)[0] == fence[0] else (m.group(1) if fence is None else fence)
            previous = line
            continue
        if fence:
            out.append((i, _unprompt(s)))
            continue
        if s.endswith("::") or re.match(r"\.\. (code-block|code|sourcecode)::", s):
            rst_block = True
            previous = line
            continue
        code_indent = line.startswith(("    ", "\t")) and s
        if code_indent and (indented or rst_block or not previous.strip()):
            indented = True
            out.append((i, _unprompt(s)))
        elif s:
            indented = rst_block = False
        previous = line
    return [(i, s) for i, s in out if s]


def _unprompt(s: str) -> str:
    return re.sub(r"^(\$|>|%|#\s*\$)\s+", "", s)


RUNNERS = re.compile(
    r"^(?:(?:[A-Z_][A-Z0-9_]*=\S*\s+)*)"  # VAR=value prefixes (CUDA_VISIBLE_DEVICES=0)
    r"(?:(?:uv|poetry|pdm|pipenv|conda)\s+run\s+(?:-n\s+\S+\s+)?)?"
    r"(python3?|torchrun|accelerate\s+launch|deepspeed|bash|sh|zsh|srun|sbatch|make|jupyter|julia|Rscript|\./)\b"
)
INSTALL = re.compile(
    r"\b(pip3?\s+install|python3?\s+-m\s+pip\s+install|conda\s+(env\s+create|create|install)|mamba\s+(env\s+create|create|install)"
    r"|uv\s+(sync|pip\s+install)|poetry\s+install|pdm\s+install|pipenv\s+install|docker\s+(build|pull|run)|setup\.py\s+(install|develop)"
    r"|apptainer\s+(build|pull)|singularity\s+(build|pull)|R\s+-e|install\.packages)"
)


def readme_text(repo: Repo) -> tuple[str | None, str]:
    path = repo.readme()
    return path, (repo.text(path) or "") if path else ""


def docs(repo: Repo) -> list[str]:
    """The README and other docs: top-level text files and docs/ (where setup and results are often written)."""
    readme = repo.readme()
    rest = [f for f in repo.files if f.lower().endswith(DOCS) and f != readme and (f.count("/") == 0 or f.lower().startswith(("docs/", "doc/")))
            and not f.lower().endswith(("requirements.txt", "license.txt", "licence.txt"))]  # fmt: skip
    return ([readme] if readme else []) + rest[:40]


def code_files(repo: Repo) -> list[str]:
    return [f for f in repo.files if f.lower().endswith(CODE)]


# --- dependencies ----------------------------------------------------------------------------------------------------

LOCKS = ("uv.lock", "poetry.lock", "pipfile.lock", "pdm.lock", "conda-lock.yml", "conda-lock.yaml", "renv.lock", "manifest.toml",
         "pixi.lock", "requirements.lock")  # fmt: skip
CONTAINERS = ("dockerfile", "containerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yaml", ".def", "flake.nix",
              ".devcontainer/devcontainer.json", "devcontainer.json")  # fmt: skip


def _dep_files(repo: Repo) -> list[str]:
    out = []
    for f in repo.files:
        name = PurePosixPath(f).name.lower()
        depth = f.count("/")
        if depth > 2:
            continue
        if (re.fullmatch(r"requirements[\w.-]*\.(txt|in)", name) or re.fullmatch(r"(environment|env|conda)[\w.-]*\.ya?ml", name)
                or name in ("setup.py", "setup.cfg", "pyproject.toml", "pipfile", "description", "project.toml", "install.r")
                or name in LOCKS):  # fmt: skip
            out.append(f)
    return out


def _requirement_lines(text: str, kind: str) -> list[tuple[int, str]]:
    """(line, requirement) for the packages a dependency file names."""
    reqs: list[tuple[int, str]] = []
    if kind == "requirements":
        for i, line in enumerate(text.splitlines(), 1):
            s = line.split(" #")[0].strip()
            if s and not s.startswith(("#", "-", "--")):
                reqs.append((i, s))
    elif kind == "conda":
        in_deps = False
        for i, line in enumerate(text.splitlines(), 1):
            if re.match(r"^dependencies\s*:", line):
                in_deps = True
                continue
            if in_deps and re.match(r"^\S", line):
                in_deps = False
            m = re.match(r"^\s+-\s+([^:#\s][^#]*)$", line) if in_deps else None
            if m and m.group(1).strip() not in ("pip",) and not m.group(1).strip().endswith(":"):
                reqs.append((i, m.group(1).strip()))
    elif kind == "pyproject":
        m = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)\]", text)
        if m:
            start = text[: m.start(1)].count("\n") + 1
            for j, line in enumerate(m.group(1).splitlines()):
                for req in re.findall(r"[\"']([^\"']+)[\"']", line):
                    reqs.append((start + j, req))
        m = re.search(r"(?ms)^\[tool\.poetry\.dependencies\]\s*\n(.*?)(?=^\[|\Z)", text)
        if m:
            start = text[: m.start(1)].count("\n") + 1
            for j, line in enumerate(m.group(1).splitlines()):
                if "=" in line and not line.strip().startswith(("#", "python")):
                    reqs.append((start + j, line.strip()))
    elif kind == "setup":
        m = re.search(r"install_requires\s*=\s*\[(.*?)\]", text, re.S)
        if m:
            start = text[: m.start(1)].count("\n") + 1
            for j, line in enumerate(m.group(1).splitlines()):
                for req in re.findall(r"[\"']([^\"']+)[\"']", line):
                    reqs.append((start + j, req))
    return reqs


def pinned(req: str) -> bool:
    """A requirement fixed to one version: `torch==2.1.0`, `numpy=1.26` (conda), `pkg @ git+...@<commit>`, a poetry
    `"2.1.0"` without a range.

    >>> [pinned(r) for r in ("torch==2.1.0", "numpy>=1.20", "scipy", "python=3.10", "x @ git+https://g/x@3f2a1bc9", 'torch = "2.1.0"')]
    [True, False, False, True, True, True]
    """
    r = req.strip()
    if "==" in r or "===" in r:
        return True
    if re.search(r"@\s*git\+\S+@[0-9a-f]{7,40}\b", r):
        return True
    if re.fullmatch(r"[\w.\-\[\]]+\s*=\s*[\w.*]+(=\w+)?", r) and not re.search(r"[<>~^!]", r):  # conda: numpy=1.26 or numpy=1.26=py310
        return True
    m = re.fullmatch(r"[\w.\-]+\s*=\s*[\"']([^\"']+)[\"']", r)  # poetry: torch = "2.1.0"
    if m:
        return bool(re.fullmatch(r"=?=?\d[\w.]*", m.group(1)))
    return False


def _readme_packages(repo: Repo) -> list[tuple[str, int, str]]:
    """Packages named in the README's `pip install` / `conda install` commands (not `-r file`, `-e .` or URLs)."""
    path, text = readme_text(repo)
    out = []
    for i, cmd in code_blocks(text) if path else []:
        m = re.search(r"\b(?:pip3?|conda|mamba|uv\s+pip)\s+install\s+(.*)", cmd)
        if not m:
            continue
        for tok in m.group(1).split():
            tok = tok.strip("\"'")
            if tok.startswith("-") or tok in (".", "..") or "/" in tok or tok.endswith((".txt", ".yml", ".yaml")):
                continue
            out.append((path or "", i, tok))
    return out


def check_dependencies(repo: Repo) -> list[Item]:
    files = _dep_files(repo)
    items = []
    ev = [Evidence(f) for f in files[:8]]
    named = _readme_packages(repo) if not files else []
    if files:
        items.append(Item("deps.file", "deps", "a file listing the dependencies", 7, 7, ev))
    elif named:
        items.append(Item("deps.file", "deps", f"a file listing the dependencies ({len(named)} packages named only in the README)", 3, 7,
                          [Evidence(named[0][0], named[0][1], " ".join(t for _, _, t in named)[:100])],
                          "put the packages in requirements.txt or environment.yml, so they can be installed and checked as one list"))  # fmt: skip
    else:
        items.append(Item("deps.file", "deps", "a file listing the dependencies", 0, 7, [],
                          "add requirements.txt, environment.yml or pyproject.toml with every package the code imports"))  # fmt: skip
    locks = [f for f in files if PurePosixPath(f).name.lower() in LOCKS]
    total = fixed = 0
    loose: list[Evidence] = []
    for p, line, req in named:
        total += 1
        if pinned(req):
            fixed += 1
        elif len(loose) < 5:
            loose.append(Evidence(p, line, req))
    for f in files:
        name = PurePosixPath(f).name.lower()
        kind = ("requirements" if name.startswith("requirements") else "conda" if name.endswith((".yml", ".yaml")) and name not in LOCKS
                else "pyproject" if name == "pyproject.toml" else "setup" if name == "setup.py" else "")  # fmt: skip
        if not kind:
            continue
        for line, req in _requirement_lines(repo.text(f) or "", kind):
            if re.match(r"^python\b", req) and kind != "conda":
                continue
            total += 1
            if pinned(req):
                fixed += 1
            elif len(loose) < 5:
                loose.append(Evidence(f, line, req))
    if locks:
        items.append(Item("deps.pinned", "deps", "versions pinned", 7, 7, [Evidence(f, None, "a lock file") for f in locks[:3]]))
    elif total:
        share = fixed / total
        pts = 7 if share >= 0.8 else 4 if share >= 0.3 else 1 if fixed else 0
        items.append(Item("deps.pinned", "deps", f"versions pinned ({fixed} of {total} requirements)", pts, 7, loose,
                          "" if pts == 7 else "pin each package to the version you ran (pip freeze, conda env export, or a lock file)"))  # fmt: skip
    else:
        items.append(
            Item(
                "deps.pinned", "deps", "versions pinned", 0, 7, [], "pin each package to the version you ran (a lock file, or == in requirements.txt)"
            )
        )
    py = _python_version(repo, files)
    items.append(Item("deps.python", "deps", "the Python (or language) version stated", 3 if py else 0, 3, py[:2],
                      "" if py else "say which Python version it ran on (requires-python, python= in environment.yml, or the README)"))  # fmt: skip
    containers = [f for f in repo.files if PurePosixPath(f).name.lower() in CONTAINERS or f.lower().endswith(CONTAINERS)]
    envs = [f for f in files if PurePosixPath(f).name.lower().endswith((".yml", ".yaml")) and PurePosixPath(f).name.lower() not in LOCKS]
    has = containers or envs
    items.append(Item("deps.environment", "deps", "a container or environment file", 3 if has else 0, 3, [Evidence(f) for f in (containers + envs)[:3]],
                      "" if has else "add a Dockerfile or a conda environment.yml so the whole environment, not only the Python packages, can be rebuilt"))  # fmt: skip
    return items


def _python_version(repo: Repo, dep_files: list[str]) -> list[Evidence]:
    out = []
    pattern = re.compile(r"requires-python\s*=|python_requires\s*=|^\s*-\s*python\s*[=<>]=?\s*\d|^python\s*=\s*[\"'][\^~>=<]*\d|python_version")
    for f in dep_files + [f for f in repo.files if PurePosixPath(f).name.lower() in (".python-version", "runtime.txt", "dockerfile")]:
        text = repo.text(f) or ""
        if PurePosixPath(f).name.lower() in (".python-version", "runtime.txt") and text.strip():
            out.append(Evidence(f, 1, text.strip().splitlines()[0][:60]))
            continue
        if PurePosixPath(f).name.lower() == "dockerfile":
            for i, s in lines_matching(text, re.compile(r"^\s*FROM\s+\S*(python|pytorch|tensorflow|cuda|nvidia|conda)\S*:\S*\d", re.I)):
                out.append(Evidence(f, i, s[:80]))
            continue
        for i, s in lines_matching(text, pattern):
            out.append(Evidence(f, i, s[:80]))
    path, text = readme_text(repo)
    if path:
        for i, s in lines_matching(text, re.compile(r"\b(Python|python)\s*(version\s*)?(>=|=|==|≥)?\s*3\.\d+|\bpy3\d{1,2}\b")):
            out.append(Evidence(path, i, s[:80]))
    return out


# --- instructions ----------------------------------------------------------------------------------------------------


def _numeric_table(text: str) -> list[tuple[int, str]]:
    """Rows of results tables: Markdown pipe tables (after a |---| line) and HTML tables, with 2+ numbers in a row."""
    out = []
    lines = text.splitlines()
    in_table = False
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if re.fullmatch(r"\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?", s):
            in_table = True
            continue
        if in_table and "|" in s:
            cells = [c.strip() for c in s.strip("|").split("|")]
            if sum(bool(re.fullmatch(r"[~±+\-]?\*{0,2}\d+(\.\d+)?\*{0,2}\s*(%|±\s*\d+(\.\d+)?)?", c)) for c in cells) >= 2:
                out.append((i, s[:100]))
        else:
            in_table = False
    for m in re.finditer(r"<table\b.*?</table>", text, re.S | re.I):
        if len(re.findall(r"<td[^>]*>\s*[\d.]+\s*%?\s*</td>", m.group(0), re.I)) >= 2:
            out.append((text[: m.start()].count("\n") + 1, "an HTML table of results"))
    return out


def _scripts_in(command: str) -> list[tuple[str, bool]]:
    """The repository files a command runs, and whether each is a module (`-m`): `python train.py`,
    `bash scripts/run.sh`, `python -m pkg.eval`.

    >>> _scripts_in("CUDA_VISIBLE_DEVICES=0 python tools/train.py --cfg a.yaml"), _scripts_in("python -m src.eval --x 1")
    ([('tools/train.py', False)], [('src/eval', True)])
    """
    out = []
    m = re.search(r"\s-m\s+([\w.]+)", command)
    if m:
        out.append((m.group(1).replace(".", "/"), True))
    for tok in command.split():
        tok = tok.strip("\"'`;,")
        if re.fullmatch(r"(\./)?[\w./\-]+\.(py|sh|ipynb|R|jl)", tok) and not tok.startswith(("http", "/")):
            out.append((tok.removeprefix("./"), False))
            break  # the script run; later .py arguments are its inputs
    return out


def check_instructions(repo: Repo) -> list[Item]:
    path, text = readme_text(repo)
    items = []
    if not path:
        items.append(Item("run.readme", "run", "a README", 0, 3, [], "add a README that says how to install, run, and reproduce the paper's results"))
    else:
        words = len(text.split())
        items.append(Item("run.readme", "run", f"a README ({words} words)", 3 if words >= 150 else 1, 3, [Evidence(path)],
                          "" if words >= 150 else "the README is too short to say how to reproduce the results"))  # fmt: skip
    blocks = [(path or "", i, s) for i, s in code_blocks(text)] if path else []
    for d in docs(repo)[1:]:
        blocks += [(d, i, s) for i, s in code_blocks(repo.text(d) or "")]
    installs = [Evidence(p, i, s[:100]) for p, i, s in blocks if INSTALL.search(s)]
    items.append(Item("run.install", "run", "install commands", 5 if installs else 0, 5, installs[:3],
                      "" if installs else "give the commands that install the environment (pip install -r requirements.txt, conda env create -f ...)"))  # fmt: skip
    runs = [(p, i, s) for p, i, s in blocks if RUNNERS.search(s) and not INSTALL.search(s)]
    missing: list[Evidence] = []
    found: list[Evidence] = []
    for p, i, s in runs:
        for script, module in _scripts_in(s):
            ok = repo.exists(script) or (module and (repo.exists(script + ".py") or repo.exists(script + "/__main__.py")))
            if not ok and module and not repo.exists(script.split("/")[0]) and not repo.exists(script.split("/")[0] + ".py"):
                continue  # python -m torch.distributed.run: a module of an installed package, not of the repository
            (found if ok else missing).append(Evidence(p, i, s[:100] if ok else f"runs {script}, which is not in the repository"))
    if runs and not missing:
        pts, advice = 6, ""
    elif runs:
        pts, advice = 3, "the README runs files that are not in the repository: add them or fix the commands"
    else:
        pts, advice = 0, "give the exact commands that train, evaluate and produce each result, in code blocks"
    items.append(Item("run.commands", "run", f"commands to run ({len(runs)} in code blocks)", pts, 6,
                      (missing + found)[:5] or [Evidence(p, i, s[:100]) for p, i, s in runs[:3]], advice))  # fmt: skip
    rows: list[Evidence] = []
    for d in docs(repo):
        rows += [Evidence(d, i, s) for i, s in _numeric_table(repo.text(d) or "")]
    items.append(Item("run.results", "run", "a table of results", 6 if rows else 0, 6, rows[:2],
                      "" if rows else "put the paper's main results in a table in the README, next to the command that produces them"))  # fmt: skip
    return items


# --- training and evaluation code ------------------------------------------------------------------------------------

TRAIN = re.compile(
    r"(^|[_\-/])(train|training|finetune|finetuning|fine_tune|fine-tune|pretrain|pretraining|pre_train|run_train|trainer|main_train)([_\-.]|$)", re.I
)
EVAL = re.compile(
    r"(^|[_\-/])(eval|evaluate|evaluation|inference|infer|predict|sample|sampling|generate|benchmark|test|demo|reproduce)([_\-.]|$)", re.I
)


def _is_unit_test(repo: Repo, f: str) -> bool:
    """A unit test, not an experiment: in a tests/ folder, or named test_x.py and written for pytest or unittest
    (tools/test_net.py, which evaluates a model, is not one)."""
    parts = f.lower().split("/")
    if any(p in ("tests", "unittests") for p in parts[:-1]):
        return True
    if parts[-1].startswith("test_") or parts[-1].endswith("_test.py"):
        return bool(re.search(r"^\s*(import pytest|import unittest|from unittest|def test_\w*\()", repo.text(f) or "", re.M))
    return False


def check_code(repo: Repo) -> list[Item]:
    code = [f for f in code_files(repo) if not _is_unit_test(repo, f)]
    if not code:
        return [Item("code.train", "code", "training code", 0, 6, [], "the repository has no code", applies=True),
                Item("code.eval", "code", "evaluation code", 0, 6, [], "the repository has no code"),
                Item("code.config", "code", "hyperparameters in configs or arguments", 0, 3, [], "")]  # fmt: skip
    stems = {f: PurePosixPath(f).stem for f in code}
    train = [Evidence(f) for f in code if TRAIN.search(stems[f]) or (TRAIN.search(f) and f.lower().endswith((".sh", ".py")))]
    trained = {e.path for e in train}
    evals = [Evidence(f) for f in code if EVAL.search(stems[f]) and f not in trained]
    path, text = readme_text(repo)
    if path:  # a README command that trains or evaluates (python run.py train ..., run_classifier.py --do_train)
        commands = [(i, s) for i, s in code_blocks(text) if RUNNERS.search(s)]
        if not train:
            train = [Evidence(path, i, s[:90]) for i, s in commands if re.search(r"train|\bfit\b|finetune", s, re.I)][:2]
        if not evals:
            evals = [Evidence(path, i, s[:90]) for i, s in commands if re.search(r"eval|\btest\b|infer|predict|sample|generate", s, re.I)][:2]
    items = [
        Item("code.train", "code", "training code", 6 if train else 0, 6, train[:3],
             "" if train else "include the code that trains the models, so the paper's results can be reproduced from scratch"),
        Item("code.eval", "code", "evaluation code", 6 if evals else 0, 6, evals[:3],
             "" if evals else "include the exact code that evaluates the models and computes the reported numbers"),
    ]  # fmt: skip
    configs = [
        f for f in repo.files if re.search(r"(^|/)(configs?|conf|hparams|hyperparameters|experiments)/.+\.(ya?ml|json|toml|py|gin|cfg)$", f, re.I)
    ]
    args: list[Evidence] = []
    if not configs:
        pattern = re.compile(r"add_argument\(.*default\s*=|@hydra\.main|flags\.DEFINE_|ml_collections|OmegaConf\.|HfArgumentParser|tyro\.cli")
        for f in [c for c in code if c.endswith(".py")][:400]:
            hits = lines_matching(repo.text(f) or "", pattern)
            if hits:
                args.append(Evidence(f, hits[0][0], hits[0][1][:80]))
                if len(args) >= 2:
                    break
    ev = [Evidence(f) for f in configs[:3]] or args
    items.append(Item("code.config", "code", "hyperparameters in configs or arguments", 3 if ev else 0, 3, ev,
                      "" if ev else "put the hyperparameters of each experiment in config files (or command-line defaults) rather than in the code"))  # fmt: skip
    return items


# --- models and data -------------------------------------------------------------------------------------------------

URL = re.compile(r"https?://[^\s)\]>\"'`]+")
MODEL_HOSTS = re.compile(
    r"huggingface\.co/(?!datasets/|docs/|spaces/|blog/|papers/|join|login)[\w\-]+/[\w.\-]+|drive\.google\.com|docs\.google\.com/uc|dropbox\.com|"
    r"zenodo\.org/(record|records|doi)|figshare\.com|1drv\.ms|onedrive\.live\.com|sharepoint\.com|pan\.baidu\.com|"
    r"github\.com/[\w\-.]+/[\w\-.]+/releases|download\.pytorch\.org/models|storage\.googleapis\.com|s3[\w.\-]*\.amazonaws\.com|"
    r"dl\.fbaipublicfiles\.com|openaipublic\.|modelscope\.cn|\.(pth|pt|ckpt|safetensors|h5|onnx|pkl|npz|bin|tar|zip)(\?|$)"
)
DATA_HOSTS = re.compile(
    r"huggingface\.co/datasets/|kaggle\.com/(datasets|c|competitions)|zenodo\.org|figshare\.com|image-net\.org|cocodataset\.org|"
    r"archive\.ics\.uci\.edu|paperswithcode\.com/dataset|tensorflow\.org/datasets|physionet\.org|openml\.org|dataverse|osf\.io|"
    r"data\.|/datasets?/"
)
DATA_WORDS = re.compile(r"\b(data|dataset|datasets|corpus|corpora|benchmark|download|downloaded|split|splits)\b", re.I)
DATA_LOADERS = re.compile(
    r"torchvision\.datasets\.|datasets\.\w+\(\s*root|load_dataset\(|tfds\.load\(|tensorflow_datasets|keras\.datasets\.|sklearn\.datasets\."
)
HUB_ID = re.compile(r"from_pretrained\(\s*[\"']([\w\-]+/[\w.\-]+)[\"']|hf_hub_download\(|snapshot_download\(|torch\.hub\.load\(")


def links(repo: Repo) -> list[tuple[str, int, str]]:
    out = []
    for d in docs(repo):
        for i, line in enumerate((repo.text(d) or "").splitlines(), 1):
            out += [(d, i, u.rstrip(".,;:")) for u in URL.findall(line)]
    return out


def check_artifacts(repo: Repo) -> list[Item]:
    found = links(repo)
    # a link to a model host or a weights file (a Drive or Zenodo link may hold data too: it counts for models)
    models = [Evidence(p, i, u[:100]) for p, i, u in found if MODEL_HOSTS.search(u) and "huggingface.co/datasets/" not in u]
    if not models:
        for f in [c for c in code_files(repo) if c.endswith((".py", ".ipynb"))][:400]:
            hits = lines_matching(repo.text(f) or "", HUB_ID)
            if hits:
                models.append(Evidence(f, hits[0][0], hits[0][1][:80]))
                if len(models) >= 2:
                    break
    if not models:
        for f in [x for x in code_files(repo) if PurePosixPath(x).stem.lower().startswith(("download", "get_model", "fetch"))][:2]:
            models.append(Evidence(f, None, "a download script"))

    def about_data(p: str, i: int) -> bool:  # a link on a line that speaks of data, or just after one
        lines = (repo.text(p) or "").splitlines()
        return 0 < i <= len(lines) and bool(DATA_WORDS.search(" ".join(lines[max(0, i - 2) : i])))

    data = [Evidence(p, i, u[:100]) for p, i, u in found if DATA_HOSTS.search(u) or (not MODEL_HOSTS.search(u) and about_data(p, i))]
    scripts = [f for f in repo.files if re.search(r"(^|/)(download|get|fetch|prepare|preprocess|make)_?(data|dataset)s?[\w\-]*\.(sh|py)$", f, re.I)]
    data += [Evidence(f, None, "a data script") for f in scripts[:2]]
    if not data:  # a library that downloads the dataset itself
        for f in [c for c in code_files(repo) if c.endswith((".py", ".ipynb"))][:400]:
            hits = lines_matching(repo.text(f) or "", DATA_LOADERS)
            if hits:
                data.append(Evidence(f, hits[0][0], hits[0][1][:80]))
                break
    path, text = readme_text(repo)
    if not data and path:
        heads = lines_matching(text, re.compile(r"^(#+|[=\-]{3,}$)?\s*.*\b(data|dataset|datasets|data preparation|preparing data)\b", re.I))
        heads = [(i, s) for i, s in heads if s.startswith("#") or re.match(r"^\*\*.*\*\*$", s)]
        data += [Evidence(path, i, s[:80]) for i, s in heads[:2]]
    return [
        Item("artifacts.models", "artifacts", "trained models to download", 8 if models else 0, 8, models[:3],
             "" if models else "release the trained models (a Hugging Face, Zenodo or GitHub release link) so the results can be checked without retraining"),
        Item("artifacts.data", "artifacts", "where the data comes from", 7 if data else 0, 7, data[:3],
             "" if data else "say where to get each dataset and how to prepare it (links, a download script, the preprocessing steps)"),
    ]  # fmt: skip


# --- randomness ------------------------------------------------------------------------------------------------------

SEED = re.compile(
    r"\b(torch\.(cuda\.)?manual_seed(_all)?|np\.random\.seed|numpy\.random\.seed|(?<![\w.])random\.seed|tf\.random\.set_seed|tf\.set_random_seed|"
    r"set_random_seed|seed_everything|set_seed|fix_seed|setup_seed|init_seeds|jax\.random\.(PRNGKey|key)|np\.random\.default_rng\(\s*[\w.]+\s*\)|"
    r"np\.random\.RandomState\(\s*[\w.]+\s*\)|torch\.Generator\(\)\.manual_seed|set\.seed\(|Random\.seed!\()"
)
DETERMINISM = re.compile(
    r"cudnn\.deterministic\s*=\s*True|use_deterministic_algorithms\(\s*True|CUBLAS_WORKSPACE_CONFIG|cudnn\.benchmark\s*=\s*False|"
    r"enable_op_determinism|TF_DETERMINISTIC_OPS|PYTHONHASHSEED|deterministic\s*=\s*True|xla_gpu_deterministic"
)


def check_randomness(repo: Repo) -> list[Item]:
    code = [f for f in code_files(repo) if f.lower().endswith((".py", ".ipynb", ".r", ".jl", ".sh")) and not _is_unit_test(repo, f)]
    if not code:
        return [Item("randomness.seed", "randomness", "random seeds set", 0, 6, [], "", applies=False),
                Item("randomness.deterministic", "randomness", "deterministic settings", 0, 4, [], "", applies=False)]  # fmt: skip
    seeds: list[Evidence] = []
    det: list[Evidence] = []
    for f in code[:2000]:
        text = repo.text(f) or ""
        if len(seeds) < 3:
            seeds += [Evidence(f, i, s[:80]) for i, s in lines_matching(text, SEED)[:1]]
        if len(det) < 3:
            det += [Evidence(f, i, s[:80]) for i, s in lines_matching(text, DETERMINISM)[:1]]
        if len(seeds) >= 3 and len(det) >= 3:
            break
    return [
        Item("randomness.seed", "randomness", "random seeds set", 6 if seeds else 0, 6, seeds,
             "" if seeds else "set and report the random seeds (torch.manual_seed, np.random.seed, random.seed), and run more than one"),
        Item("randomness.deterministic", "randomness", "deterministic settings", 4 if det else 0, 4, det,
             "" if det else "where it matters, make GPU kernels deterministic (torch.use_deterministic_algorithms(True), cudnn.deterministic)"),
    ]  # fmt: skip


# --- compute ---------------------------------------------------------------------------------------------------------

HARDWARE = re.compile(r"\b(A100|H100|H200|B200|V100|P100|A6000|A40|A10G?|L40S?|L4|T4|K80|RTX\s?\d{4}|GTX\s?\d{3,4}|TITAN\s?\w+|TPU\s?v?\d*|"
                      r"MI\d{3}X?|Gaudi\d?|\d+\s?x\s?(GPU|GPUs)|\d+\s+GPUs?|GPUs?\s+with\s+\d+\s?GB)\b")  # fmt: skip
EFFORT = re.compile(
    r"\b\d+(\.\d+)?\s?(GPU[- ]?hours?|GPU[- ]?days?|hours?|hrs?|days?|minutes?|mins?)\b|\b\d+\s?GB\b(?!\s*(of\s+)?(disk|storage|space))", re.I
)


def check_compute(repo: Repo) -> list[Item]:
    hw: list[Evidence] = []
    effort: list[Evidence] = []
    for d in docs(repo):
        text = repo.text(d) or ""
        hw += [Evidence(d, i, s[:90]) for i, s in lines_matching(text, HARDWARE)[:2]]
        effort += [Evidence(d, i, s[:90]) for i, s in lines_matching(text, EFFORT)[:2]]
    return [
        Item("compute.hardware", "compute", "the hardware it ran on", 3 if hw else 0, 3, hw[:2],
             "" if hw else "say which GPUs (or TPUs) and how many the experiments used"),
        Item("compute.time", "compute", "how long it takes, or how much memory", 2 if effort else 0, 2, effort[:2],
             "" if effort else "say how long training and evaluation take, and how much GPU memory they need"),
    ]  # fmt: skip


# --- licence and citation --------------------------------------------------------------------------------------------

LICENCES = [
    ("MIT", r"Permission is hereby granted, free of charge"),
    ("Apache-2.0", r"Apache License,?\s+Version 2\.0"),
    ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 3"),
    ("GPL-2.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 2"),
    ("LGPL", r"GNU LESSER GENERAL PUBLIC LICENSE"),
    ("AGPL-3.0", r"GNU AFFERO GENERAL PUBLIC LICENSE"),
    ("MPL-2.0", r"Mozilla Public License,?\s+(Version|v\.?)\s*2\.0"),
    ("BSD-3-Clause", r"Neither the name of .{0,200}? nor the names of"),
    ("BSD-2-Clause", r"Redistribution and use in source and binary forms"),
    ("CC-BY-NC-4.0", r"Attribution-NonCommercial(-ShareAlike)? 4\.0"),
    ("CC-BY-4.0", r"Creative Commons Attribution 4\.0|CC BY 4\.0"),
    ("CC0-1.0", r"CC0 1\.0|Creative Commons Zero"),
    ("Unlicense", r"This is free and unencumbered software"),
    ("CreativeML-OpenRAIL-M", r"CreativeML Open RAIL-M"),
    ("OpenRAIL", r"Open RAIL|OpenRAIL|Responsible AI License"),
    ("CC-BY-NC-SA-4.0", r"CC BY-NC-SA 4\.0"),
    ("CC-BY-SA-4.0", r"Attribution-ShareAlike 4\.0"),
    ("Llama", r"LLAMA \d+(\.\d+)? COMMUNITY LICENSE"),
]


def licence_of(text: str) -> str | None:
    """The licence a LICENSE file's text is, by its wording.

    >>> licence_of("MIT License\\n\\nPermission is hereby granted, free of charge, to any person"), licence_of("All rights reserved.")
    ('MIT', None)
    """
    for name, pattern in LICENCES:
        if re.search(pattern, text, re.I | re.S):
            return name
    return None


def check_legal(repo: Repo) -> list[Item]:
    files = [f for f in repo.files if "/" not in f and re.match(r"(license|licence|copying|unlicense)(\.|$|-)", f.lower())]
    name = None
    for f in files:
        name = licence_of(repo.text(f) or "") or name
    pyproject = repo.text("pyproject.toml") or "" if repo.exists("pyproject.toml") else ""
    declared = re.search(r"(?m)^license\s*=\s*[\"{]?\s*(?:text\s*=\s*)?[\"']?([\w.\-+ ]+)", pyproject)
    if files:
        lic = Item("legal.licence", "legal", f"a licence ({name or 'not recognised'})", 6, 6, [Evidence(files[0], None, name or "")],
                   "" if name else "")  # fmt: skip
        if name and "NC" in name:
            lic.evidence[0].text += " (non-commercial: others may reuse it for research only)"
    elif declared:
        lic = Item("legal.licence", "legal", "a licence", 4, 6, [Evidence("pyproject.toml", None, declared.group(1).strip())],
                   "add the licence's text as a LICENSE file")  # fmt: skip
    else:
        lic = Item("legal.licence", "legal", "a licence", 0, 6, [],
                   "add a LICENSE file: without one, no one may legally reuse or modify the code")  # fmt: skip
    cites = [Evidence(f) for f in repo.files if PurePosixPath(f).name.lower() in ("citation.cff", "citation.bib", "citation")]
    path, text = readme_text(repo)
    if not cites and path:
        cites = [
            Evidence(path, i, s[:60])
            for i, s in lines_matching(text, re.compile(r"@(article|inproceedings|misc|conference|techreport|phdthesis|book)\s*\{", re.I))[:1]
        ]
    return [
        lic,
        Item("legal.citation", "legal", "how to cite it", 4 if cites else 0, 4, cites[:2],
             "" if cites else "add a CITATION.cff, or the paper's BibTeX in the README"),
    ]  # fmt: skip


# --- notebooks -------------------------------------------------------------------------------------------------------


def notebook_state(text: str) -> tuple[int, int, bool]:
    """(code cells, code cells with outputs, run top to bottom): execution counts increasing and none missing.

    >>> cell = lambda n, out: {"cell_type": "code", "execution_count": n, "source": ["x"], "outputs": [{"output_type": "stream"}] if out else []}
    >>> notebook_state(json.dumps({"cells": [cell(1, True), cell(2, False), cell(3, True)]}))
    (3, 2, True)
    >>> notebook_state(json.dumps({"cells": [cell(5, True), cell(2, True)]}))
    (2, 2, False)
    """
    try:
        nb = json.loads(text)
    except (json.JSONDecodeError, RecursionError):
        return 0, 0, False
    cells = nb.get("cells") if isinstance(nb, dict) else None
    if not isinstance(cells, list):
        return 0, 0, False
    code = [c for c in cells if isinstance(c, dict) and c.get("cell_type") == "code" and "".join(c.get("source") or []).strip()]
    with_out = sum(1 for c in code if c.get("outputs"))
    raw = [c.get("execution_count") for c in code]
    counts = [n for n in raw if isinstance(n, int)]
    ordered = bool(raw) and len(counts) == len(raw) and all(b > a for a, b in zip(counts, counts[1:], strict=False))
    return len(code), with_out, ordered


def check_notebooks(repo: Repo) -> list[Item]:
    nbs = [f for f in repo.named(".ipynb")]
    if not nbs:
        return [Item("notebooks.outputs", "notebooks", "notebooks with their outputs", 0, 3, [], "", applies=False),
                Item("notebooks.order", "notebooks", "notebooks run top to bottom", 0, 2, [], "", applies=False)]  # fmt: skip
    shown: list[Evidence] = []
    unrun: list[Evidence] = []
    disordered: list[Evidence] = []
    ordered = 0
    for f in nbs[:200]:
        n, out, in_order = notebook_state(repo.text(f) or "")
        if n == 0:
            continue
        (shown if out else unrun).append(Evidence(f, None, f"{out} of {n} code cells with outputs"))
        if in_order:
            ordered += 1
        else:
            disordered.append(Evidence(f, None, "cells run out of order, or not all run"))
    total = len(shown) + len(unrun)
    if total == 0:
        return [Item("notebooks.outputs", "notebooks", "notebooks with their outputs", 0, 3, [], "", applies=False),
                Item("notebooks.order", "notebooks", "notebooks run top to bottom", 0, 2, [], "", applies=False)]  # fmt: skip
    share = len(shown) / total
    return [
        Item("notebooks.outputs", "notebooks", f"notebooks with their outputs ({len(shown)} of {total})", round(3 * share, 1), 3,
             (unrun + shown)[:3], "" if share == 1 else "save notebooks with their outputs, so readers see the results each one produces"),
        Item("notebooks.order", "notebooks", f"notebooks run top to bottom ({ordered} of {total})", round(2 * ordered / total, 1), 2,
             disordered[:3], "" if ordered == total else "restart the kernel and run all cells before saving, so the outputs come from the code as it is"),
    ]  # fmt: skip


ALL = [check_dependencies, check_instructions, check_code, check_artifacts, check_randomness, check_compute, check_legal, check_notebooks]


def run_checks(repo: Repo) -> list[Item]:
    return [item for check in ALL for item in check(repo)]
