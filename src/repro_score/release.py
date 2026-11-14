r"""repro-score release: do the places that state a release agree?

A release is written down in many places: the package's version (pyproject.toml, setup.py, setup.cfg, package.json,
`__version__`), CITATION.cff (version, date-released, doi), .zenodo.json and codemeta.json, the CHANGELOG's newest
heading, the git tags, a Hugging Face model card's version, and the DOI badges in the README. They drift: a tag
v1.2.0 while CITATION.cff still says 1.1.0, a Zenodo DOI in the README that CITATION.cff does not have. This reads
them all (files only; the tags from .git/refs and .git/packed-refs, without running git) and lists each value with
its file and line, then what disagrees.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .repo import Repo

VERSION = r"v?(\d+(?:\.\d+){1,3}(?:[-.]?(?:a|b|rc|alpha|beta|dev|post)\.?\d*)?)"
DEV = re.compile(r"(?:a|b|rc|alpha|beta|dev|pre)\.?\d*$|\.dev|-dev|dev\d", re.I)
DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>\]\)]+[^\s\"'<>\]\).,;])", re.I)


@dataclass
class Value:
    what: str  # "version", "date", "doi"
    value: str
    file: str
    line: int = 0
    source: str = ""  # which field, e.g. "pyproject [project] version"


@dataclass
class ReleaseReport:
    name: str
    values: list[Value] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def text(self) -> str:
        out = [f"repro-score release: {self.name}"]
        for what in ("version", "date", "doi"):
            vs = [v for v in self.values if v.what == what]
            if vs:
                out.append(f"  {what}:")
                out += [f"    {v.value:24} {v.file}{':' + str(v.line) if v.line else ''}  ({v.source})" for v in vs]
        if not self.values:
            out.append("  no version, release date or DOI found")
        out.append("")
        out += [f"  ✗ {p}" for p in self.problems] or ["  ✓ they agree"]
        out += [f"  · {n}" for n in self.notes]
        return "\n".join(out)

    def json(self) -> dict:
        return {"name": self.name, "ok": self.ok, "values": [v.__dict__ for v in self.values], "problems": self.problems, "notes": self.notes}


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _norm(v: str) -> str:
    """1.2 and 1.2.0 and v1.2.0 are the same version.

    >>> _norm("v1.2"), _norm("1.2.0"), _norm("1.2.0rc1")
    ('1.2', '1.2', '1.2rc1')
    """
    v = v.strip().lstrip("vV")
    m = re.match(r"(\d+(?:\.\d+)*)(.*)", v)
    if not m:
        return v
    nums = m.group(1).split(".")
    while len(nums) > 2 and nums[-1] == "0":
        nums.pop()
    return ".".join(nums) + m.group(2).replace("-", "").replace(".", "")


def _top(repo: Repo, name: str) -> list[str]:
    """Files called `name` at the top or one folder down (a package folder, a model folder)."""
    return [f for f in repo.files if PurePosixPath(f).name.lower() == name.lower() and f.count("/") <= 1]


def versions(repo: Repo) -> list[Value]:
    out: list[Value] = []

    def find(path: str, pattern: str, source: str, flags: int = re.M) -> None:
        text = repo.text(path)
        if not text:
            return
        m = re.search(pattern, text, flags)
        if m:
            out.append(Value("version", m.group("v"), path, _line(text, m.start("v")), source))

    top = [f for f in repo.files if "/" not in f]  # a package's own manifest; a sub-package (benchmark/setup.py) has its own
    for f in [x for x in top if x.lower() == "pyproject.toml"]:
        text = repo.text(f) or ""
        for section in ("project", "tool.poetry"):
            m = re.search(rf"^\[{re.escape(section)}\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
            if m:
                v = re.search(r'^version\s*=\s*["\'](?P<v>[^"\']+)["\']', m.group(1), re.M)
                if v:
                    out.append(Value("version", v.group("v"), f, _line(text, m.start(1) + v.start("v")), f"[{section}] version"))
    for f in [x for x in top if x.lower() == "setup.py"]:
        find(f, r"""\bversion\s*=\s*["'](?P<v>\d[^"']*)["']""", "setup(version=...)")
    for f in [x for x in top if x.lower() == "setup.cfg"]:
        find(f, r"^version\s*=\s*(?P<v>\d\S*)", "[metadata] version")
    for f in [x for x in top if x.lower() == "package.json"]:
        find(f, r'"version"\s*:\s*"(?P<v>\d[^"]*)"', "package.json version")
    for f in repo.files:  # an agent plugin's manifest (Claude Code: .claude-plugin/plugin.json)
        if f.endswith(".claude-plugin/plugin.json") and f.count("/") <= 3:
            find(f, r'"version"\s*:\s*"(?P<v>\d[^"]*)"', "plugin.json version")
    for f in repo.files:
        if (
            PurePosixPath(f).name in ("__init__.py", "version.py", "_version.py", "__about__.py")
            and f.count("/") <= 2
            and not re.match(r"(?:tests?|benchmarks?|examples?|docs?|scripts?|third_party|vendor)/", f)
        ):
            find(f, r"""^__version__\s*(?::\s*str\s*)?=\s*["'](?P<v>\d[^"']*)["']""", "__version__")
    for f in _top(repo, "CITATION.cff"):
        find(f, r"""^version\s*:\s*["']?(?P<v>[^"'\s#]+)""", "CITATION.cff version")
    for f in _top(repo, ".zenodo.json") + _top(repo, "codemeta.json"):
        text = repo.text(f) or ""
        try:
            data = json.loads(text)
        except ValueError:
            continue
        v = data.get("version") or data.get("softwareVersion") if isinstance(data, dict) else None
        if isinstance(v, str) and v:
            out.append(Value("version", v, f, _line(text, text.find(v)), f"{PurePosixPath(f).name} version"))
    for f in _top(repo, "CHANGELOG.md") + _top(repo, "CHANGES.md") + _top(repo, "HISTORY.md") + _top(repo, "CHANGELOG.rst"):
        text = repo.text(f) or ""
        for m in re.finditer(rf"^(?:#+\s*|\s*)\[?{VERSION}\]?(?P<rest>[^\n]*)$", text, re.M):
            if re.search(r"unreleased", m.group("rest"), re.I):
                continue
            out.append(Value("version", m.group(1), f, _line(text, m.start(1)), "CHANGELOG newest"))
            break
    for f in repo.files:  # a Hugging Face model card's version, in its YAML front matter
        if PurePosixPath(f).name.lower() == "readme.md" and f.count("/") <= 1:
            text = repo.text(f) or ""
            fm = re.match(r"---\n(.*?)\n---", text, re.S)
            if fm:
                v = re.search(r"^(?:model_)?version\s*:\s*[\"']?(?P<v>\d[^\"'\s]*)", fm.group(1), re.M)
                if v:
                    out.append(Value("version", v.group("v"), f, _line(text, v.start("v") + 4), "model card version"))
    return out


def tags(repo: Repo) -> list[str]:
    """The version tags, from .git/refs/tags and .git/packed-refs (files only), newest version last."""
    root = repo.root / ".git"
    found: set[str] = set()
    if (root / "refs" / "tags").is_dir():
        found |= {p.name for p in (root / "refs" / "tags").iterdir() if p.is_file()}
    packed = root / "packed-refs"
    if packed.is_file():
        found |= set(re.findall(r"refs/tags/(\S+)", packed.read_text(encoding="utf-8", errors="replace")))
    ver = [t for t in found if re.fullmatch(VERSION, t) and not DEV.search(t)]  # releases, not pre-releases
    if ver:  # the usual shape of the project's tags: an odd old one (v0.03 among v0.0.37) would sort first
        shapes = [len(re.findall(r"\d+", t)) for t in ver]
        common = max(set(shapes), key=shapes.count)
        ver = [t for t in ver if len(re.findall(r"\d+", t)) == common]

    def key(t: str) -> tuple:
        nums = re.findall(r"\d+", t)
        pre = bool(re.search(r"a|b|rc|alpha|beta|dev", t.lstrip("v")))
        return (*[int(n) for n in nums[:3]], 0 if pre else 1)

    return sorted(ver, key=key)


def check(repo: Repo, name: str = "") -> ReleaseReport:
    r = ReleaseReport(name or repo.root.name)
    r.values = versions(repo)
    cff = next(iter(_top(repo, "CITATION.cff")), None)
    cff_text = repo.text(cff) if cff else None
    if cff and cff_text:
        m = re.search(r"""^date-released\s*:\s*["']?(\d{4}-\d{2}-\d{2})""", cff_text, re.M)
        if m:
            r.values.append(Value("date", m.group(1), cff, _line(cff_text, m.start(1)), "CITATION.cff date-released"))
        for m in DOI.finditer(cff_text):
            r.values.append(Value("doi", m.group(1), cff, _line(cff_text, m.start(1)), "CITATION.cff"))
        missing = [k for k in ("cff-version", "message", "title", "authors") if not re.search(rf"^{k}\s*:", cff_text, re.M)]
        if missing:
            r.problems.append(f"{cff}: missing {', '.join(missing)} (required by the Citation File Format)")
    for f in _top(repo, ".zenodo.json"):
        text = repo.text(f) or ""
        for m in DOI.finditer(text):
            r.values.append(Value("doi", m.group(1), f, _line(text, m.start(1)), ".zenodo.json"))
    readme = repo.readme()
    rtext = repo.text(readme) if readme else None
    if readme and rtext:
        for m in re.finditer(r"10\.5281/zenodo\.\d+", rtext):
            r.values.append(Value("doi", m.group(0), readme, _line(rtext, m.start()), "README (Zenodo)"))
    tagged = tags(repo)
    if tagged:
        r.values.append(Value("version", tagged[-1], ".git", 0, f"newest of {len(tagged)} version tag(s)"))
    every = [v for v in r.values if v.what == "version"]
    vs = [v for v in every if not DEV.search(v.value)]
    for v in every:
        if DEV.search(v.value):  # main is usually ahead of the last release: 1.16.0.dev0 after v1.15.0
            r.notes.append(f"{v.value} in {v.file} is a development version: left out of the comparison")
    distinct = {_norm(v.value) for v in vs}
    if len(distinct) > 1:

        def key(x: str) -> list[int]:
            return [int(n) for n in re.findall(r"\d+", x)[:3]]

        newest = max(distinct, key=key)
        files = [v for v in vs if v.file != ".git"]
        tag = next((v for v in vs if v.file == ".git"), None)
        if tag and {_norm(v.value) for v in files} == {newest} and key(_norm(tag.value)) < key(newest):
            # every file says the same, newer than the last tag: a release written down, not tagged yet
            r.notes.append(f"{newest} is in the files but the newest tag is {tag.value}: tag the release when it is out")
        else:
            behind = [v for v in vs if _norm(v.value) != newest]
            shown = next(v.value for v in vs if _norm(v.value) == newest).lstrip("vV")
            r.problems.append(f"the version is not the same everywhere: {shown} in "
                              + ", ".join(f"{v.file}" for v in vs if _norm(v.value) == newest)
                              + "; but " + "; ".join(f"{v.value} in {v.file}{':' + str(v.line) if v.line else ''} ({v.source})" for v in behind))  # fmt: skip
    if not every:
        r.notes.append("no version stated anywhere: tag releases (v1.0.0) and put the version in CITATION.cff")
    if not cff:
        r.notes.append("no CITATION.cff: GitHub's 'Cite this repository' button and Zenodo read it")
    zenodo_readme = [v for v in r.values if v.what == "doi" and v.source == "README (Zenodo)"]
    cff_dois = [v for v in r.values if v.what == "doi" and v.source == "CITATION.cff"]
    if zenodo_readme and cff and not cff_dois:
        r.problems.append(f"the README shows a Zenodo DOI ({readme}:{zenodo_readme[0].line}) but {cff} has no doi")
    dates = [v for v in r.values if v.what == "date"]
    if dates and tagged and vs and any(v.source == "CITATION.cff version" and _norm(v.value) != _norm(tagged[-1]) for v in vs):
        r.notes.append(f"CITATION.cff's date-released ({dates[0].value}) is probably for its own version, not the newest tag {tagged[-1]}")
    return r
