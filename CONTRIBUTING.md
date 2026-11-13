# Contributing

```bash
uv sync
uv run pytest -q          # made-up repositories only; downloads and link checks are faked; no network
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

## Where things are

| Module | What it does |
| --- | --- |
| `repo.py` | a repository read as files (no links followed, large files not read) |
| `checks.py` | the checks: each returns items with points, evidence (file and line) and advice |
| `report.py` | the score and the report as text, Markdown and JSON |
| `badge.py` | the SVG badge |
| `remote.py` | a GitHub repository downloaded as an archive to a temporary folder |
| `links.py` | `--check-links`: whether model and data links answer |
| `cli.py` | `repro-score` |
| `action.yml` | the GitHub Action |

`examples/paper-code` is a made-up repository; a test checks that the README shows what repro-score prints for it,
and CI runs the Action on it.

## Changing a check

Say where the item comes from (the Papers with Code checklist, a conference checklist) in the docstring, keep each
finding's evidence a file and line a reader can open, and try the change on real repositories (downloaded to a
scratch folder, never run, deleted after) as well as on made-up ones in `tests/test_checks.py`.
