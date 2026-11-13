"""repro-score: how well a research code repository lets someone reproduce its paper.

repro-score                      the repository in the current folder
repro-score path/to/repo         another checkout
repro-score . --min-score 60     exit 1 below 60 (for CI)

It reads the files and runs nothing: dependencies and their versions, install and run instructions, training and
evaluation code, links to trained models and data, random seeds, the hardware stated, licence and citation, and
whether notebooks were saved with their outputs. Each item shows the file and line it was decided from.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .badge import badge
from .report import score_repo


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="repro-score", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="exit status: 0 scored (and at least --min-score), 1 under --min-score, 2 it could not run")  # fmt: skip
    ap.add_argument("path", nargs="?", default=".", type=Path, help="the repository's folder (default: the current one)")
    ap.add_argument("--json", action="store_true", help="the report as JSON")
    ap.add_argument("--markdown", action="store_true", help="the report as a Markdown table (for $GITHUB_STEP_SUMMARY or a comment)")
    ap.add_argument("--badge", type=Path, metavar="FILE", help="also write the score as an SVG badge to FILE")
    ap.add_argument("--min-score", type=int, metavar="N", help="exit 1 if the score is under N")
    ap.add_argument("--brief", action="store_true", help="the items without their evidence")
    ap.add_argument("--name", help="the name to show (default: the folder's)")
    ap.add_argument("--version", action="version", version=f"repro-score {__version__}")
    args = ap.parse_args(argv)
    if not args.path.is_dir():
        print(f"repro-score: {args.path.as_posix()}: not a folder", file=sys.stderr)
        return 2
    report = score_repo(args.path, args.name)
    if args.json:
        print(json.dumps(report.json(), indent=2, ensure_ascii=False))
    elif args.markdown:
        print(report.markdown())
    else:
        print(report.text(evidence=not args.brief))
    if args.badge:
        args.badge.write_text(badge(report.score), encoding="utf-8")
    if args.min_score is not None and report.score < args.min_score:
        print(f"repro-score: {report.score} is under the minimum of {args.min_score}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
