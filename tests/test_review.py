"""Regressions for what an independent review of the checks found (polishing round 2): each was reproduced first."""

from __future__ import annotations

import http.client
import io
import json
import tarfile
import time
import urllib.request
from pathlib import Path

import pytest

from repro_score import cli
from repro_score.checks import (
    Evidence,
    Item,
    check_artifacts,
    check_code,
    check_dependencies,
    check_instructions,
    check_legal,
    check_notebooks,
    code_blocks,
    lines_matching,
    notebook_state,
)
from repro_score.links import check_links
from repro_score.remote import RemoteError, download
from repro_score.repo import Repo
from repro_score.report import Report

W = "w " * 160


def items(check, files: dict[str, str]) -> dict:  # noqa: ANN001
    return {i.id: i for i in check(Repo.of(files))}


@pytest.mark.parametrize("source", [[None], 5, {"a": 1}, ["x", 3]])
def test_odd_notebook_sources_do_not_crash(source: object) -> None:
    nb = json.dumps({"cells": [{"cell_type": "code", "source": source, "outputs": []}]})
    notebook_state(nb)  # no exception
    assert notebook_state('{"cells": [], "x": ' + "9" * 6000 + "}") == (0, 0, False)  # too long for int(): not a crash


def test_a_malformed_reply_is_unreachable_not_a_crash() -> None:
    def opener(req: urllib.request.Request, timeout: float) -> int:
        raise http.client.BadStatusLine("GARBAGE")

    assert check_links([("https://x.example/m.pth", "README.md:1")], opener, pause=0)[0].verdict == "unreachable"
    with pytest.raises(RemoteError, match="could not download"):
        download("o", "r", "HEAD", Path("unused"), lambda u, n: (_ for _ in ()).throw(http.client.IncompleteRead(b"")))


def test_large_notebooks_and_utf16_files_are_read(tmp_path: Path) -> None:
    big = {"cells": [{"cell_type": "code", "execution_count": 1, "source": ["x"], "outputs": [{"text": "y" * 2_500_000}]}]}
    (tmp_path / "run.ipynb").write_text(json.dumps(big), encoding="utf-8")
    (tmp_path / "requirements.txt").write_bytes("torch==2.1.0\nnumpy==1.26.4\n".encode("utf-16"))
    repo = Repo.read(tmp_path)
    assert {i.id: i for i in check_notebooks(repo)}["notebooks.outputs"].points == 3
    pinned = {i.id: i for i in check_dependencies(repo)}["deps.pinned"]
    assert pinned.points == 7 and "2 of 2" in pinned.title


def test_pyproject_extras_and_config_only_files() -> None:
    got = items(check_dependencies, {"pyproject.toml": '[project]\ndependencies = ["uvicorn[standard]==0.23", "torch==2.1.0"]\n'})
    assert "2 of 2" in got["deps.pinned"].title
    got = items(check_dependencies, {"pyproject.toml": "[tool.black]\nline-length = 100\n", "setup.cfg": "[flake8]\nmax-line-length = 100\n"})
    assert got["deps.file"].points == 0
    got = items(check_dependencies, {"setup.cfg": "[options]\ninstall_requires =\n    torch==2.1.0\n    numpy\n"})
    assert got["deps.file"].points == 7 and "1 of 2" in got["deps.pinned"].title


def test_markers_and_flag_values_are_not_versions_or_packages() -> None:
    got = items(check_dependencies, {"requirements.txt": 'dataclasses; python_version < "3.7"\n'})
    assert got["deps.python"].points == 0
    got = items(check_dependencies, {"README.md": "```\nconda install -c conda-forge faiss==1.7.4\n```\n"})
    assert "1 packages named only" in got["deps.file"].title and got["deps.pinned"].points == 7


@pytest.mark.parametrize(("readme", "models", "data"), [
    ("Get a token at https://huggingface.co/settings/tokens\n", 0, 0),
    ("The dataset: https://example.edu/files/dataset.zip\n", 0, 7),
    ("Our checkpoints: https://example.edu/files/ckpt.zip\n", 8, 0),
    ("Download Anaconda from https://www.anaconda.com/download\n", 0, 0),
    ("We use the datasets package: https://pypi.org/project/datasets/\n", 0, 0),
    ("| model | link |\n|---|---|\n| ours | **https://x.example/model.pth** |\n", 8, 0),
])  # fmt: skip
def test_model_and_data_links(readme: str, models: int, data: int) -> None:
    got = items(check_artifacts, {"README.md": readme})
    assert (got["artifacts.models"].points, got["artifacts.data"].points) == (models, data)
    for e in got["artifacts.models"].evidence:
        assert not e.text.endswith(("*", "|"))


def test_dependency_lists_are_not_docs() -> None:
    got = items(check_artifacts, {"README.md": "x\n", "requirements-dev.txt": "-f https://data.pyg.org/whl/torch-2.1.0.html\n"})
    assert got["artifacts.data"].points == 0


