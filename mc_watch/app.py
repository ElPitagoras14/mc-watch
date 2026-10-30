"""Wires config, poller, tray and panel together."""

import logging
import threading
from pathlib import Path

import webview

from mc_watch import __version__
from mc_watch.config import Config, config_dir, config_path, load_config
from mc_watch.log import setup_logging
from mc_watch.models import Snapshot
from mc_watch.poller import Poller
from mc_watch.servers import ServerManager
from mc_watch.tray import Tray
from mc_watch.view import snapshot_payload
from mc_watch.window import Panel, Payload

log = logging.getLogger(__name__)


class App:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or config_dir()
        setup_logging(self.directory)
        log.info("mc-watch %s", __version__)

        self.config: Config = load_config(self.directory)
        self._config_path = str(config_path(self.directory))
        self.poller = Poller(self.config.servers, self.config.poll_interval_secs)
        self.servers = ServerManager(self.directory, self.config, self.poller)
        self.panel = Panel(
            lambda: self._payload(self.poller.snapshot()),
            add_server=self.servers.add_server,
            refresh=self.poller.refresh,
        )
        self.tray = Tray(
            on_toggle=self.panel.toggle,
            on_open=self.panel.show,
            on_quit=self.quit,
        )
        self.poller.subscribe(self.servers.on_snapshot)
        self.poller.subscribe(self._on_snapshot)
        self._quit_lock = threading.Lock()
        self._quitting = False

    def _payload(self, snapshot: Snapshot) -> Payload:
        return snapshot_payload(
            snapshot,
            config_path=self._config_path,
            version=__version__,
            config_error=self.config.error,
        )

    def _on_snapshot(self, snapshot: Snapshot) -> None:
        self.tray.update(snapshot)
        self.panel.push(self._payload(snapshot))

    def run(self) -> int:
        """Block until the app quits."""
        self.panel.create()
        try:
            # The GUI loop owns the main thread; `_start_background` runs once it is up.
            webview.start(self._start_background)
        finally:
            self.quit()
        log.info("mc-watch terminó")
        return 0

    def _start_background(self) -> None:
        self.tray.start()
        self.tray.update(self.poller.snapshot())
        self.poller.start()

    def quit(self) -> None:
        """Stop everything. Safe to call from any thread, more than once."""
        with self._quit_lock:
            if self._quitting:
                return
            self._quitting = True
        log.info("Saliendo")
        self.poller.stop()
        self.tray.stop()
        self.panel.destroy()
