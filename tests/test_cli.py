"""The command, its outputs (text, Markdown, JSON, badge) and exit statuses, on a repository written to a temporary folder."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from repro_score import cli
from repro_score.badge import badge, colour


def repo(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("# x\n\n```\npip install -r requirements.txt\npython train.py\n```\n" + "word " * 160, encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("torch==2.3.1\n", encoding="utf-8")
    (tmp_path / "train.py").write_text("import torch\ntorch.manual_seed(0)\n", encoding="utf-8")
    return tmp_path


def test_text_markdown_json_and_badge(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    r = repo(tmp_path / "r")
    assert cli.main([str(r), "--name", "demo"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("repro-score: demo: ") and "✓ random seeds set  6/6" in out and "train.py:2: torch.manual_seed(0)" in out
    assert cli.main([str(r), "--brief"]) == 0
    assert "train.py:2" not in capsys.readouterr().out
    assert cli.main([str(r), "--markdown"]) == 0
    md = capsys.readouterr().out
    assert md.startswith("### repro-score: ") and "| ✓ | Randomness: random seeds set | 6/6 |" in md and "no code was run" in md
    svg = tmp_path / "badge.svg"
    assert cli.main([str(r), "--json", "--badge", str(svg)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["score"] == data["score"] and {s["section"] for s in data["sections"]} >= {"deps", "run", "notebooks"}
    seed = next(i for i in data["items"] if i["id"] == "randomness.seed")
    assert seed["status"] == "pass" and seed["evidence"][0] == {"path": "train.py", "line": 2, "text": "torch.manual_seed(0)"}
    root = ET.fromstring(svg.read_text(encoding="utf-8"))
    assert root.tag.endswith("svg") and f"{data['score']}/100" in svg.read_text(encoding="utf-8")


def test_min_score_and_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    r = repo(tmp_path / "r")
    assert cli.main([str(r), "--min-score", "101"]) == 1
    assert "under the minimum of 101: r (" in capsys.readouterr().err
    assert cli.main([str(r), "--min-score", "0"]) == 0
    assert cli.main([str(tmp_path / "nothing")]) == 2
    assert "not a folder" in capsys.readouterr().err


def test_links_inside_are_not_followed(tmp_path: Path) -> None:
    r = repo(tmp_path / "r")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "LICENSE").write_text("Permission is hereby granted, free of charge", encoding="utf-8")
    try:
        (r / "LICENSE").symlink_to(outside / "LICENSE")
    except OSError:
        pytest.skip("symbolic links are not allowed here")
    from repro_score import score_repo

    assert "LICENSE" not in [i.evidence[0].path for i in score_repo(r).items if i.evidence]


@pytest.mark.parametrize(("score", "fill"), [(95, "#4c1"), (70, "#97ca00"), (55, "#dfb317"), (40, "#fe7d37"), (10, "#e05d44")])
def test_badge_colours(score: int, fill: str) -> None:
    assert colour(score) == fill and fill in badge(score)


def test_lists_folders_and_output_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty_list = tmp_path / "l.txt"
    empty_list.write_text("# nothing yet\n", encoding="utf-8")
    assert cli.main(["--list", str(empty_list)]) == 2
    assert "no repositories listed" in capsys.readouterr().err
    (tmp_path / "empty").mkdir()
    assert cli.main([str(tmp_path / "empty"), "--brief"]) == 0
    assert "(an empty folder: nothing to read)" in capsys.readouterr().out
    r = repo(tmp_path / "r")
    assert cli.main([str(r), "--brief", "--badge", str(tmp_path / "new" / "dir" / "b.svg")]) == 0
    assert (tmp_path / "new" / "dir" / "b.svg").is_file()
    capsys.readouterr()
    assert cli.main(["github:only-owner"]) == 2
    assert "(github:owner/repo)" in capsys.readouterr().err
