# Releasing

Versions are plain `X.Y.Z` tags (no `v` prefix), created by CI.

1. `git checkout -b release/0.2.0`
2. `./dev release 0.2.0`: updates `VERSION` and turns `## Unreleased` into a
   dated `0.2.0` section in `CHANGELOG.md`.
3. Commit, push, open a pull request.
4. On merge, `release.yml` tags `0.2.0`, runs the tests, builds
   `dist/triaina-0.2.0.tar.gz` with `make dist` and publishes a GitHub release
   with the CHANGELOG section as notes.

The archive contains `config/`, `scripts/` (with a copy of script-helpers'
`helpers.sh` and `lib/`), `assets/`, `README.md`, `LICENSE`, `CHANGELOG.md`
and `requirements.txt`.

To rebuild the archive for an existing tag: Actions > Release > Run workflow,
version `0.2.0`.
