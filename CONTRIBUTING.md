# Contributing

1. Fork, then `git clone --recursive` and `./dev install`.
2. Branch from `main`.
3. Keep runtime scripts standard-library only; add tests under `tests/` (no network).
4. `./dev preflight` must pass.
5. Add a line under `## Unreleased` in `CHANGELOG.md`.
6. Open a pull request describing what changed and why.

Hardware changes (new board revision, new mount): include what you measured and
on which unit.
