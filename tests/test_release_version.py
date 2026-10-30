import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import release_version  # noqa: E402


class ReleaseVersionTest(unittest.TestCase):
    def project(self, pyproject: str, package: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "mc_watch").mkdir()
        (root / "pyproject.toml").write_text(f'[project]\nversion = "{pyproject}"\n', "utf-8")
        (root / "mc_watch" / "__init__.py").write_text(f'__version__ = "{package}"\n', "utf-8")
        return root

    def test_matching_versions_are_printed_and_exported(self) -> None:
        root = self.project("0.2.0", "0.2.0")
        output = root / "output"
        os.environ["GITHUB_OUTPUT"] = str(output)
        self.addCleanup(os.environ.pop, "GITHUB_OUTPUT")
        self.assertEqual(release_version.main([str(root)]), 0)
        self.assertEqual(output.read_text("utf-8"), "version=0.2.0\n")

    def test_diverging_versions_name_both(self) -> None:
        root = self.project("0.2.0", "0.1.0")
        with self.assertRaises(release_version.VersionError) as raised:
            release_version.version(root)
        self.assertIn("0.2.0", str(raised.exception))
        self.assertIn("0.1.0", str(raised.exception))

    def test_malformed_version_is_rejected(self) -> None:
        root = self.project("0.1", "0.1")
        with self.assertRaises(release_version.VersionError):
            release_version.version(root)


if __name__ == "__main__":
    unittest.main()