@pytest.mark.parametrize(("cmd", "script"), [("cd src && python train.py", "src/train.py"), ("(myenv) $ python train.py", "train.py"),
                                             ("cd src\npython train.py", "src/train.py")])  # fmt: skip
def test_commands_after_cd_and_env_prompts(cmd: str, script: str) -> None:
    got = items(check_instructions, {"README.md": f"```\n{cmd}\n```\n" + W, script: ""})
    assert got["run.commands"].points == 6, got["run.commands"].evidence


def test_an_unknown_licence_gets_part() -> None:
    got = items(check_legal, {"LICENSE": "All rights reserved. No redistribution."})
    assert got["legal.licence"].points == 3 and "not a licence it recognises" in got["legal.licence"].advice
    got = items(check_legal, {"pyproject.toml": '[project]\nlicense = {file = "LICENSE.md"}\n'})
    assert got["legal.licence"].points == 0


def test_data_scripts_are_not_training_or_evaluation_code() -> None:
    got = items(check_code, {"data/split_train_val.py": "", "data/generate_splits.py": "", "model.py": ""})
    assert got["code.train"].points == 0 and got["code.eval"].points == 0


def test_long_lines_are_fast() -> None:
    start = time.perf_counter()
    lines_matching(" " * 200_000 + "x", __import__("re").compile(r"^(?:#+|\*\*)[^\n]{0,200}?\b(data)\b"))
    items(check_artifacts, {"README.md": "# x\n" + " " * 200_000 + "\n" + "see https://a.example/data\n" * 2000})
    items(check_code, {"run.py": "p.add_argument(" * 20_000})
    assert time.perf_counter() - start < 5


def test_no_readme_still_reads_the_other_docs() -> None:
    got = items(check_instructions, {"INSTALL.md": "```\npip install -r requirements.txt\n```\n"})
    assert got["run.install"].points == 5


def test_a_fence_shown_inside_a_longer_one() -> None:
    lines = [s for _, s in code_blocks("````md\n```bash\npython a.py\n```\nmore\n````\n")]
    assert "python a.py" in lines and "more" in lines


def test_a_decompression_bomb_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import repro_score.remote as remote

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        info = tarfile.TarInfo("r-1/big.bin")
        info.size = 2_000_000
        t.addfile(info, io.BytesIO(b"\0" * info.size))
    monkeypatch.setattr(remote, "MAX_EXTRACTED", 1_000_000)
    with pytest.raises(RemoteError, match="unpacks to more than"):
        download("o", "r", "HEAD", tmp_path, lambda u, n: buf.getvalue())


def test_every_download_failing_is_status_2(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fail(owner: str, repo: str, ref: str, dest: Path) -> Path:
        raise RemoteError("could not download (404)")

    monkeypatch.setattr(cli, "download", fail)
    monkeypatch.setattr(cli, "DOWNLOAD_PAUSE", 0)
    assert cli.main(["github:a/b", "github:c/d", "--min-score", "50"]) == 2
    capsys.readouterr()


def test_markdown_escapes_a_bar_once() -> None:
    r = Report("x", [Item("legal.licence", "legal", "a licence", 0, 6, [], "a \\| b | c")])
    assert "a \\| b \\| c" in r.markdown()


def test_the_summary_and_json_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "README.md").write_text("# r\n", encoding="utf-8")
    summary, report = tmp_path / "summary.md", tmp_path / "report.json"
    summary.write_text("earlier step\n", encoding="utf-8")
    assert cli.main(["--brief", "--summary-file", str(summary), "--json-file", str(report), "--", str(tmp_path / "r")]) == 0
    assert summary.read_text(encoding="utf-8").startswith("earlier step\n### repro-score: ")
    assert json.loads(report.read_text(encoding="utf-8"))["repository"] == "r"
    capsys.readouterr()


def test_evidence_text_is_shown_whole() -> None:
    assert str(Evidence("a.py", 3, "x")) == "a.py:3: x"


def test_a_venues_repositories_round_4() -> None:
    # NVIDIA's and Inria's research licences are recognised, and said to be non-commercial
    got = items(
        check_legal, {"LICENSE.txt": "Copyright (c) 2021, NVIDIA Corporation. All rights reserved.\n\nNVIDIA Source Code License for StyleGAN3\n"}
    )
    assert got["legal.licence"].points == 6 and "non-commercial" in got["legal.licence"].evidence[0].text
    assert items(check_legal, {"LICENSE.md": "Gaussian-Splatting License\n===\n"})["legal.licence"].title == "a licence (Gaussian-Splatting License)"
    # a run.py that trains with --is_training (thuml) is training code; a helper named grid_sample_gradfix.py is not evaluation code
    got = items(check_code, {"run.py": "parser.add_argument('--is_training', type=int, required=True, default=1)\n",
                             "torch_utils/ops/grid_sample_gradfix.py": "", "gen_images.py": ""})  # fmt: skip
    assert got["code.train"].evidence[0].path == "run.py"
    assert [e.path for e in got["code.eval"].evidence] == ["gen_images.py"]
