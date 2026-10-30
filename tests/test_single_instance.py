import tempfile
import threading
import unittest
from pathlib import Path

from mc_watch.single_instance import Guard, acquire


class SingleInstanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.guards: list[Guard] = []

    def tearDown(self) -> None:
        for guard in self.guards:
            guard.close()

    def directory(self, name: str) -> Path:
        path = Path(self._tmp.name) / name
        path.mkdir()
        return path

    def test_second_launch_asks_the_first_to_show(self) -> None:
        directory = self.directory("a")
        first = acquire(directory)
        assert first is not None
        self.guards.append(first)
        shown = threading.Event()
        first.serve(shown.set)

        self.assertIsNone(acquire(directory))
        self.assertTrue(shown.wait(2))

    def test_another_config_directory_runs_alongside(self) -> None:
        first = acquire(self.directory("a"))
        second = acquire(self.directory("b"))
        self.guards.extend(guard for guard in (first, second) if guard is not None)
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)


if __name__ == "__main__":
    unittest.main()
