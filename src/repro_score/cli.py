"""repro-score: how well a research code repository lets someone reproduce its paper.

repro-score                          the repository in the current folder
repro-score path/to/repo             another checkout
repro-score github:owner/repo        a GitHub repository (downloaded to a temporary folder, read, deleted)
repro-score a b github:c/d           several: a table, one row each
repro-score --list repos.txt         the repositories listed in a file, one per line (a venue's papers' code)
repro-score . --min-score 60         exit 1 below 60 (for CI)

It reads the files and runs nothing: dependencies and their versions, install and run instructions, training and
evaluation code, links to trained models and data, random seeds, the hardware stated, licence and citation, and
whether notebooks were saved with their outputs. Each item shows the file and line it was decided from.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

from . import __version__
from .badge import badge
from .remote import RemoteError, download, parse
from .report import Report, Table, score_repo

DOWNLOAD_PAUSE = 3.0  # seconds between two downloads from GitHub


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="repro-score", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="exit status: 0 scored (and at least --min-score), 1 under --min-score, 2 it could not run")  # fmt: skip
    ap.add_argument("targets", nargs="*", help="repository folders, or github:owner/repo[@ref] or GitHub URLs (default: the current folder)")
    ap.add_argument("--list", type=Path, metavar="FILE", help="also the repositories listed in FILE, one per line (# for comments)")
    ap.add_argument("--json", action="store_true", help="the report (or the rows, for several) as JSON")
    ap.add_argument("--markdown", action="store_true", help="the report as a Markdown table (for $GITHUB_STEP_SUMMARY or a comment)")
    ap.add_argument("--csv", action="store_true", help="for several repositories: the table as CSV")
    ap.add_argument("--badge", type=Path, metavar="FILE", help="also write the score as an SVG badge to FILE (one repository)")
    ap.add_argument("--summary-file", type=Path, metavar="FILE", help="also append the Markdown report to FILE ($GITHUB_STEP_SUMMARY)")
    ap.add_argument("--json-file", type=Path, metavar="FILE", help="also write the JSON report to FILE")
    ap.add_argument("--min-score", type=int, metavar="N", help="exit 1 if a score is under N")
    ap.add_argument("--check-links", action="store_true", help="also check that the model and data links answer (reaches the network)")
    ap.add_argument("--brief", action="store_true", help="the items without their evidence")
    ap.add_argument("--name", help="the name to show (default: the folder's, or owner/repo)")
    ap.add_argument("--version", action="version", version=f"repro-score {__version__}")
    args = ap.parse_args(argv)
    targets = list(args.targets)
    if args.list:
        try:
            lines = args.list.read_text(encoding="utf-8").splitlines()
        except OSError as e:
            print(f"repro-score: {args.list}: {e.strerror or e}", file=sys.stderr)
            return 2
        targets += [s.split("#")[0].strip() for s in lines if s.split("#")[0].strip()]
    if not targets:
        targets = ["."]
    for t in targets:
        if parse(t) is None and not Path(t).is_dir():
            print(f"repro-score: {t}: not a folder, nor github:owner/repo", file=sys.stderr)
            return 2
    many = len(targets) > 1
    if args.badge and many:
        print("repro-score: --badge is for one repository", file=sys.stderr)
        return 2
    reports: list[Report] = []
    fetched = 0
    for t in targets:
        remote = parse(t)
        if remote is None:
            reports.append(score_repo(Path(t), args.name if not many else None, links=args.check_links))
            continue
        owner, repo, ref = remote
        name = args.name if args.name and not many else f"{owner}/{repo}" + ("" if ref == "HEAD" else f"@{ref}")
        if fetched:
            time.sleep(DOWNLOAD_PAUSE)
        fetched += 1
        with tempfile.TemporaryDirectory(prefix="repro-score-") as d:
            try:
                download(owner, repo, ref, Path(d))
            except RemoteError as e:
                if not many:
                    print(f"repro-score: {e}", file=sys.stderr)
                    return 2
                reports.append(Report(name, [], error=str(e)))
                continue
            reports.append(score_repo(Path(d), name, links=args.check_links))
    if many:
        table = Table(reports)
        if args.json:
            print(json.dumps([r.json() for r in reports], indent=2, ensure_ascii=False))
        elif args.csv:
            print(table.csv(), end="")
        elif args.markdown:
            print(table.markdown())
        else:
            print(table.text())
    else:
        report = reports[0]
        if args.json:
            print(json.dumps(report.json(), indent=2, ensure_ascii=False))
        elif args.markdown:
            print(report.markdown())
        else:
            print(report.text(evidence=not args.brief))
        if args.badge:
            args.badge.write_text(badge(report.score), encoding="utf-8")
    if args.summary_file:
        with args.summary_file.open("a", encoding="utf-8") as f:
            f.write((Table(reports).markdown() if many else reports[0].markdown()) + "\n")
    if args.json_file:
        data = [r.json() for r in reports] if many else reports[0].json()
        args.json_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if all(r.error for r in reports):
        return 2  # nothing could be read
    under = [r for r in reports if not r.error and args.min_score is not None and r.score < args.min_score]
    if under:
        names = ", ".join(f"{r.name} ({r.score})" for r in under[:10])
        print(f"repro-score: under the minimum of {args.min_score}: {names}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
