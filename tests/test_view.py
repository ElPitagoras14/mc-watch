import json
import unittest

from mc_watch.models import Edition, ServerConfig, ServerStatus, Snapshot, State
from mc_watch.view import snapshot_payload

SERVER = ServerConfig("Survival", "play.example.com")


class SnapshotPayloadTest(unittest.TestCase):
    def test_online_server(self) -> None:
        snapshot = Snapshot(
            servers=(ServerStatus(SERVER, State.ONLINE, online=3, max=20),),
            updated_at=1730000000.0,
        )

        payload = snapshot_payload(snapshot, config_path=r"C:\cfg\config.toml", version="0.1.0")

        self.assertEqual(
            payload,
            {
                "servers": [
                    {
                        "name": "Survival",
                        "address": "play.example.com",
                        "edition": "unknown",
                        "state": "online",
                        "online": 3,
                        "max": 20,
                    }
                ],
                "updated_at": 1730000000.0,
                "config_path": r"C:\cfg\config.toml",
                "config_error": None,
                "version": "0.1.0",
            },
        )

    def test_all_states_use_stable_names(self) -> None:
        snapshot = Snapshot(
            servers=tuple(ServerStatus(SERVER, state) for state in State), updated_at=None
        )

        payload = snapshot_payload(snapshot, config_path="x", version="0.1.0")

        self.assertEqual(
            [server["state"] for server in payload["servers"]],
            ["querying", "online", "offline", "error"],
        )
        self.assertIsNone(payload["updated_at"])

    def test_edition_uses_stable_names(self) -> None:
        servers = tuple(
            ServerStatus(ServerConfig("S", "s.example.com", edition), State.ONLINE, 1, 2)
            for edition in Edition
        )
        payload = snapshot_payload(
            Snapshot(servers=servers, updated_at=None), config_path="x", version="0.1.0"
        )
        self.assertEqual(
            [server["edition"] for server in payload["servers"]], ["java", "bedrock", "unknown"]
        )

    def test_config_error_is_passed_through(self) -> None:
        payload = snapshot_payload(
            Snapshot(servers=(), updated_at=None),
            config_path="x",
            version="0.1.0",
            config_error="config.toml tiene un error",
        )
        self.assertEqual(payload["config_error"], "config.toml tiene un error")

    def test_payload_is_json_serializable(self) -> None:
        snapshot = Snapshot(servers=(ServerStatus(SERVER, State.OFFLINE),), updated_at=1.5)

        json.dumps(snapshot_payload(snapshot, config_path="x", version="0.1.0"))


if __name__ == "__main__":
    unittest.main()
