"""A repository's score and its report: as text, Markdown (for a GitHub job summary) and JSON; and a table for many."""

from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import __version__
from .checks import SECTIONS, Item, run_checks
from .links import Link, Opener, check_links, link_targets
from .repo import Repo

MARK = {"pass": "✓", "partial": "~", "missing": "✗", "n/a": "·"}
LINK_MARK = {"ok": "✓", "dead": "✗", "unclear": "?", "unreachable": "✗"}


@dataclass
class Report:
    name: str
    items: list[Item]
    truncated: bool = False
    links: list[Link] | None = None  # None: not checked (--check-links not given)
    links_total: int = 0  # how many links there were to check (only the first MAX_LINKS are)
    error: str = ""  # a repository that could not be read (a download that failed)

    @property
    def score(self) -> int:
        """Points over the points of the items that apply, out of 100."""
        got = sum(i.points for i in self.items if i.applies)
        out_of = sum(i.max for i in self.items if i.applies)
        return round(100 * got / out_of) if out_of else 0

    def sections(self) -> list[tuple[str, str, float, float, list[Item]]]:
        out = []
        for key, title in SECTIONS.items():
            items = [i for i in self.items if i.section == key]
            applying = [i for i in items if i.applies]
            out.append((key, title, sum(i.points for i in applying), sum(i.max for i in applying), items))
        return out

    def missing(self) -> list[Item]:
        """The items short of their points, the ones worth most first."""
        return sorted((i for i in self.items if i.applies and i.points < i.max), key=lambda i: -(i.max - i.points))

    def bad_links(self) -> list[Link]:
        return [x for x in self.links or [] if x.verdict in ("dead", "unreachable")]

    def text(self, evidence: bool = True) -> str:
        if self.error:
            return f"repro-score: {self.name}: {self.error}"
        lines = [f"repro-score: {self.name}: {self.score}/100"]
        if self.truncated:
            lines.append("  (more than 50,000 files: only the first were read)")
        for _, title, got, out_of, items in self.sections():
            if not out_of:
                lines.append(f"{title}: does not apply")
                continue
            lines.append(f"{title}  {_n(got)}/{_n(out_of)}")
            for i in items:
                if not i.applies:
                    continue
                lines.append(f"  {MARK[i.status]} {i.title}  {_n(i.points)}/{_n(i.max)}")
                if evidence:
                    lines += [f"      {e}" for e in i.evidence[:3]]
                if i.advice and i.points < i.max:
                    lines.append(f"      → {i.advice}")
        if self.links is not None:
            lines.append(self._links_line())
            shown = self.links if evidence else self.bad_links()
            for x in shown:
                status = x.status if x.status is not None else x.note or "no answer"
                lines.append(f"  {LINK_MARK[x.verdict]} {x.url}  ({status}; {x.where})")
        return "\n".join(lines)

    def _links_line(self) -> str:
        if not self.links:
            return "Links: no model or data links to check"
        counts = {v: sum(1 for x in self.links if x.verdict == v) for v in ("ok", "dead", "unreachable", "unclear")}
        more = f" (the first {len(self.links)} of {self.links_total})" if self.links_total > len(self.links) else ""
        parts = [f"{n} {v}" for v, n in counts.items() if n]
        return f"Links checked{more}: " + ", ".join(parts) + ("; the score does not count them" if self.bad_links() else "")

    def markdown(self) -> str:
        if self.error:
            return f"### repro-score: {self.name}\n\n{self.error}"
        lines = [f"### repro-score: {self.score}/100", "", "| | Item | Points | Evidence or what to add |", "|---|---|---|---|"]
        for _, title, _got, out_of, items in self.sections():
            if not out_of:
                continue
            for i in items:
                if not i.applies:
                    continue
                note = i.advice if i.points < i.max and i.advice else "; ".join(str(e) for e in i.evidence[:2])
                note = note.replace("|", "\\|")
                lines.append(f"| {MARK[i.status]} | {title}: {i.title} | {_n(i.points)}/{_n(i.max)} | {note} |")
        if self.links is not None:
            lines += ["", self._links_line()]
            lines += [f"- {LINK_MARK[x.verdict]} {x.url} ({x.status or x.note or 'no answer'}; {x.where})" for x in self.bad_links()]
        lines.append("")
        lines.append(f"<sub>repro-score {__version__}: read from the repository's files; no code was run.</sub>")
        return "\n".join(lines)

    def json(self) -> dict[str, object]:
        out: dict[str, object] = {"version": __version__, "repository": self.name}
        if self.error:
            return {**out, "error": self.error}
        out |= {
            "score": self.score,
            "sections": [{"section": key, "title": title, "points": got, "max": out_of} for key, title, got, out_of, _ in self.sections()],
            "items": [{**asdict(i), "status": i.status} for i in self.items],
            "truncated": self.truncated,
        }
        if self.links is not None:
            out["links"] = [asdict(x) for x in self.links]
            out["links_total"] = self.links_total
        return out


@dataclass
class Table:
    """Many repositories, one row each: the score and each section's points."""

    reports: list[Report] = field(default_factory=list)

    def rows(self) -> list[dict[str, object]]:
        rows = []
        for r in self.reports:
            row: dict[str, object] = {"repository": r.name, "score": "" if r.error else r.score}
            for key, _, got, out_of, _ in r.sections():
                row[key] = "" if r.error else "-" if not out_of else f"{_n(got)}/{_n(out_of)}"
            if any(x.links is not None for x in self.reports):
                row["dead_links"] = "" if r.links is None else len(r.bad_links())
            row["error"] = r.error
            rows.append(row)
        return rows

    def text(self) -> str:
        rows = self.rows()
        if not rows:
            return "repro-score: no repositories"
        keys = [k for k in rows[0] if k != "error"]
        width = {k: max(len(k), *(len(str(r[k])) for r in rows)) for k in keys}
        lines = ["  ".join(k.ljust(width[k]) for k in keys)]
        for r in rows:
            line = "  ".join(str(r[k]).ljust(width[k]) for k in keys)
            lines.append((line + "  " + str(r["error"])) if r["error"] else line.rstrip())
        scored = [r.score for r in self.reports if not r.error]
        if scored:
            mean = sum(scored) / len(scored)
            ordered = sorted(scored)
            median = ordered[len(ordered) // 2] if len(ordered) % 2 else (ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]) / 2
            lines.append(f"repro-score: {len(scored)} repositories scored, mean {mean:.1f}, median {_n(median)}"
                         + (f"; {len(self.reports) - len(scored)} could not be read" if len(scored) < len(self.reports) else ""))  # fmt: skip
        return "\n".join(lines)

    def csv(self) -> str:
        rows = self.rows()
        buf = io.StringIO()
        if rows:
            w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        return buf.getvalue()

    def markdown(self) -> str:
        rows = self.rows()
        if not rows:
            return "repro-score: no repositories"
        keys = list(rows[0])
        lines = ["| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)]
        lines += ["| " + " | ".join(str(r[k]).replace("|", "\\|") for k in keys) + " |" for r in rows]
        return "\n".join(lines)


def _n(x: float) -> str:
    return f"{x:g}"


def score_repo(path: Path, name: str | None = None, links: bool = False, opener: Opener | None = None) -> Report:
    """A repository's report; `links` also checks its model and data links (over the network)."""
    repo = Repo.read(path)
    report = Report(name or path.resolve().name, run_checks(repo), repo.truncated)
    if links:
        targets = link_targets(repo)
        report.links = check_links(targets, opener) if opener else check_links(targets)
        report.links_total = len(targets)
    return report
