"""repro-score release, on made-up repositories written to a temporary folder (no network)."""

from __future__ import annotations

from pathlib import Path

from repro_score.cli import main
from repro_score.release import check
from repro_score.repo import Repo


def make(tmp: Path, files: dict[str, str], tags: list[str] = ()) -> Path:
    for name, text in files.items():
        p = tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    if tags:
        (tmp / ".git" / "refs" / "tags").mkdir(parents=True)
        for t in tags[:-1]:
            (tmp / ".git" / "refs" / "tags" / t).write_text("0" * 40, encoding="utf-8")
        (tmp / ".git" / "packed-refs").write_text(f"{'0' * 40} refs/tags/{tags[-1]}\n", encoding="utf-8")
    return tmp


CFF = 'cff-version: 1.2.0\nmessage: "cite"\ntitle: "x"\nauthors:\n  - name: A\nversion: "{v}"\ndate-released: "2026-01-02"\ndoi: 10.5281/zenodo.123\n'


def test_all_in_step(tmp_path, capsys):
    make(tmp_path, {
        "pyproject.toml": '[project]\nname = "x"\nversion = "1.2.0"\n\n[tool.ruff]\nversion = "9"\n',
        "src/x/__init__.py": '__version__ = "1.2.0"\n',
        "CITATION.cff": CFF.format(v="1.2.0"),
        "CHANGELOG.md": "# Changelog\n\n## Unreleased\n\n## 1.2.0 - 2026-01-02\n\n## 1.1.0\n",
        "README.md": "[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.123.svg)](https://doi.org/10.5281/zenodo.123)\n",
        "plugin/.claude-plugin/plugin.json": '{"name": "x", "version": "1.2.0"}',
        "benchmark/setup.py": 'setup(version="0.1.0")\n',  # a sub-package's own version: not compared
    }, tags=["v1.0.0", "v1.1.0", "v1.2.0", "v1.3.0rc1"])  # fmt: skip
    r = check(Repo.read(tmp_path))
    assert r.ok, r.problems
    sources = {v.source for v in r.values if v.what == "version"}
    assert {"[project] version", "__version__", "CITATION.cff version", "CHANGELOG newest", "plugin.json version"} <= sources
    assert any(v.source.startswith("newest of 3") and v.value == "v1.2.0" for v in r.values)  # the rc is not a release
    assert main(["release", str(tmp_path)]) == 0
    assert "✓ they agree" in capsys.readouterr().out


def test_drift_is_found_with_its_place(tmp_path, capsys):
    make(tmp_path, {
        "pyproject.toml": '[project]\nversion = "2.0.1"\n',
        "CITATION.cff": CFF.format(v="1.0").replace("doi: 10.5281/zenodo.123\n", ""),
        "README.md": "DOI: https://doi.org/10.5281/zenodo.999\n",
        "plugin/.claude-plugin/plugin.json": '{"version": "1.9.0"}',
    }, tags=["v2.0.0", "v2.0.1"])  # fmt: skip
    r = check(Repo.read(tmp_path))
    joined = " | ".join(r.problems)
    assert "2.0.1 in pyproject.toml, .git; but " in joined and "1.0 in CITATION.cff:6 (CITATION.cff version)" in joined
    assert "1.9.0 in plugin/.claude-plugin/plugin.json:1 (plugin.json version)" in joined
    assert "README shows a Zenodo DOI (README.md:1) but CITATION.cff has no doi" in joined
    assert main(["release", str(tmp_path), "--json"]) == 1
    assert '"ok": false' in capsys.readouterr().out


def test_development_versions_and_untagged_releases(tmp_path):
    make(tmp_path / "a", {"setup.py": 'setup(version="1.16.0.dev0")\n'}, tags=["v1.15.0"])
    r = check(Repo.read(tmp_path / "a"))
    assert r.ok and any("development version" in n for n in r.notes)
    make(tmp_path / "b", {"CHANGELOG.md": "## 0.6.1\n", "pyproject.toml": '[project]\nversion = "0.6.1"\n'}, tags=["v0.5.0", "v0.6.0"])
    r = check(Repo.read(tmp_path / "b"))
    assert r.ok and any("tag the release" in n for n in r.notes)
    make(tmp_path / "c", {"CHANGELOG.md": "## 0.0.37\n"}, tags=["v0.03", "v0.0.35", "v0.0.36", "v0.0.37"])  # an odd old tag
    assert check(Repo.read(tmp_path / "c")).ok


def test_citation_file_basics(tmp_path):
    make(tmp_path, {"CITATION.cff": "title: x\n"})
    r = check(Repo.read(tmp_path))
    assert any("missing cff-version, message, authors" in p for p in r.problems)
    assert any("no version stated anywhere" in n for n in r.notes)
    assert main(["release", str(tmp_path / "nowhere")]) == 2
