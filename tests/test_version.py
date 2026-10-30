import tomllib
import unittest
from pathlib import Path

import mc_watch

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


class VersionTest(unittest.TestCase):
    def test_package_version_matches_pyproject(self) -> None:
        with PYPROJECT.open("rb") as file:
            declared = tomllib.load(file)["project"]["version"]
        self.assertEqual(mc_watch.__version__, declared)


if __name__ == "__main__":
    unittest.main()
