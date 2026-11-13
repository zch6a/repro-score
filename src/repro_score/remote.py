"""A GitHub repository scored without cloning it: its tarball downloaded to a temporary folder, read, deleted.

`github:owner/repo`, `github:owner/repo@ref` or `https://github.com/owner/repo` (a branch, tag or commit after `@`,
or `/tree/<ref>` in a URL). The tarball comes from GitHub's public archive endpoint, with a generic User-Agent and no
token; it is capped at MAX_BYTES, and extracted with tarfile's data filter (no links, no paths outside the folder).
Nothing in it is run.
"""

from __future__ import annotations

import io
import re
import tarfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

MAX_BYTES = 300 * 1024 * 1024
USER_AGENT = "repro-score"
PATTERN = re.compile(r"^(?:github:|gh:|https?://(?:www\.)?github\.com/)([\w.\-]+)/([\w.\-]+?)(?:\.git)?(?:/tree/([\w.\-/]+)|@([\w.\-/]+))?/?$")

Fetcher = Callable[[str, int], bytes]  # a URL and a byte limit -> the body


class RemoteError(Exception):
    pass


def parse(target: str) -> tuple[str, str, str] | None:
    """(owner, repository, ref) for a GitHub target, or None for anything else (a local folder).

    >>> parse("github:karpathy/nanoGPT"), parse("https://github.com/a/b.git"), parse("gh:a/b@v1.2"), parse("https://github.com/a/b/tree/dev")
    (('karpathy', 'nanoGPT', 'HEAD'), ('a', 'b', 'HEAD'), ('a', 'b', 'v1.2'), ('a', 'b', 'dev'))
    >>> parse("examples/paper-code") is None
    True
    """
    m = PATTERN.match(target.strip())
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3) or m.group(4) or "HEAD"


def _fetch(url: str, limit: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise RemoteError(f"the archive is larger than {limit // (1024 * 1024)} MB")
    return data


def download(owner: str, repo: str, ref: str, dest: Path, fetcher: Fetcher = _fetch) -> Path:
    """The repository at `ref`, extracted into dest (which must be empty); returns dest."""
    url = f"https://codeload.github.com/{owner}/{repo}/tar.gz/{ref}"
    try:
        data = fetcher(url, MAX_BYTES)
    except RemoteError:
        raise
    except OSError as e:  # URLError, HTTPError, timeouts
        reason = getattr(e, "code", None) or getattr(e, "reason", e)
        raise RemoteError(f"github:{owner}/{repo}@{ref}: could not download ({reason})") from e
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
            for m in t.getmembers():
                parts = m.name.split("/", 1)
                if len(parts) < 2 or not parts[1] or not (m.isfile() or m.isdir()):
                    continue  # the top folder (repo-sha/), links and devices
                m.name = parts[1]
                try:
                    t.extract(m, dest, filter="data")
                except (tarfile.FilterError, OSError):
                    continue  # a path outside the folder, or one this system cannot hold
    except (tarfile.TarError, EOFError, OSError) as e:
        raise RemoteError(f"github:{owner}/{repo}@{ref}: not a readable archive ({e})") from e
    return dest
