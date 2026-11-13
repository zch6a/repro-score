"""Checking the model and data links a report counted, when asked (--check-links): whether each still answers.

Opt-in, because it reaches the network: one request per link (HEAD, then a one-byte GET where HEAD is refused), a
generic User-Agent, at most MAX_LINKS links, a second between requests to the same host. The score does not depend on
it (it stays the same offline); dead links are listed beside it.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from .checks import artifact_links
from .repo import Repo

MAX_LINKS = 40
TIMEOUT = 15
USER_AGENT = "repro-score (link check)"
AMBIGUOUS = {401, 403, 405, 429}  # the server is there but will not say: sign-in pages, bot checks, rate limits

Opener = Callable[[urllib.request.Request, float], int]  # a request and a timeout -> the HTTP status


@dataclass
class Link:
    url: str
    where: str  # the file and line it was found at
    status: int | None  # the HTTP status, or None when it could not be reached
    verdict: str  # "ok", "dead", "unclear" (sign-in, bot check, rate limit), "unreachable"
    note: str = ""


def _open(req: urllib.request.Request, timeout: float) -> int:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.status)
    except urllib.error.HTTPError as e:
        return int(e.code)


def verdict(status: int | None) -> str:
    """
    >>> [verdict(s) for s in (200, 302, 404, 410, 403, 429, 500, None)]
    ['ok', 'ok', 'dead', 'dead', 'unclear', 'unclear', 'dead', 'unreachable']
    """
    if status is None:
        return "unreachable"
    if status < 400:
        return "ok"
    return "unclear" if status in AMBIGUOUS else "dead"


def link_targets(repo: Repo) -> list[tuple[str, str]]:
    """(url, where) for every model and data link the docs give, each once, models first."""
    models, data = artifact_links(repo)
    seen: dict[str, str] = {}
    for e in models + data:
        if e.text.startswith(("http://", "https://")) and e.text not in seen:
            seen[e.text] = f"{e.path}:{e.line}" if e.line else e.path
    return list(seen.items())


def check_links(targets: list[tuple[str, str]], opener: Opener = _open, pause: float = 1.0) -> list[Link]:
    out: list[Link] = []
    last: dict[str, float] = {}
    for url, where in targets[:MAX_LINKS]:
        host = urlsplit(url).netloc.lower()
        wait = last.get(host, 0) + pause - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        status: int | None = None
        note = ""
        try:
            status = opener(urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT}), TIMEOUT)
            if status in (403, 405, 501):  # some hosts refuse HEAD: ask for one byte instead
                status = opener(urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"}), TIMEOUT)
        except (urllib.error.URLError, OSError, ValueError) as e:
            note = str(getattr(e, "reason", e))[:80]
        last[host] = time.monotonic()
        out.append(Link(url, where, status, verdict(status), note))
    return out
