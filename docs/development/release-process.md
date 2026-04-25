# Release Process

This document is the single source of truth for releasing tvkit — covering versioning strategy, the automated pipeline, manual steps, and the one-time setup required.

---

## Versioning Strategy

tvkit follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

| Change type | Component | Example |
| --- | --- | --- |
| Breaking API change | `MAJOR` | `0.x.x → 1.0.0` |
| New feature, backwards-compatible | `MINOR` | `0.11.x → 0.12.0` |
| Bug fix or internal improvement | `PATCH` | `0.11.1 → 0.11.2` |

### Pre-release tags

Append a suffix to mark unstable releases:

| Suffix | Meaning | Example |
| --- | --- | --- |
| `-beta.N` | Feature-complete, needs testing | `v0.12.0-beta.1` |
| `-rc.N` | Release candidate, final validation | `v1.0.0-rc.1` |
| `-alpha.N` | Early preview, may break | `v1.0.0-alpha.1` |

Pre-release tags publish to PyPI with `--pre` semantics and are marked as pre-release on GitHub.

### Milestone roadmap

| Version | Theme | Key targets |
| --- | --- | --- |
| `0.11.x` | Stability | Bug fixes, improved error handling |
| `0.12.0` | Completeness | Scanner pagination, more intervals |
| `0.13.0` | Developer experience | Richer errors, better docs, type stubs |
| `1.0.0` | Stable API | Frozen public contract, full coverage |

Do not bump to `1.0.0` until the public API is frozen and test coverage is ≥ 90% on all public modules.

---

## Automated Pipeline

Every version tag (`v*.*.*`) triggers `.github/workflows/release.yml`:

```text
push tag vX.Y.Z
  │
  ├─ validate     — tag matches pyproject.toml version
  ├─ ci           — ruff + mypy + pytest (full suite)
  ├─ build        — sdist + wheel via `python -m build`
  ├─ publish-pypi — upload via PyPI Trusted Publisher (OIDC)
  └─ github-release — extract CHANGELOG section → create GitHub Release + attach dist assets
```

**Both PyPI and GitHub Release are created automatically from a single tag push. You never need to do them separately.**

---

## One-Time Setup (do this once per repository)

### 1. PyPI Trusted Publisher

This replaces token-based uploads in CI. No secret is stored in GitHub.

1. Log in to [pypi.org](https://pypi.org) → **Manage** → **Publishing** → **Add a new publisher**
2. Fill in:
   - **Owner**: `lumduan`
   - **Repository**: `tvkit`
   - **Workflow name**: `release.yml`
   - **Environment**: `pypi`
3. Save.

### 2. GitHub Environment

1. Go to **Settings → Environments → New environment**
2. Name it exactly `pypi`
3. (Optional but recommended) Add a required reviewer so no release can go out without approval

### 3. `softprops/action-gh-release` permissions

The workflow already sets `permissions: contents: write`. No extra token is needed.

---

## Release Checklist

Follow these steps for every release, in order.

### Before bumping the version

- [ ] All work for this release is merged to `main`
- [ ] `git pull origin main` — local branch is current
- [ ] Quality gate passes:

  ```bash
  uv run ruff check . && uv run ruff format . && uv run mypy tvkit/
  uv run python -m pytest tests/ -v
  ```

- [ ] `CHANGELOG.md` has a section for the new version with date and full notes

### Bump and tag

```bash
# 1. Update version in pyproject.toml
#    Change: version = "0.11.1"  →  version = "0.12.0"

# 2. Commit the version bump
git add pyproject.toml CHANGELOG.md
git commit -m "chore(release): bump version to v0.12.0"

# 3. Tag the commit
git tag v0.12.0

# 4. Push branch and tag together
git push origin main --tags
```

Pushing the tag starts the automated pipeline. Watch it at:
`https://github.com/lumduan/tvkit/actions`

### After the pipeline completes

- [ ] Verify PyPI: `https://pypi.org/project/tvkit/0.12.0/`
- [ ] Test installation in a clean environment:

  ```bash
  pip install tvkit==0.12.0
  ```

- [ ] Verify GitHub Release: `https://github.com/lumduan/tvkit/releases/tag/v0.12.0`
  - Release notes match the CHANGELOG section
  - Both `.whl` and `.tar.gz` assets are attached
- [ ] Mark the release as **Latest** if this is a stable release (the workflow does this automatically for non-pre-release tags)

---

## Manual Fallback (if automation fails)

If the GitHub Actions pipeline fails after a tag is already pushed:

```bash
# Rebuild
rm -rf dist/ build/
uv run python -m build

# Publish to PyPI manually
./scripts/publish.sh

# Create GitHub Release manually
gh release create v0.12.0 dist/* \
  --title "tvkit v0.12.0" \
  --notes-file <(awk '/^## \[0\.12\.0\]/,/^## \[/' CHANGELOG.md | head -n -1 | tail -n +2)
```

Never skip the GitHub Release step — **every PyPI publish must have a matching GitHub Release**.

---

## CHANGELOG Format

Every release section must follow this format so the automation can extract it cleanly:

```markdown
## [0.12.0] — 2026-05-15

### Added
- New feature description

### Changed
- What changed and why

### Fixed
- Bug that was fixed

### Removed
- What was removed (include migration path if breaking)
```

Rules:

- The header must be exactly `## [VERSION] — YYYY-MM-DD`
- Add the new section at the **top** of the file, above the previous release
- Every public API change needs an entry

---

## Local Publishing (reference)

`./scripts/publish.sh` is the manual publish path. It reads `PYPI_TOKEN` from `.env`, builds, and uploads. Use this only when you need to bypass CI (e.g., fixing a broken release quickly). Always follow up with a manual `gh release create` afterward.

---

## See Also

- [Testing Strategy](testing-strategy.md) — quality gates required before release
- [Architecture Decisions](architecture-decisions.md) — design rationale
- [Workflow file](../../.github/workflows/release.yml) — the automation itself
