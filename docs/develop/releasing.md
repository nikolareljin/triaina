# Releasing

Versions are plain `X.Y.Z` tags (no `v` prefix), created by CI.

1. `git checkout -b release/0.2.0`
2. `./dev release 0.2.0`: updates `VERSION` and inserts an empty dated
   `0.2.0` section in `CHANGELOG.md`.
3. By hand, until https://github.com/nikolareljin/script-helpers/issues/137 is
   fixed:
    - set `__version__` in `triaina/__init__.py` to the same version
      (`tests/test_version.py` fails otherwise);
    - move the entries from `## [Unreleased]` into the new section, grouped
      under Added / Changed / Fixed, and leave `## [Unreleased]` empty. The
      release notes are that section; left empty, the release has empty notes.
4. `bash scripts/check-changelog.sh` must print the new version.
5. Commit, push, open a pull request.
6. On merge, `auto-tag.yml` tags `0.2.0` through the ci-helpers `auto-tag.yml`
   preset, then the ci-helpers `release-build.yml` preset runs the tests, builds
   `dist/triaina-0.2.0.tar.gz` with `make dist` and publishes the GitHub release
   with notes generated from the CHANGELOG section.

The archive contains `triaina/` (the package), `scripts/` (the three CLIs plus
script-helpers' `helpers.sh` and `lib/`), `config/`, `deploy/`, `assets/`,
`pyproject.toml`, `requirements.txt`, `README.md`, `LICENSE` and
`CHANGELOG.md`.

If the release job fails after tagging, fix the cause and re-run the failed
job from the Actions tab; the tag already exists and is reused.
