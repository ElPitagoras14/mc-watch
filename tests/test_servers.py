import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mc_watch.config import Config, ConfigWriteError, config_path, load_config
from mc_watch.models import (
    Edition,
    ProbeOk,
    ProbeResult,
    ProbeUnreachable,
    ProbeUnresolvable,
    ServerConfig,
    State,
)
from mc_watch.poller import Poller
from mc_watch.servers import ServerManager
from tests.test_poller import Collector

JAVA_OK = ProbeOk(online=4, max=20, latency_ms=10.0, edition=Edition.JAVA)
BEDROCK_OK = ProbeOk(online=2, max=10, latency_ms=30.0, edition=Edition.BEDROCK)


class ServerManagerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.path = config_path(self.directory)
        self.probed: list[ServerConfig] = []
        self.result: ProbeResult = JAVA_OK

    async def probe_fn(self, server: ServerConfig, *, query: bool = False) -> ProbeResult:
        self.probed.append(server)
        return self.result

    def make(
        self, config: Config | None = None, interval: float = 3600
    ) -> tuple[ServerManager, Poller]:
        config = config or load_config(self.directory)
        poller = Poller(config.servers, interval, self.probe_fn)
        self.addCleanup(poller.stop)
        manager = ServerManager(self.directory, config, poller, self.probe_fn)
        poller.subscribe(manager.on_snapshot)
        return manager, poller


