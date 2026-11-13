"""A repository read as files, without running anything: its paths, and the text of the files small enough to read."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env", ".tox", ".mypy_cache", ".pytest_cache",
             ".ruff_cache", "site-packages", ".idea", ".vscode", "wandb", ".ipynb_checkpoints"}  # fmt: skip
TEXT_LIMIT = 2_000_000  # bytes: larger files are listed, not read
NOTEBOOK_LIMIT = 50_000_000


def decode(data: bytes) -> str:
    """Text as files are written: UTF-8 (with or without a BOM), or UTF-16 with its BOM (PowerShell 5's
    `pip freeze > requirements.txt`); undecodable bytes replaced.

    >>> decode("torch==2.1\\n".encode("utf-16")), decode(b"\\xef\\xbb\\xbf{}")
    ('torch==2.1\\n', '{}')
    """
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


MAX_FILES = 50_000


@dataclass
class Repo:
    root: Path
    files: list[str] = field(default_factory=list)  # posix paths relative to the root
    truncated: bool = False  # more files than MAX_FILES
    _text: dict[str, str | None] = field(default_factory=dict, repr=False)
    _set: set[str] = field(default_factory=set, repr=False)
    _dirs: set[str] = field(default_factory=set, repr=False)

    @classmethod
    def read(cls, root: Path) -> Repo:
        repo = cls(root.resolve())
        for dirpath, dirnames, filenames in os.walk(repo.root, followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info"))
            for name in sorted(filenames):
                p = Path(dirpath) / name
                if p.is_symlink():
                    continue  # a link could point outside the repository
                repo.files.append(p.relative_to(repo.root).as_posix())
                if len(repo.files) >= MAX_FILES:
                    repo.truncated = True
                    break
            if repo.truncated:
                break
        repo._set = set(repo.files)
        repo._dirs = {f.rsplit("/", i)[0] for f in repo.files for i in range(1, f.count("/") + 1)}
        return repo

    @classmethod
    def of(cls, files: dict[str, str]) -> Repo:
        """A repository in memory (for tests and examples): paths and their text."""
        repo = cls(Path("."), sorted(files))
        repo._text = dict(files)
        repo._set = set(repo.files)
        repo._dirs = {f.rsplit("/", i)[0] for f in repo.files for i in range(1, f.count("/") + 1)}
        return repo

    def text(self, path: str) -> str | None:
        """A file's text (UTF-8, errors replaced), or None if it is too large or cannot be read."""
        if path not in self._text:
            p = self.root / path
            limit = NOTEBOOK_LIMIT if path.lower().endswith(".ipynb") else TEXT_LIMIT  # notebooks saved with outputs are large
            try:
                self._text[path] = decode(p.read_bytes()) if p.stat().st_size <= limit else None
            except OSError:
                self._text[path] = None
        return self._text[path]

    def exists(self, path: str) -> bool:
        """A file or folder of the repository, by its path from the root (`./` and a trailing `/` allowed)."""
        p = path.strip().removeprefix("./").rstrip("/")
        while p.startswith("./"):
            p = p.removeprefix("./")
        return p in self._set or p in self._dirs

    def named(self, *suffixes: str) -> list[str]:
        """Files whose name ends with one of these (case-insensitive)."""
        low = tuple(s.lower() for s in suffixes)
        return [f for f in self.files if f.lower().endswith(low)]

    def readme(self) -> str | None:
        """The top-level README's path (README.md first, then .rst, .txt, none)."""
        top = [f for f in self.files if "/" not in f and f.lower().startswith("readme")]
        order = {".md": 0, ".markdown": 0, ".rst": 1, ".txt": 2, "": 3}
        top.sort(key=lambda f: order.get(Path(f).suffix.lower(), 4))
        return top[0] if top else None
