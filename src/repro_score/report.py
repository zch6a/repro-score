"""A repository's score and its report: as text, Markdown (for a GitHub job summary) and JSON."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from . import __version__
from .checks import SECTIONS, Item, run_checks
from .repo import Repo

MARK = {"pass": "✓", "partial": "~", "missing": "✗", "n/a": "·"}


@dataclass
class Report:
    name: str
    items: list[Item]
    truncated: bool = False

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

    def text(self, evidence: bool = True) -> str:
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
        return "\n".join(lines)

    def markdown(self) -> str:
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
        lines.append("")
        lines.append(f"<sub>repro-score {__version__}: read from the repository's files; no code was run.</sub>")
        return "\n".join(lines)

    def json(self) -> dict[str, object]:
        return {
            "version": __version__,
            "repository": self.name,
            "score": self.score,
            "sections": [{"section": key, "title": title, "points": got, "max": out_of} for key, title, got, out_of, _ in self.sections()],
            "items": [{**asdict(i), "status": i.status} for i in self.items],
            "truncated": self.truncated,
        }


def _n(x: float) -> str:
    return f"{x:g}"


def score_repo(path: Path, name: str | None = None) -> Report:
    repo = Repo.read(path)
    return Report(name or path.resolve().name, run_checks(repo), repo.truncated)