class AddServerTest(ServerManagerTestCase):
    def started(self, config: Config | None = None) -> tuple[ServerManager, Poller]:
        manager, poller = self.make(config)
        poller.start()
        self.probed.clear()
        return manager, poller

    def test_adds_a_java_server(self) -> None:
        manager, poller = self.started()

        reply = manager.add_server("Hypixel", "mc.hypixel.net")

        self.assertEqual(reply, {"ok": True})
        status = poller.snapshot().servers[0]
        self.assertEqual(status.server, ServerConfig("Hypixel", "mc.hypixel.net", Edition.JAVA))
        self.assertEqual((status.state, status.online, status.max), (State.ONLINE, 4, 20))
        saved = load_config(self.directory).servers
        self.assertEqual(saved, (ServerConfig("Hypixel", "mc.hypixel.net", Edition.JAVA),))

    def test_probes_with_an_unknown_edition_so_both_protocols_are_tried(self) -> None:
        manager, _ = self.started()
        manager.add_server("A", "a.example.com")
        self.assertEqual([s.edition for s in self.probed], [Edition.UNKNOWN])

    def test_adds_a_bedrock_server(self) -> None:
        self.result = BEDROCK_OK
        manager, poller = self.started()

        self.assertEqual(manager.add_server("Isla", "isla.example.com"), {"ok": True})

        self.assertEqual(poller.snapshot().servers[0].server.edition, Edition.BEDROCK)
        self.assertIn('edition = "bedrock"', self.path.read_text(encoding="utf-8"))

    def test_unresolvable_host_adds_nothing(self) -> None:
        self.result = ProbeUnresolvable()
        manager, poller = self.started()

        reply = manager.add_server("X", "no-existe.invalid")

        self.assertFalse(reply["ok"])
        self.assertEqual(reply["field"], "address")
        self.assertEqual(reply["message"], "No se encontró el host")
        self.assertEqual(poller.snapshot().servers, ())
        self.assertFalse(self.path.exists())

    def test_nobody_answering_adds_an_unknown_server(self) -> None:
        self.result = ProbeUnreachable()
        manager, poller = self.started()

        self.assertEqual(manager.add_server("X", "mudo.example.com"), {"ok": True})

        status = poller.snapshot().servers[0]
        self.assertEqual(status.server.edition, Edition.UNKNOWN)
        self.assertEqual(status.state, State.QUERYING)
        self.assertIn('edition = "unknown"', self.path.read_text(encoding="utf-8"))

    def test_empty_name_uses_the_address(self) -> None:
        manager, poller = self.started()
        manager.add_server("", "play.example.com")
        self.assertEqual(poller.snapshot().servers[0].server.name, "play.example.com")

    def test_validation_errors_do_not_touch_the_network(self) -> None:
        manager, _ = self.started()

        reply = manager.add_server("A", "")
        self.assertEqual((reply["ok"], reply["field"]), (False, "address"))
        reply = manager.add_server("A", "a.example.com:99999")
        self.assertEqual((reply["ok"], reply["field"]), (False, "address"))

        self.assertEqual(self.probed, [])
        self.assertFalse(self.path.exists())

    def test_duplicate_is_rejected(self) -> None:
        manager, poller = self.started()
        manager.add_server("A", "play.example.com")
        self.probed.clear()

        reply = manager.add_server("B", "Play.Example.com")

        self.assertEqual((reply["ok"], reply["field"]), (False, "address"))
        self.assertEqual(len(poller.snapshot().servers), 1)
        self.assertEqual(self.probed, [])

    def test_write_failure_adds_nothing(self) -> None:
        manager, poller = self.started()

        with mock.patch(
            "mc_watch.servers.append_server", side_effect=ConfigWriteError("sin permisos")
        ):
            reply = manager.add_server("A", "a.example.com")

        self.assertEqual(reply, {"ok": False, "field": None, "message": "sin permisos"})
        self.assertEqual(poller.snapshot().servers, ())

    def test_unwritable_config_is_refused_without_probing(self) -> None:
        broken = "esto no es toml ["
        self.path.write_text(broken, encoding="utf-8")
        config = load_config(self.directory)
        manager, poller = self.started(config)

        reply = manager.add_server("A", "a.example.com")

        self.assertFalse(reply["ok"])
        self.assertIn("config.toml", reply["message"])
        self.assertEqual(self.probed, [])
        self.assertEqual(self.path.read_text(encoding="utf-8"), broken)
        self.assertEqual(poller.snapshot().servers, ())

    def test_stopped_poller_is_reported_not_raised(self) -> None:
        manager, _ = self.make()  # never started

        reply = manager.add_server("A", "a.example.com")

        self.assertFalse(reply["ok"])
        self.assertFalse(self.path.exists())

    def test_added_server_does_not_rewrite_its_edition_on_the_next_snapshot(self) -> None:
        self.result = ProbeUnreachable()
        manager, poller = self.make(interval=0.05)
        poller.start()
        collector = Collector()
        poller.subscribe(collector)
        manager.add_server("X", "mudo.example.com")
        before = self.path.read_text(encoding="utf-8")

        with mock.patch("mc_watch.servers.set_edition") as set_edition:
            count = len(collector.snapshots)
            self.assertTrue(collector.wait_for(count + 2))

        set_edition.assert_not_called()
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)


