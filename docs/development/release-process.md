# Release Process

This page documents how to prepare, build, and publish a new tvkit release to PyPI.

## Prerequisites

- `uv` installed and `uv sync` run (all dev dependencies present)
- PyPI project-scoped API token stored in `.env` as `PYPI_TOKEN=pypi-...`
- All quality checks passing
- Working on or merged into `main`

## Quick Release Steps

1. Sync `main` from remote
2. Run the full quality gate
3. Bump version in `pyproject.toml`
4. Commit, tag, and push
5. Run `./scripts/publish.sh`
6. Verify the package on PyPI and create a GitHub release

## Sync Repository

Ensure the local repository is up to date before starting:

```bash
git checkout main
git pull origin main
```

Never release from a stale local branch.

## Pre-Release Checklist

Run the full quality gate:

```bash
uv run ruff check . && uv run ruff format . && uv run mypy tvkit/
uv run python -m pytest tests/ -v
```

All checks must pass. Do not publish a release with failing tests or type errors.

## Version Bump

Version is declared in `pyproject.toml`:

```toml
[project]
version = "0.3.0"
```

tvkit follows [Semantic Versioning](https://semver.org/):

| Change type | Version component | Example |
|-------------|-------------------|---------|
| Backwards-incompatible API change | Major (`X.0.0`) | `0.3.0` → `1.0.0` |
| New feature, backwards-compatible | Minor (`0.X.0`) | `0.3.0` → `0.4.0` |
| Bug fix or internal change | Patch (`0.0.X`) | `0.3.0` → `0.3.1` |

Update the version in `pyproject.toml`, commit the change, and tag the commit:

```bash
git add pyproject.toml
git commit -m "release: bump version to vX.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

## Build

Clean previous build artifacts before building to avoid uploading stale files:

```bash
rm -rf dist/ build/ *.egg-info
uv run python3 -m build
```

Output goes to `dist/`. The publish script validates that `dist/` is non-empty before uploading.

## Publishing

Use the publish script:

```bash
./scripts/publish.sh
```

The script:
1. Reads `PYPI_TOKEN` from `.env`
2. Validates the token starts with `pypi-`
3. Builds the package with `python -m build`
4. Prompts for confirmation before uploading
5. Uploads to production PyPI with `twine`

The script publishes to **production PyPI** — not TestPyPI. Verify the version number and quality checks before confirming the prompt.

### Optional: Verify with TestPyPI First

To test the upload without affecting production:

```bash
uv run python3 -m twine upload --repository testpypi dist/* --username __token__ --password "$PYPI_TOKEN"
```

Note: TestPyPI uses a separate token from a separate account (`test.pypi.org`).

## Post-Release

After a successful publish:

1. Verify the release at `https://pypi.org/project/tvkit/`
2. Test installation: `pip install tvkit==X.Y.Z`
3. Create a GitHub release for the tag `vX.Y.Z` with release notes
4. Update `CHANGELOG.md` if maintained

## PyPI Token Setup

Generate a project-scoped token at `https://pypi.org/manage/project/tvkit/settings/` (requires a PyPI account with maintainer access). Store it in a `.env` file at the project root:

```text
PYPI_TOKEN=pypi-your-token-here
```

The `.env` file is gitignored. Never commit a PyPI token to version control.

## See Also

- [Testing Strategy](testing-strategy.md) — quality gates required before release
- [Architecture Decisions](architecture-decisions.md) — why certain design choices were made
