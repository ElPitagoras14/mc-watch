"""Print the project version, or fail if it is not unique and well formed.

The version lives in two places, `pyproject.toml` and `mc_watch/__init__.py`, and the release
pipeline needs it before syncing dependencies. So this uses only the standard library and reads
the package as text instead of importing it.

    python scripts/release_version.py

On GitHub Actions it also writes `version=<value>` to `$GITHUB_OUTPUT`.
"""

import os
import re
import sys
import tomllib
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]

# MAJOR.MINOR.PATCH, no suffixes: the tag and the .exe's version resource look like this.
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
DUNDER = re.compile(r"^__version__\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)


class VersionError(Exception):
    """The version cannot be determined; the message says why."""


def read_pyproject(path: Path) -> str:
    project = tomllib.loads(path.read_text("utf-8")).get("project")
    version = (
        cast("dict[str, object]", project).get("version") if isinstance(project, dict) else None
    )
    if not isinstance(version, str):
        raise VersionError(f"{path.name} no declara project.version como cadena")
    return version


def read_package(path: Path) -> str:
    found = DUNDER.search(path.read_text("utf-8"))
    if found is None:
        raise VersionError(f"{path.name} no declara __version__")
    return found.group(1)


def version(root: Path = ROOT) -> str:
    declared = read_pyproject(root / "pyproject.toml")
    packaged = read_package(root / "mc_watch" / "__init__.py")
    if declared != packaged:
        raise VersionError(
            f"la versión diverge: pyproject.toml dice {declared!r} "
            f"y mc_watch/__init__.py dice {packaged!r}"
        )
    if not SEMVER.match(declared):
        raise VersionError(f"la versión {declared!r} no tiene la forma MAJOR.MINOR.PATCH")
    return declared


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]).resolve() if argv else ROOT
    try:
        ver = version(root)
    except (VersionError, OSError, tomllib.TOMLDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(ver)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as file:
            file.write(f"version={ver}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
