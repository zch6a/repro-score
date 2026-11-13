"""Link checking and GitHub downloads, with the network replaced: a fake opener answers the link requests, a fake
fetcher returns a tarball made here."""

from __future__ import annotations

import io
import json
import tarfile
import urllib.request
from pathlib import Path

import pytest

from repro_score import cli
from repro_score.links import check_links, link_targets
from repro_score.remote import MAX_BYTES, RemoteError, download
from repro_score.repo import Repo
from repro_score.report import score_repo

README = ("Weights: https://huggingface.co/org/model and https://zenodo.org/records/1 (gone).\n"
          "The dataset is at https://example.org/corpus.tar\n")  # fmt: skip


def test_link_targets_are_the_model_and_data_links_each_once() -> None:
    repo = Repo.of({"README.md": README + "Again: https://huggingface.co/org/model\nSee https://arxiv.org/abs/1\n"})
    assert [u for u, _ in link_targets(repo)] == [
        "https://huggingface.co/org/model",
        "https://zenodo.org/records/1",
        "https://example.org/corpus.tar",
    ]


def test_check_links_heads_then_gets_and_reads_statuses() -> None:
    seen: list[tuple[str, str]] = []

    def opener(req: urllib.request.Request, timeout: float) -> int:
        seen.append((req.get_method(), req.full_url))
        if "zenodo" in req.full_url:
            return 404
        if "example.org" in req.full_url:
            return 405 if req.get_method() == "HEAD" else 206  # HEAD refused: a one-byte GET answers
        if "down" in req.full_url:
            raise urllib.error.URLError("no route")
        return 200

    import urllib.error

    links = check_links([("https://huggingface.co/a/b", "README.md:1"), ("https://zenodo.org/records/1", "README.md:1"),
                         ("https://example.org/x", "README.md:2"), ("https://down.example/y", "README.md:3")], opener, pause=0)  # fmt: skip
    assert [(x.verdict, x.status) for x in links] == [("ok", 200), ("dead", 404), ("ok", 206), ("unreachable", None)]
    assert ("GET", "https://example.org/x") in seen and links[3].note == "no route"
    assert all(m == "HEAD" for m, u in seen if "example.org" not in u)


def test_dead_links_are_listed_beside_the_score_not_in_it(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(README, encoding="utf-8")
    offline = score_repo(tmp_path)
    online = score_repo(tmp_path, links=True, opener=lambda req, t: 404 if "zenodo" in req.full_url else 200)
    assert online.score == offline.score and offline.links is None
    assert [x.url for x in online.bad_links()] == ["https://zenodo.org/records/1"]
    text = online.text()
    assert "Links checked: 2 ok, 1 dead; the score does not count them" in text and "✗ https://zenodo.org/records/1  (404; README.md:1)" in text
    assert online.json()["links"][1]["verdict"] == "dead"


def tarball(files: dict[str, bytes], extra: list[tarfile.TarInfo] | None = None) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, data in files.items():
            info = tarfile.TarInfo(f"repo-abc123/{name}")
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
        for info in extra or []:
            t.addfile(info)
    return buf.getvalue()


def test_download_extracts_inside_the_folder_only(tmp_path: Path) -> None:
    link = tarfile.TarInfo("repo-abc123/LICENSE")
    link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
    escape = tarfile.TarInfo("repo-abc123/../../evil.txt")
    data = tarball({"README.md": b"# hi\n", "src/train.py": b"x = 1\n"}, [link, escape])
    urls: list[str] = []

    def fetcher(url: str, limit: int) -> bytes:
        urls.append(url)
        assert limit == MAX_BYTES
        return data

    out = download("o", "r", "v1", tmp_path / "d", fetcher)
    assert urls == ["https://codeload.github.com/o/r/tar.gz/v1"]
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == ["README.md", "src/train.py"]
    assert not (tmp_path / "evil.txt").exists() and not (out / "LICENSE").exists()


def test_download_errors() -> None:
    def big(url: str, limit: int) -> bytes:
        raise RemoteError("the archive is larger than 300 MB")

    with pytest.raises(RemoteError, match="larger"):
        download("o", "r", "HEAD", Path("unused"), big)
    with pytest.raises(RemoteError, match="not a readable archive"):
        download("o", "r", "HEAD", Path("unused"), lambda u, n: b"not a tarball")


def test_many_repositories_make_a_table(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "README.md").write_text("# a\n" + "w " * 200, encoding="utf-8")
    good = tarball({"README.md": b"# b\n\n```\npip install -r requirements.txt\npython train.py\n```\n", "requirements.txt": b"torch==2.3.1\n",
                    "train.py": b"import torch\ntorch.manual_seed(0)\n"})  # fmt: skip

    def fake_download(owner: str, repo: str, ref: str, dest: Path) -> Path:
        if repo == "missing":
            raise RemoteError(f"github:{owner}/{repo}@{ref}: could not download (404)")
        return download(owner, repo, ref, dest, lambda u, n: good)

    monkeypatch.setattr(cli, "download", fake_download)
    monkeypatch.setattr(cli, "DOWNLOAD_PAUSE", 0)
    listing = tmp_path / "repos.txt"
    listing.write_text("# a venue's code\ngithub:o/b\nhttps://github.com/o/missing  # gone\n", encoding="utf-8")
    assert cli.main([str(tmp_path / "a"), "--list", str(listing)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].split()[:3] == ["repository", "score", "deps"]
    assert out[2].startswith("o/b ") and out[3].startswith("o/missing") and out[3].endswith("could not download (404)")
    assert out[-1].startswith("repro-score: 2 repositories scored, mean") and out[-1].endswith("1 could not be read")
    assert cli.main([str(tmp_path / "a"), "github:o/b", "--csv"]) == 0
    csv = capsys.readouterr().out.splitlines()
    assert csv[0] == "repository,score,deps,run,code,artifacts,randomness,compute,legal,notebooks,error" and csv[2].startswith("o/b,")
    assert cli.main([str(tmp_path / "a"), "github:o/b", "--json"]) == 0
    assert [r["repository"] for r in json.loads(capsys.readouterr().out)] == ["a", "o/b"]
    assert cli.main([str(tmp_path / "a"), "github:o/b", "--badge", str(tmp_path / "x.svg")]) == 2
