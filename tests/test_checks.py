"""Each check on made-up repositories (in memory: Repo.of), the way a real one would be read."""

from __future__ import annotations

import json

import pytest

from repro_score.checks import (
    check_artifacts,
    check_code,
    check_compute,
    check_dependencies,
    check_instructions,
    check_legal,
    check_notebooks,
    check_randomness,
    pinned,
    run_checks,
)
from repro_score.repo import Repo
from repro_score.report import Report

MIT = "MIT License\n\nCopyright (c) 2024 A. Author\n\nPermission is hereby granted, free of charge, to any person obtaining a copy"


def items(check, files: dict[str, str]) -> dict:  # noqa: ANN001
    return {i.id: i for i in check(Repo.of(files))}


def test_dependencies_pinned_loose_and_locked() -> None:
    got = items(check_dependencies, {"requirements.txt": "torch==2.1.0\nnumpy==1.26.4\nscipy>=1.10\n# a comment\n-r extra.txt\n"})
    assert got["deps.file"].points == 7
    assert got["deps.pinned"].points == 4 and "2 of 3" in got["deps.pinned"].title
    assert str(got["deps.pinned"].evidence[0]) == "requirements.txt:3: scipy>=1.10"
    assert got["deps.python"].points == 0 and got["deps.environment"].points == 0
    got = items(check_dependencies, {"pyproject.toml": '[project]\nrequires-python = ">=3.10"\ndependencies = ["torch>=2"]\n', "uv.lock": "x"})
    assert got["deps.pinned"].points == 7 and got["deps.python"].points == 3
    env = "name: x\nchannels:\n  - pytorch\ndependencies:\n  - python=3.10\n  - pytorch=2.1.0\n  - pip:\n    - timm==0.9.2\n"
    got = items(check_dependencies, {"environment.yml": env})
    assert got["deps.pinned"].points == 7 and got["deps.environment"].points == 3 and got["deps.python"].points == 3
    assert "3 of 3" in got["deps.pinned"].title  # python, pytorch, timm; "pip:" is not a package


def test_packages_named_only_in_the_readme_are_partly_credited() -> None:
    got = items(check_dependencies, {"README.md": "Install:\n\n```\npip install torch==2.1 numpy\n```\n"})
    assert got["deps.file"].points == 3 and "2 packages named only in the README" in got["deps.file"].title
    assert got["deps.pinned"].points == 4  # one of two pinned


@pytest.mark.parametrize(("req", "fixed"), [("torch==2.1.0", True), ("numpy>=1.20", False), ("scipy", False), ("numpy=1.26=py310h", True),
                                            ("x @ git+https://github.com/a/x@3f2a1bc9e0", True), ("x @ git+https://github.com/a/x", False),
                                            ('torch = "^2.1"', False), ('torch = "2.1.0"', True)])  # fmt: skip
def test_pinned(req: str, fixed: bool) -> None:
    assert pinned(req) is fixed


README = (
    """# Method

## Install

```bash
conda env create -f environment.yml
```

## Train and evaluate

```bash
$ python train.py --config configs/base.yaml
CUDA_VISIBLE_DEVICES=0 python -m src.eval --ckpt out/model.pt
bash scripts/missing.sh
```

| Model | Top-1 | Top-5 |
|---|---|---|
| ours | 81.2 | 95.4 |
"""
    + "word " * 150
)


def test_instructions_commands_scripts_and_results() -> None:
    files = {"README.md": README, "train.py": "", "src/eval.py": "", "configs/base.yaml": ""}
    got = items(check_instructions, files)
    assert got["run.readme"].points == 3 and got["run.install"].points == 5
    cmds = got["run.commands"]
    assert cmds.points == 3 and "runs scripts/missing.sh, which is not in the repository" in str(cmds.evidence[0])
    assert got["run.results"].points == 6 and got["run.results"].evidence[0].line == 19
    files["scripts/missing.sh"] = ""
    assert items(check_instructions, files)["run.commands"].points == 6


def test_installed_modules_are_not_taken_for_missing_scripts() -> None:
    got = items(check_instructions, {"README.md": "```\npython -m torch.distributed.run --nproc 8 main.py\n```\n" + "w " * 200, "main.py": ""})
    assert got["run.commands"].points == 6


def test_indented_and_rst_code_blocks() -> None:
    md = "Run it:\n\n    python demo.py\n" + "w " * 160
    assert items(check_instructions, {"README.md": md, "demo.py": ""})["run.commands"].points == 6
    rst = "Train::\n\n    python train.py\n\n" + "w " * 160
    assert items(check_instructions, {"README.rst": rst, "train.py": ""})["run.commands"].points == 6


def test_no_readme() -> None:
    got = items(check_instructions, {"main.py": ""})
    assert got["run.readme"].points == 0 and got["run.commands"].points == 0


