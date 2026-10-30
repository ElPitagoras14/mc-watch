import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

from mc_watch.preview import build_preview, scenarios

NOW = 1730000000.0


def extract_data(html: str) -> list[dict[str, Any]]:
    match = re.search(r"window\.__MCW_PREVIEW__ = (.*?);</script>", html, re.DOTALL)
    assert match is not None
    return json.loads(match.group(1).replace("<\\/", "</"))


class PreviewTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name) / "preview"

    def test_scenarios_cover_the_four_states_and_the_empty_panel(self) -> None:
        data = scenarios(NOW)
        by_label = {item["label"]: item["payload"] for item in data}

        states = {s["state"] for item in data for s in item["payload"]["servers"]}
        self.assertEqual(states, {"querying", "online", "offline", "error"})
        self.assertEqual(by_label["Vacío"]["servers"], [])
        self.assertIsNone(by_label["Antes del 1er ciclo"]["updated_at"])
        self.assertGreater(len(by_label["Muchos (scroll)"]["servers"]), 8)

    def test_builds_a_self_contained_page(self) -> None:
        index = build_preview(self.directory, now=NOW)

        self.assertEqual(index, self.directory / "index.html")
        for name in ("index.html", "styles.css", "app.js"):
            self.assertTrue((self.directory / name).exists(), name)
        html = index.read_text(encoding="utf-8")
        self.assertLess(html.index("__MCW_PREVIEW__"), html.index('src="app.js"'))
        self.assertEqual(len(extract_data(html)), 4)

    def test_does_not_modify_the_real_ui(self) -> None:
        from mc_watch.preview import UI_DIR

        before = (UI_DIR / "index.html").read_text(encoding="utf-8")
        build_preview(self.directory, now=NOW)
        self.assertEqual((UI_DIR / "index.html").read_text(encoding="utf-8"), before)
        self.assertNotIn("__MCW_PREVIEW__", before)


if __name__ == "__main__":
    unittest.main()
