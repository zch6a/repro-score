"""The repository's own promises: the README shows what repro-score prints for the example, and the action is as
documented."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from repro_score import cli

ROOT = Path(__file__).resolve().parent.parent


def test_the_readme_output_is_the_examples(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    assert cli.main(["examples/paper-code"]) == 0
    printed = capsys.readouterr().out.rstrip("\n")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    block = re.search(r"```\n(repro-score: paper-code: .*?)\n```", readme, re.S)
    assert block and block.group(1) == printed, "run: repro-score examples/paper-code, and paste into the README"


def test_the_action_reads_its_inputs_from_the_environment() -> None:
    action = (ROOT / "action.yml").read_text(encoding="utf-8")
    run = action.split("run: |", 1)[1]
    assert "${{" not in run  # inputs are environment variables in the script, never pasted into it
    for name in ("path", "min-score", "badge"):
        assert re.search(rf"^  {name}:", action, re.M) and f"inputs.{name}" in action
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "uses: zch6a/repro-score@v0" in readme and "min-score:" in readme


def test_the_package_is_typed_and_has_no_dependencies() -> None:
    assert (ROOT / "src" / "repro_score" / "py.typed").is_file()
    assert "dependencies = []" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
