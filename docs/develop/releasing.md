# Releasing

Versions are plain `X.Y.Z` tags (no `v` prefix), created by CI.

1. `git checkout -b release/0.2.0`
2. `./dev release 0.2.0`: updates `VERSION` and turns `## Unreleased` into a
   dated `0.2.0` section in `CHANGELOG.md`.
3. Commit, push, open a pull request.
4. On merge, `auto-tag.yml` tags `0.2.0` through the ci-helpers `auto-tag.yml`
   preset, then the ci-helpers `release-build.yml` preset runs the tests, builds
   `dist/triaina-0.2.0.tar.gz` with `make dist` and publishes the GitHub release
   with notes generated from the CHANGELOG section.

The archive contains `config/`, `scripts/` (with a copy of script-helpers'
`helpers.sh` and `lib/`), `assets/`, `README.md`, `LICENSE`, `CHANGELOG.md`
and `requirements.txt`.

If the release job fails after tagging, fix the cause and re-run the failed
job from the Actions tab; the tag already exists and is reused.
