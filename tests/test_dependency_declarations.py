"""
Guard against third-party imports that are not declared as runtime dependencies.

This exists because of a real shipped bug. ``tvkit/time/exchange.py`` did
``import yaml`` inside ``load_exchange_overrides()``, but ``pyyaml`` was never listed
in ``[project.dependencies]``. Every test passed, because ``pre-commit`` pulls
``pyyaml`` in as a transitive *dev* dependency — so it is always present in a
contributor's environment and never in a user's. The published wheel raised
``ImportError`` from documented public API until 0.13.1.

No behavioural test can catch that class of bug: the dev environment always has the
package. The only reliable check is a structural one — compare what ``tvkit/``
actually imports against what ``pyproject.toml`` actually declares.

Scope: runtime imports under ``tvkit/`` versus ``[project.dependencies]``. Test-only
imports and dev dependencies are deliberately not covered. The reverse direction
(declared but never imported) is not asserted either — tvkit currently declares
several such packages on purpose.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
import tomllib
from importlib.metadata import packages_distributions

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "tvkit"
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Imports that resolve to the package itself rather than to a distribution.
FIRST_PARTY = {"tvkit"}


def _normalize(name: str) -> str:
    """Normalize a distribution name per PEP 503 (``PyYAML`` -> ``pyyaml``)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _imported_top_level_modules(package_dir: pathlib.Path) -> dict[str, list[str]]:
    """
    Map every top-level module imported under ``package_dir`` to its call sites.

    Walks the full AST rather than reading only the header, so imports nested inside
    functions or ``if TYPE_CHECKING:`` blocks are found too — the ``yaml`` import that
    motivated this test was a lazy one inside a function body.

    Relative imports are skipped: they are first-party by construction.
    """
    modules: dict[str, list[str]] = {}
    for path in sorted(package_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level or node.module is None:
                    continue
                names = [node.module]
            else:
                continue
            site = f"{path.relative_to(REPO_ROOT)}:{node.lineno}"
            for name in names:
                modules.setdefault(name.split(".")[0], []).append(site)
    return modules


def _third_party_imports() -> dict[str, list[str]]:
    """Imported top-level modules that are neither stdlib nor first-party."""
    return {
        module: sites
        for module, sites in _imported_top_level_modules(PACKAGE_DIR).items()
        if module not in sys.stdlib_module_names and module not in FIRST_PARTY
    }


def _declared_runtime_distributions() -> set[str]:
    """Normalized distribution names from ``[project.dependencies]``."""
    with PYPROJECT.open("rb") as handle:
        pyproject = tomllib.load(handle)
    return {
        _normalize(re.split(r"[<>=!~;\[]", requirement)[0].strip())
        for requirement in pyproject["project"]["dependencies"]
    }


def _undeclared(declared: set[str]) -> dict[str, tuple[list[str], list[str]]]:
    """
    Return imported modules not provided by any declared distribution.

    Maps import name to (providing distributions, call sites). A module that no
    installed distribution provides is reported with an empty distribution list
    rather than skipped — an unresolvable import is a finding, not a pass.
    """
    provided_by = packages_distributions()
    problems: dict[str, tuple[list[str], list[str]]] = {}
    for module, sites in sorted(_third_party_imports().items()):
        distributions = sorted({_normalize(d) for d in provided_by.get(module, [])})
        if not distributions or not set(distributions) & declared:
            problems[module] = (distributions, sites)
    return problems


def test_third_party_imports_are_declared_runtime_dependencies() -> None:
    """Every third-party module imported by tvkit/ must be a declared dependency."""
    problems = _undeclared(_declared_runtime_distributions())

    if problems:
        lines = [
            "Imported by tvkit/ but not declared in [project.dependencies]:",
            "",
        ]
        for module, (distributions, sites) in problems.items():
            provider = ", ".join(distributions) if distributions else "no installed distribution"
            lines.append(f"  {module!r} (provided by {provider})")
            for site in sites[:5]:
                lines.append(f"      {site}")
        lines += [
            "",
            "These import fine here because a dev dependency happens to supply them,",
            "and will raise ImportError for anyone installing tvkit from PyPI.",
            "Add the distribution to [project.dependencies] in pyproject.toml.",
        ]
        raise AssertionError("\n".join(lines))


def test_guard_detects_an_undeclared_dependency() -> None:
    """
    The guard must fail when a dependency is missing — otherwise it is decoration.

    Re-runs the check with one genuinely-imported distribution dropped from the
    declared set, reproducing the shape of the pre-0.13.1 ``pyyaml`` bug. Without
    this, a regression that made ``_third_party_imports()`` return nothing would turn
    the test above into a vacuous pass that still reported green.

    The victim is chosen dynamically rather than hard-coded, so that legitimately
    dropping any single dependency does not fail this test for the wrong reason.
    """
    declared = _declared_runtime_distributions()
    provided_by = packages_distributions()

    covered = {
        module: sorted({_normalize(d) for d in provided_by.get(module, [])} & declared)
        for module in _third_party_imports()
    }
    candidates = {module: dists for module, dists in covered.items() if dists}
    assert candidates, "no imported module maps to a declared distribution — nothing to test with"

    module, distributions = sorted(candidates.items())[0]
    problems = _undeclared(declared - set(distributions))

    assert module in problems, (
        f"removing {distributions} from the declared set did not make the guard flag "
        f"{module!r} — the guard would not catch the bug it exists for"
    )


def test_declared_runtime_dependencies_are_actually_imported() -> None:
    """
    Every declared runtime dependency must be imported somewhere under tvkit/.

    The reverse of the guard above. Until 0.14.0 tvkit declared six packages it never
    imported — ``pandas``, ``pyarrow``, ``matplotlib``, ``seaborn``, ``curl-cffi`` and
    ``rich`` — which together pulled 21 extra packages and ~380 MB into every install.

    Optional extras are deliberately excluded: ``[project.optional-dependencies]``
    exists precisely for packages tvkit does not import, such as the ``pandas`` extra
    that enables Polars' ``.to_pandas()`` interop.
    """
    imported = set(_third_party_imports())
    provided_by = packages_distributions()

    # invert module -> distributions into distribution -> modules
    supplies: dict[str, set[str]] = {}
    for module, distributions in provided_by.items():
        for distribution in distributions:
            supplies.setdefault(_normalize(distribution), set()).add(module)

    unused = sorted(
        distribution
        for distribution in _declared_runtime_distributions()
        if not (supplies.get(distribution, set()) & imported)
    )

    assert not unused, (
        f"Declared in [project.dependencies] but never imported by tvkit/: {unused}. "
        "Every runtime dependency is installed for every user, so an unused one is pure "
        "weight (and extra security surface). Remove it, or move it to "
        "[project.optional-dependencies] if it enables an opt-in integration."
    )


def test_import_scan_finds_known_dependencies() -> None:
    """
    Anchor the scanner against known imports.

    A parsing regression that silently found zero modules would make the guard pass
    for the wrong reason. These are imported unconditionally by tvkit and are not
    going away quietly.
    """
    modules = _third_party_imports()

    assert modules, "no third-party imports discovered under tvkit/ — the AST scan is broken"
    for expected in ("pydantic", "websockets", "polars", "httpx"):
        assert expected in modules, f"expected tvkit/ to import {expected!r}"


def test_lazy_and_type_checking_imports_are_scanned() -> None:
    """
    Imports nested in function bodies and TYPE_CHECKING blocks must be found.

    The bug this file guards against was a lazy ``import yaml`` inside a function, so
    a header-only scan would have missed it entirely.
    """
    modules = _imported_top_level_modules(PACKAGE_DIR)

    # lazy, inside load_exchange_overrides()
    assert "yaml" in modules
    assert any("tvkit/time/exchange.py" in site for site in modules["yaml"])

    # lazy, inside _get_browser_cookie3()
    assert "browser_cookie3" in modules
    assert any("tvkit/auth/cookie_provider.py" in site for site in modules["browser_cookie3"])
