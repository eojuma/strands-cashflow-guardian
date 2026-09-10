#!/usr/bin/env python3
"""Stage a self-contained Lambda deployment directory, offline.

Why this exists: `sam build` normally runs `pip install -r requirements.txt`
inside a container, which needs network access and installs the dependency set
twice (once per function). This script instead reuses the packages already
installed in the project virtualenv and copies only the *runtime* dependency
closure into the build directory, so deployment works with no network access.

It also prunes ``googleapiclient``'s discovery cache down to the one document the
Gmail tool needs (``gmail.v1.json``), saving ~100 MB.

Usage:
    python scripts/build_lambda_package.py [dest]        # default: .lambda_build

The destination must NOT contain a requirements.txt — that is deliberate, so
`sam build` only copies the code instead of trying to pip-install anything.
"""

from __future__ import annotations

import argparse
import importlib.metadata as md
import shutil
import sys
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIRS = ("agents", "memory", "lambda_handlers")
DEFAULT_REQUIREMENTS = REPO_ROOT / "requirements-lambda.txt"
# Only the Gmail v1 discovery document is needed by agents/tools/gmail_tool.py.
KEEP_DISCOVERY_DOCS = {"gmail.v1.json"}


def _norm(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def _runtime_closure(roots: list[str]) -> list[md.Distribution]:
    """Resolve the installed dependency closure of ``roots`` for this interpreter."""
    env = default_environment()
    seen: set[str] = set()
    order: list[md.Distribution] = []

    def walk(name: str) -> None:
        key = _norm(name)
        if key in seen:
            return
        try:
            dist = md.distribution(name)
        except md.PackageNotFoundError:
            raise SystemExit(
                f"Dependency {name!r} is not installed in this interpreter "
                f"({sys.executable}). Run `pip install -r requirements.txt` first."
            )
        seen.add(key)
        order.append(dist)
        for req_str in dist.requires or []:
            try:
                req = Requirement(req_str)
            except Exception:  # noqa: BLE001 - tolerate odd metadata
                continue
            if req.marker and not req.marker.evaluate(env):
                continue
            walk(req.name)

    for root in roots:
        walk(root)
    return order


def _roots_from_requirements(path: Path) -> list[str]:
    names: list[str] = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        names.append(Requirement(line).name)
    return names


def _copy_dist(dist: md.Distribution, site: Path, dest: Path) -> None:
    for f in dist.files or []:
        if ".." in f.parts:
            continue
        if f.suffix == ".pyc" or "__pycache__" in f.parts:
            continue
        src = site / f
        if not src.is_file():
            continue
        target = dest / f
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


def _prune_discovery_docs(dest: Path) -> None:
    docs = dest / "googleapiclient" / "discovery_cache" / "documents"
    if not docs.is_dir():
        return
    for path in docs.iterdir():
        if path.is_file() and path.suffix == ".json" and path.name not in KEEP_DISCOVERY_DOCS:
            path.unlink()


def _copy_backend(dest: Path) -> None:
    for name in BACKEND_DIRS:
        src = REPO_ROOT / name
        target = dest / name
        shutil.copytree(
            src,
            target,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            dirs_exist_ok=True,
        )


def _dir_size_mb(path: Path) -> float:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) / 1e6


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dest", nargs="?", default=str(REPO_ROOT / ".lambda_build"))
    parser.add_argument("--requirements", default=str(DEFAULT_REQUIREMENTS))
    args = parser.parse_args()

    dest = Path(args.dest).resolve()
    site = Path(sysconfig_site_packages())

    print(f"Staging Lambda package into {dest}")
    print(f"  interpreter:   {sys.executable}")
    print(f"  site-packages: {site}")

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    _copy_backend(dest)
    print(f"  copied backend: {', '.join(BACKEND_DIRS)}")

    roots = _roots_from_requirements(Path(args.requirements))
    dists = _runtime_closure(roots)
    for dist in dists:
        _copy_dist(dist, site, dest)
    _prune_discovery_docs(dest)
    print(f"  copied {len(dists)} runtime distributions (discovery cache pruned)")

    # Deliberately ensure sam build does not try to pip install anything.
    stray = dest / "requirements.txt"
    if stray.exists():
        stray.unlink()

    print(f"Done: {_dir_size_mb(dest):.1f} MB (uncompressed)")


def sysconfig_site_packages() -> str:
    import sysconfig

    return sysconfig.get_paths()["purelib"]


if __name__ == "__main__":
    main()