def test_training_evaluation_and_configs() -> None:
    got = items(check_code, {"tools/train_net.py": "", "tools/test_net.py": "evaluate(model)\n", "tests/test_model.py": "", "configs/r50.yaml": ""})
    assert got["code.train"].points == 6 and got["code.eval"].evidence[0].path == "tools/test_net.py"  # not the unit test
    assert got["code.config"].points == 3
    got = items(check_code, {"model.py": "", "run.py": "p.add_argument('--lr', type=float, default=3e-4)\n"})
    assert got["code.train"].points == 0 and got["code.eval"].points == 0
    assert got["code.config"].points == 3 and got["code.config"].evidence[0].line == 1


def test_models_and_data() -> None:
    readme = ("Weights: [here](https://huggingface.co/org/model-7b). Data: https://huggingface.co/datasets/org/corpus, "
              "and https://zenodo.org/records/123.\n")  # fmt: skip
    got = items(check_artifacts, {"README.md": readme})
    assert got["artifacts.models"].evidence[0].text == "https://huggingface.co/org/model-7b"
    assert all("datasets" not in e.text for e in got["artifacts.models"].evidence)
    assert got["artifacts.data"].points == 7
    got = items(check_artifacts, {"demo.py": "model = AutoModel.from_pretrained('org/model')\n", "scripts/download_data.sh": ""})
    assert got["artifacts.models"].points == 8 and got["artifacts.data"].evidence[0].path == "scripts/download_data.sh"
    got = items(check_artifacts, {"README.md": "See the paper.\n"})
    assert got["artifacts.models"].points == 0 and got["artifacts.data"].points == 0


def test_randomness() -> None:
    code = "import random\nimport torch\nrandom.seed(0)\ntorch.manual_seed(0)\ntorch.backends.cudnn.deterministic = True\n"
    got = items(check_randomness, {"train.py": code})
    assert got["randomness.seed"].evidence[0].line == 3 and got["randomness.deterministic"].points == 4
    got = items(check_randomness, {"train.py": "x = torch.randn(3)\n", "test_x.py": "import pytest\ntorch.manual_seed(0)\n"})
    assert got["randomness.seed"].points == 0  # a unit test's seed is not the experiments'
    assert not items(check_randomness, {"README.md": "x"})["randomness.seed"].applies


def test_compute() -> None:
    got = items(check_compute, {"README.md": "Training takes about 12 hours on 8 A100 GPUs with 80 GB each.\n"})
    assert got["compute.hardware"].points == 3 and got["compute.time"].points == 2
    got = items(check_compute, {"README.md": "Needs 20 GB of disk space.\n"})
    assert got["compute.hardware"].points == 0 and got["compute.time"].points == 0


def test_licence_and_citation() -> None:
    got = items(check_legal, {"LICENSE": MIT, "CITATION.cff": "cff-version: 1.2.0\n"})
    assert got["legal.licence"].title == "a licence (MIT)" and got["legal.citation"].points == 4
    got = items(check_legal, {"README.md": "```bibtex\n@inproceedings{a2024,\n}\n```\n"})
    assert got["legal.licence"].points == 0 and "no one may legally reuse" in got["legal.licence"].advice
    assert got["legal.citation"].evidence[0].line == 2
    got = items(check_legal, {"LICENSE": "Attribution-NonCommercial 4.0 International"})
    assert "non-commercial" in got["legal.licence"].evidence[0].text


def _nb(*cells: tuple[int | None, bool]) -> str:
    return json.dumps({"cells": [{"cell_type": "code", "execution_count": n, "source": ["x"], "outputs": [{"output_type": "stream"}] if out else []}
                                 for n, out in cells]})  # fmt: skip


def test_notebooks() -> None:
    got = items(
        check_notebooks, {"a.ipynb": _nb((1, True), (2, True)), "b.ipynb": _nb((None, False), (None, False)), "c.ipynb": _nb((3, True), (1, True))}
    )
    assert got["notebooks.outputs"].points == 2 and "2 of 3" in got["notebooks.outputs"].title
    assert got["notebooks.order"].points == round(2 / 3, 1)
    assert not items(check_notebooks, {"a.py": ""})["notebooks.outputs"].applies
    assert not items(check_notebooks, {"broken.ipynb": "{not json"})["notebooks.outputs"].applies


def test_the_score_leaves_out_what_does_not_apply() -> None:
    r = Report("x", run_checks(Repo.of({"README.md": "hello"})))
    assert all(i.applies is False for i in r.items if i.section in ("notebooks", "randomness"))
    out_of = sum(i.max for i in r.items if i.applies)
    assert out_of == 85 and r.score == round(100 * sum(i.points for i in r.items if i.applies) / 85)
