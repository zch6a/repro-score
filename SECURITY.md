# Security

## What it does

- **Reads, never runs.** It lists the repository's files and reads their text; no code of the repository is run,
  imported or installed, and notebooks are read as JSON.
- **Over the network only when asked.** A local folder is read offline; links are counted, not fetched. Two things
  reach the network, each only when you ask for it: `github:owner/repo` downloads that repository's archive from
  GitHub (no token, 300 MB at most, a generic User-Agent, extracted with tarfile's data filter: no links, no paths
  outside a temporary folder, which is deleted after); `--check-links` asks each model and data link whether it
  answers (at most 40, a second apart per host). The GitHub Action installs repro-score from the action's own files
  and runs it on the checkout.
- **Inside the repository only.** Symbolic links are not followed (one could point outside the repository); files over
  2 MB are listed but not read; at most 50,000 files are read.
- **The Action's inputs are data.** They reach its shell script as environment variables, never pasted into it, and
  `min-score` must be a whole number.

## Reporting a vulnerability

Please open a private security advisory on GitHub (Security → Report a vulnerability) rather than a public issue.