class PersistDetectedEditionTest(ServerManagerTestCase):
    HAND_WRITTEN = (
        '# a mano\n[[servers]]\nname = "Hypixel" # el grande\naddress = "mc.hypixel.net"\n'
    )

    def run_one_cycle(self, config: Config) -> None:
        manager, poller = self.make(config, interval=3600)
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(1))
        self.assertIsNotNone(manager)

    def test_detected_edition_is_written_to_the_entry(self) -> None:
        self.path.write_text(self.HAND_WRITTEN, encoding="utf-8")
        config = load_config(self.directory)

        self.run_one_cycle(config)

        text = self.path.read_text(encoding="utf-8")
        self.assertEqual(text, self.HAND_WRITTEN + 'edition = "java"\n')
        self.assertEqual(load_config(self.directory).servers[0].edition, Edition.JAVA)

    def test_nothing_is_written_while_the_server_stays_unknown(self) -> None:
        self.result = ProbeUnreachable()
        self.path.write_text(self.HAND_WRITTEN, encoding="utf-8")

        self.run_one_cycle(load_config(self.directory))

        self.assertEqual(self.path.read_text(encoding="utf-8"), self.HAND_WRITTEN)

    def test_known_edition_is_not_rewritten(self) -> None:
        self.path.write_text(self.HAND_WRITTEN + 'edition = "java"\n', encoding="utf-8")
        config = load_config(self.directory)

        with mock.patch("mc_watch.servers.set_edition") as set_edition:
            self.run_one_cycle(config)

        set_edition.assert_not_called()

    def test_unwritable_config_is_never_written(self) -> None:
        config = Config(
            servers=(ServerConfig("Hypixel", "mc.hypixel.net"),), writable=False, error="roto"
        )
        with mock.patch("mc_watch.servers.set_edition") as set_edition:
            self.run_one_cycle(config)
        set_edition.assert_not_called()

    def test_write_failure_is_logged_and_does_not_stop_the_poller(self) -> None:
        self.path.write_text(self.HAND_WRITTEN, encoding="utf-8")
        config = load_config(self.directory)

        with (
            mock.patch(
                "mc_watch.servers.set_edition", side_effect=ConfigWriteError("sin permisos")
            ),
            self.assertLogs("mc_watch.servers", level="WARNING"),
        ):
            self.run_one_cycle(config)


class RenameAndRemoveTest(ServerManagerTestCase):
    TWO = (
        '[[servers]]\nname = "A"\naddress = "a.example.com"\nedition = "java"\n\n'
        '[[servers]]\nname = "B"\naddress = "b.example.com"\nedition = "java"\n'
    )

    def started(self) -> tuple[ServerManager, Poller]:
        self.path.write_text(self.TWO, encoding="utf-8")
        manager, poller = self.make()
        poller.start()
        return manager, poller

    def test_rename_and_remove_save_the_file_and_update_the_poller(self) -> None:
        manager, poller = self.started()

        self.assertEqual(
            manager.rename_server("a.example.com", "  Alfa "), {"ok": True, "name": "Alfa"}
        )
        self.assertEqual(manager.remove_server("b.example.com"), {"ok": True})

        self.assertEqual([s.server.name for s in poller.snapshot().servers], ["Alfa"])
        self.assertEqual([s.name for s in load_config(self.directory).servers], ["Alfa"])

    def test_empty_name_falls_back_to_the_address_and_a_long_one_is_rejected(self) -> None:
        manager, poller = self.started()

        manager.rename_server("a.example.com", "  ")
        reply = manager.rename_server("b.example.com", "x" * 41)

        self.assertEqual(poller.snapshot().servers[0].server.name, "a.example.com")
        self.assertEqual((reply["ok"], reply["field"]), (False, "name"))
        self.assertEqual(poller.snapshot().servers[1].server.name, "B")

    def test_write_failure_changes_nothing(self) -> None:
        manager, poller = self.started()

        with (
            mock.patch("mc_watch.servers.set_name", side_effect=ConfigWriteError("sin permisos")),
            mock.patch(
                "mc_watch.servers.remove_server", side_effect=ConfigWriteError("sin permisos")
            ),
        ):
            renamed = manager.rename_server("a.example.com", "Alfa")
            removed = manager.remove_server("b.example.com")

        self.assertEqual((renamed["ok"], removed["ok"]), (False, False))
        self.assertEqual([s.server.name for s in poller.snapshot().servers], ["A", "B"])

    def test_unwritable_config_blocks_both(self) -> None:
        config = Config(servers=(ServerConfig("A", "a.example.com"),), writable=False, error="roto")
        manager, poller = self.make(config)
        poller.start()

        self.assertFalse(manager.rename_server("a.example.com", "Alfa")["ok"])
        self.assertFalse(manager.remove_server("a.example.com")["ok"])
        self.assertEqual(len(poller.snapshot().servers), 1)


if __name__ == "__main__":
    unittest.main()
